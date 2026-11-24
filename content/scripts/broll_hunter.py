#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：外部実写B-roll収集・検品 & 編集オーバーレイ生成ツール

自社撮影素材だけで全カットが単調になるのを防ぐため、前半の生活・悩み・共感パート用の
実写B-roll（Mixkit / Pexels / Pixabay / 公開RED）を収集・フレーム検品し、
必要に応じてコメント吹き出しやバッジ等の編集オーバーレイPNG/GIFを生成します。

使い方:
  # 1. Mixkit からキー不要で生活B-rollを検索（商用無料・透かしなし）
  python3 broll_hunter.py search-mixkit --query "cosmetics" --limit 15

  # 2. Pexels API から縦9:16専用検索（環境変数 PEXELS_API_KEY が必要）
  python3 broll_hunter.py search-pexels --query "skincare hand" --limit 10

  # 3. 公開RED（小紅書）投稿URLを yt-dlp で取得＋フレーム検品シート自動生成
  python3 broll_hunter.py fetch-red --url "https://www.xiaohongshu.com/explore/..." --out-dir ./assets/red

  # 4. 選んだMP4 URLをダウンロード＋1秒刻み検品シート生成
  python3 broll_hunter.py download --url "https://assets.mixkit.co/..." --out ./assets/broll/clip.mp4 --sheet ./work/clip_sheet.png

  # 5. 編集オーバーレイ生成（コメント吹き出しPNG / 左上バッジPNG）
  python3 broll_hunter.py make-overlay --kind comment --text "美容液って結局何本使えばいいの？" --out ./work/comment_q.png
