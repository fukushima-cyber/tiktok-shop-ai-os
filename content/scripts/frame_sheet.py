#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：0.5秒刻み精密フレームシート生成 & 参考動画構造抽出ツール

用途:
  1. 自社素材の「一番画が強い0.5秒（とろみが落ちる・ツヤが出る・ラベルが正面向く瞬間）」を
     タイムスタンプ付きグリッド画像で目視特定し、plan.json の start_sec を正確に決める。
  2. 共有Drive等の参考動画（競合ヒット動画）を 1.0秒刻みシート＋（faster-whisper導入時）
     タイムスタンプ付き文字起こしへ分解し、売れた構成・フック秒数を構造分析する。

使い方:
  python3 frame_sheet.py --input ./assets/I_apply.mov --out ./work/I_05s.png --step 0.5
  python3 frame_sheet.py --input ./ref_hit.mp4 --out ./work/ref_sheet.png --step 1.0 --transcribe
"""

from __future__ import annotations
import argparse
import json
import math
import os
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont


def ffprobe_duration(path: str) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        check=True,
        text=True,
        capture_output=True,
    )
    return float(res.stdout.strip())


def load_font(size: int = 20):
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_frame_sheet(
    video_path: str,
    out_png: str,
    step: float = 0.5,
    start: float = 0.0,
    end: float | None = None,
    cols: int = 6,
    thumb_w: int = 240,
    max_frames: int = 72,
) -> dict:
    dur = ffprobe_duration(video_path)
    t_end = min(dur, end) if end is not None else dur
    times = []
    t = max(0.0, start)
    while t < t_end - 0.05 and len(times) < max_frames:
        times.append(round(t, 2))
        t += step

    if not times:
        raise ValueError(f"フレーム抽出対象がありません: duration={dur:.2f}s")

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    font = load_font(22)

    with tempfile.TemporaryDirectory(prefix="frame_sheet_") as tmp:
        thumbs = []
        for idx, ts in enumerate(times):
            jpg = os.path.join(tmp, f"f_{idx:03d}.jpg")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{ts:.2f}", "-i", video_path,
                    "-frames:v", "1",
                    "-vf", f"scale={thumb_w}:-2",
                    jpg,
                ],
                check=True,
            )
            if os.path.isfile(jpg):
                im = Image.open(jpg).convert("RGB")
                d = ImageDraw.Draw(im)
                label = f"{ts:05.2f}s"
                bbox = d.textbbox((0, 0), label, font=font)
                lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                d.rectangle([6, 6, 6 + lw + 14, 6 + lh + 10], fill=(0, 0, 0))
                d.text((13, 10), label, font=font, fill=(255, 255, 0))
                thumbs.append((ts, im))

        tw, th = thumbs[0][1].size
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (tw * cols, th * rows), (18, 18, 18))
        for idx, (_, im) in enumerate(thumbs):
            r, c = divmod(idx, cols)
            sheet.paste(im, (c * tw, r * th))
        sheet.save(out_png)

    return {
        "input": os.path.abspath(video_path),
        "duration_sec": round(dur, 2),
        "step_sec": step,
        "frames_extracted": len(times),
        "time_range": [times[0], times[-1]],
        "output_png": os.path.abspath(out_png),
    }


def transcribe_video(video_path: str, model_size: str = "small") -> dict:
    try:
        from faster_whisper import WhisperModel
        import numpy as np
    except Exception:
        return {"status": "skipped", "reason": "faster-whisper is not installed"}

    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video_path, "-ar", "16000", "-ac", "1", "-f", "f32le", "-"],
        check=True,
        stdout=subprocess.PIPE,
    )
    audio_np = np.frombuffer(res.stdout, dtype=np.float32)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_np, language="ja", vad_filter=True)
    items = []
    for seg in segments:
        items.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
    return {
        "status": "ok",
        "language": getattr(info, "language", "ja"),
        "segments": items,
        "full_text": "".join(x["text"] for x in items),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Generate timestamped 0.5s frame sheet & optional transcript")
    p.add_argument("--input", required=True, help="Input video file path")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--step", type=float, default=0.5, help="Interval in seconds (default: 0.5)")
    p.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    p.add_argument("--end", type=float, default=None, help="End time in seconds")
    p.add_argument("--cols", type=int, default=6, help="Grid columns (default: 6)")
    p.add_argument("--max-frames", type=int, default=72, help="Max frames to extract")
    p.add_argument("--transcribe", action="store_true", help="Also transcribe audio with faster-whisper if installed")
    p.add_argument("--whisper-model", default="small", help="Whisper model size (tiny/base/small)")
    args = p.parse_args()

    meta = make_frame_sheet(
        args.input,
        args.out,
        step=args.step,
        start=args.start,
        end=args.end,
        cols=args.cols,
        max_frames=args.max_frames,
    )
    if args.transcribe:
        meta["transcript"] = transcribe_video(args.input, model_size=args.whisper_model)
        json_path = os.path.splitext(args.out)[0] + "_analysis.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        meta["analysis_json"] = os.path.abspath(json_path)

    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