"""

from __future__ import annotations
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from PIL import Image, ImageDraw, ImageFont


def load_jp_font(size: int = 34):
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def ffprobe_info(path: str) -> dict:
    res = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate:format=duration",
            "-of", "json", path,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(res.stdout)
    st = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    w = int(st.get("width") or 0)
    h = int(st.get("height") or 0)
    dur = float(fmt.get("duration") or 0.0)
    orient = "portrait" if h >= w else "landscape"
    crop_factor_for_9_16 = 1.0 if orient == "portrait" else round((w / max(1, h)) / (9 / 16), 2)
    return {
        "width": w,
        "height": h,
        "duration_sec": round(dur, 2),
        "orientation": orient,
        "base_crop_factor_to_9_16": crop_factor_for_9_16,
        "within_2x_rule": crop_factor_for_9_16 <= 2.0,
    }


def make_inspect_sheet(video_path: str, out_png: str, max_frames: int = 12) -> str:
    info = ffprobe_info(video_path)
    dur = max(0.5, info["duration_sec"])
    step = max(0.5, round(dur / max_frames, 2))
    times = []
    t = 0.2
    while t < dur - 0.1 and len(times) < max_frames:
        times.append(round(t, 2))
        t += step
    if not times:
        times = [0.0]

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    font = load_jp_font(22)
    with tempfile.TemporaryDirectory(prefix="broll_sheet_") as tmp:
        thumbs = []
        for idx, ts in enumerate(times):
            jpg = os.path.join(tmp, f"f_{idx:02d}.jpg")
            # Preview cropped to 9:16 vertical so face/watermark/crop check is exact
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{ts:.2f}", "-i", video_path,
                    "-frames:v", "1",
                    "-vf", "scale=270:480:force_original_aspect_ratio=increase,crop=270:480",
                    jpg,
                ],
                check=True,
            )
            if os.path.isfile(jpg):
                im = Image.open(jpg).convert("RGB")
                d = ImageDraw.Draw(im)
                label = f"{ts:05.2f}s"
                bbox = d.textbbox((0, 0), label, font=font)
                d.rectangle([6, 6, 20 + bbox[2] - bbox[0], 16 + bbox[3] - bbox[1]], fill=(0, 0, 0))
                d.text((12, 10), label, font=font, fill=(255, 255, 0))
                thumbs.append(im)
        cols = min(4, len(thumbs))
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (270 * cols, 480 * rows), (18, 18, 18))
        for idx, im in enumerate(thumbs):
            r, c = divmod(idx, cols)
            sheet.paste(im, (c * 270, r * 480))
        sheet.save(out_png)
    return os.path.abspath(out_png)


def search_mixkit(query: str, limit: int = 15) -> list[dict]:
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", query.strip().lower()).strip("-")
    urls_to_try = [
        f"https://mixkit.co/free-stock-video/discover/{urllib.parse.quote(slug)}/",
        f"https://mixkit.co/free-stock-video/{urllib.parse.quote(slug)}/",
    ]
    items = []
    seen = set()
    for url in urls_to_try:
        r = subprocess.run(["curl", "-fsSL", url], text=True, capture_output=True)
        if r.returncode != 0:
            continue
        for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', r.stdout, re.S):
            try:
                data = json.loads(block)
            except Exception:
                continue
            graph = data.get("@graph") if isinstance(data, dict) else None
            nodes = graph if isinstance(graph, list) else ([data] if isinstance(data, dict) else [])
            for node in nodes:
                if not isinstance(node, dict) or node.get("@type") != "VideoObject":
                    continue
                mp4 = node.get("contentUrl") or ""
                if not mp4 or mp4 in seen:
                    continue
                seen.add(mp4)
                items.append({
                    "source": "mixkit",
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "mp4_url": mp4,
                    "thumb_url": node.get("thumbnailUrl", ""),
                    "license": node.get("license", "https://mixkit.co/license/#videoFree"),
                })
                if len(items) >= limit:
                    return items
    return items


def search_pexels(query: str, limit: int = 10, orientation: str = "portrait") -> dict:
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        return {"status": "missing_api_key", "hint": "環境変数 PEXELS_API_KEY を設定するとPexels縦動画API検索が使えます（https://www.pexels.com/api/）"}
    qs = urllib.parse.urlencode({"query": query, "per_page": limit, "orientation": orientation})
    req = urllib.request.Request(
        f"https://api.pexels.com/videos/search?{qs}",
        headers={"Authorization": api_key},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = []
    for v in data.get("videos", []):
        files = sorted(v.get("video_files", []), key=lambda f: abs((f.get("height") or 0) - 1920))
        best = files[0] if files else {}
        results.append({
            "source": "pexels",
            "id": v.get("id"),
            "duration": v.get("duration"),
            "width": best.get("width"),
            "height": best.get("height"),
            "mp4_url": best.get("link"),
            "page_url": v.get("url"),
        })
    return {"status": "ok", "items": results}


def download_mp4(url: str, out_path: str, sheet_path: str = "") -> dict:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-L", url, "-o", out_path], check=True)
    info = ffprobe_info(out_path)
    out = {"downloaded": os.path.abspath(out_path), **info}
    if sheet_path:
        out["inspect_sheet_png"] = make_inspect_sheet(out_path, sheet_path)
    return out


def fetch_red(url: str, out_dir: str, sheet_dir: str = "") -> dict:
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp が見つかりません。")
    os.makedirs(out_dir, exist_ok=True)
    tpl = os.path.join(out_dir, "red_%(id)s.%(ext)s")
    res = subprocess.run(
        ["yt-dlp", "--no-playlist", "-f", "mp4/bestvideo+bestaudio/best", "--merge-output-format", "mp4", "-o", tpl, url],
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        return {
            "status": "blocked_or_failed",
            "url": url,
            "error": (res.stderr or res.stdout).strip()[-500:],
            "fallback": "公開REDがログイン制限等で取得不可の場合は、Drive既存RED素材または Mixkit / Pexels へ切り替えてください。",
        }
    mp4s = sorted(
        [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".mp4")],
        key=os.path.getmtime,
        reverse=True,
    )
    if not mp4s:
        return {"status": "no_file_downloaded", "url": url}
    latest = mp4s[0]
    info = ffprobe_info(latest)
    out = {"status": "ok", "downloaded": os.path.abspath(latest), **info}
    if sheet_dir:
        os.makedirs(sheet_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(latest))[0]
        out["inspect_sheet_png"] = make_inspect_sheet(latest, os.path.join(sheet_dir, f"{base}_9x16_inspect.png"))
    return out


def make_overlay(kind: str, text: str, out_png: str, subtext: str = "") -> dict:
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    if kind == "comment":
        # TikTok comment-reply style pill card (clean white card with subtle shadow)
        W, H = 760, 220
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([14, 18, W - 10, H - 10], radius=28, fill=(0, 0, 0, 90))
        d.rounded_rectangle([8, 10, W - 16, H - 18], radius=28, fill=(255, 255, 255, 245))
        f_sub = load_jp_font(24)
        f_main = load_jp_font(34)
        header = subtext or "視聴者コメントへの返信"
        d.text((38, 28), header, font=f_sub, fill=(115, 115, 120, 255))
        lines = text.split("\\n") if "\\n" in text else text.split("\n")
        y = 72
        for line in lines[:2]:
            d.text((38, y), line, font=f_main, fill=(24, 24, 28, 255))
            y += 48
        im.save(out_png)
    elif kind == "badge":
        W, H = 560, 110
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([8, 8, W - 8, H - 8], radius=22, fill=(20, 20, 24, 210), outline=(255, 255, 255, 220), width=4)
        f_main = load_jp_font(38)
        bbox = d.textbbox((0, 0), text, font=f_main)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((W - tw) // 2, (H - th) // 2 - 4), text, font=f_main, fill=(255, 255, 255, 255))
        im.save(out_png)
    else:
        raise ValueError(f"Unsupported overlay kind: {kind}")
    return {"status": "ok", "kind": kind, "output_png": os.path.abspath(out_png)}


def main() -> None:
    p = argparse.ArgumentParser(description="TikTok Shop OS B-roll hunter & overlay helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_mk = sub.add_parser("search-mixkit")
    p_mk.add_argument("--query", required=True)
    p_mk.add_argument("--limit", type=int, default=15)

    p_px = sub.add_parser("search-pexels")
    p_px.add_argument("--query", required=True)
    p_px.add_argument("--limit", type=int, default=10)
    p_px.add_argument("--orientation", default="portrait")

    p_dl = sub.add_parser("download")
    p_dl.add_argument("--url", required=True)
    p_dl.add_argument("--out", required=True)
    p_dl.add_argument("--sheet", default="")

    p_red = sub.add_parser("fetch-red")
    p_red.add_argument("--url", required=True)
    p_red.add_argument("--out-dir", required=True)
    p_red.add_argument("--sheet-dir", default="")

    p_ov = sub.add_parser("make-overlay")
    p_ov.add_argument("--kind", choices=["comment", "badge"], required=True)
    p_ov.add_argument("--text", required=True)
    p_ov.add_argument("--subtext", default="")
    p_ov.add_argument("--out", required=True)

    args = p.parse_args()
    if args.cmd == "search-mixkit":
        print(json.dumps(search_mixkit(args.query, args.limit), ensure_ascii=False, indent=2))
    elif args.cmd == "search-pexels":
        print(json.dumps(search_pexels(args.query, args.limit, args.orientation), ensure_ascii=False, indent=2))
    elif args.cmd == "download":
        print(json.dumps(download_mp4(args.url, args.out, args.sheet), ensure_ascii=False, indent=2))
    elif args.cmd == "fetch-red":
        print(json.dumps(fetch_red(args.url, args.out_dir, args.sheet_dir), ensure_ascii=False, indent=2))
    elif args.cmd == "make-overlay":
        print(json.dumps(make_overlay(args.kind, args.text, args.out, args.subtext), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
