#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：Muse.ai / GrokBot 向け JSON駆動 本番動画レンダリングエンジン（Skill 06）

特徴:
  - ffmpeg に drawtext (libfreetype) が入っていない軽量VM/Homebrew環境でも動くよう、
    Pillow で 1080x1920 の透明PNGテロップをピクセル実測付きで描画し overlay 合成する（Pillow不在時のみ drawtext へ自動フォールバック）。
  - 日本語フォント自動検出（豆腐文字防止）＋ 記号・改行・クォートでのクラッシュゼロ。
  - 2.0倍以内寄せ・1.1倍以内スロー・SDR/HLG色空間統一・32bit効果音線形ミックス・全体1.2倍速。
  - 「本線mp4（効果音あり）」＋「ナレのみmp4」の2本出力＋1秒コンタクトシートPNG＋ebur128音量ログ自動生成。

使い方:
  python3 render_video.py --plan ./plan.json --out-dir ./output
"""

from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/NotoSansJP-Bold.ttf",
]


def run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def ffmpeg_has_filter(name: str) -> bool:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], text=True, capture_output=True)
    return bool(re.search(rf"\b{re.escape(name)}\b", res.stdout))


def detect_jp_font(explicit: str = "") -> str:
    if explicit and os.path.isfile(explicit):
        return explicit
    for c in FONT_CANDIDATES:
        if os.path.isfile(c):
            return c
    if shutil.which("fc-list"):
        res = subprocess.run(["fc-list", ":lang=ja", "file"], text=True, capture_output=True)
        for line in res.stdout.splitlines():
            p = line.split(":")[0].strip()
            if p and os.path.isfile(p):
                return p
    raise RuntimeError(
        "日本語フォントが見つかりません。preflight_muse.sh を実行するか plan.json の font_path を指定してください。"
    )


def ffprobe_duration(path: str) -> float:
    res = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture=True,
    )
    return float(res.stdout.strip())


def ensure_cut_audio(cut: dict, voice: str, work_dir: str) -> str:
    cid = cut["id"]
    out_wav = os.path.join(work_dir, f"nar_{cid:02d}.wav")
    if cut.get("audio_wav") and os.path.isfile(cut["audio_wav"]):
        run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", cut["audio_wav"],
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_f32le", out_wav,
            ]
        )
        return out_wav

    reading = (cut.get("reading") or cut.get("telop") or "").replace("。", "、").replace("\n", "、").strip()
    if not reading:
        raise ValueError(f"Cut {cid}: reading または audio_wav が必要です。")
    if not shutil.which("edge-tts"):
        raise RuntimeError("edge-tts が見つかりません。pip install edge-tts を実行するか audio_wav を渡してください。")

    tmp_mp3 = os.path.join(work_dir, f"nar_{cid:02d}.mp3")
    run(["edge-tts", "--voice", voice, "--text", reading, "--write-media", tmp_mp3])
    run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", tmp_mp3,
            "-af", "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_f32le", out_wav,
        ]
    )
    return out_wav


KINSOKU_HEAD = set("っゃゅょぁぃぅぇぉッャュョァィゥェォー、。！？!?」』）)].,・…")
PARTICLES = ("から", "まで", "より", "けど", "のに", "ので", "って", "には", "では", "とは", "は", "が", "を", "に", "で", "と", "へ", "の", "も", "、", "。", "！", "？")


def _char_class(ch: str) -> str:
    code = ord(ch)
    if 0x4E00 <= code <= 0x9FFF:
        return "kanji"
    if 0x30A0 <= code <= 0x30FF or ch == "ー":
        return "kata"
    if 0x3040 <= code <= 0x309F:
        return "hira"
    if ch.isascii() and ch.isalnum():
        return "alnum"
    return "other"


def _find_best_break(text: str, draw, font, stroke_w: int, max_width: int) -> int:
    """単語分断・禁則違反・孤立文字(1〜2文字)を避けて自然な文節切れ目を選ぶ"""
    n = len(text)
    # まずmax_widthに収まる最大インデックスを調べる
    max_fit = 0
    for i in range(1, n + 1):
        bbox = draw.textbbox((0, 0), text[:i], font=font, stroke_width=stroke_w)
        if (bbox[2] - bbox[0]) <= max_width:
            max_fit = i
        else:
            break
    if max_fit >= n:
        return n
    if max_fit <= 2:
        return max(1, max_fit)

    # 残り部分も1行に収まりやすいよう、理想的な分割位置（中央寄り）を目標にする
    target = max(3, min(max_fit, round(n / 2)))
    best_idx = None
    best_score = -10**9

    for i in range(2, max_fit + 1):
        left = text[:i]
        right = text[i:]
        if not right:
            continue
        # 行頭禁則文字が次行の先頭に来る位置は強く避ける
        if right[0] in KINSOKU_HEAD:
            continue

        score = 0.0
        # 1) 読点・句点・感嘆符・スペースの直後は最優先
        if left[-1] in "、。！？!? 　":
            score += 100
        # 2) 助詞・接続語の直後
        elif any(left.endswith(p) for p in PARTICLES):
            score += 65
        # 3) 文字種の切れ目（例: 漢字/カタカナ/英数字 -> ひらがな、または逆）
        elif _char_class(left[-1]) != _char_class(right[0]):
            # ただし「数字＋助数詞(7つ/1個)」や「漢字＋送り仮名(言わ/れた)」の分断は減点
            if _char_class(left[-1]) == "alnum" and _char_class(right[0]) == "hira":
                score -= 20
            elif _char_class(left[-1]) == "kanji" and _char_class(right[0]) == "hira":
                score += 5
            else:
                score += 40
        else:
            # 同じ文字種（特にカタカナ・漢字・英数字の単語途中）は強く減点
            if _char_class(left[-1]) in ("kata", "kanji", "alnum"):
                score -= 60
            else:
                score -= 10

        # 4) 孤立文字（左または右が1〜2文字だけ）を強く減点
        if len(right) <= 2 or len(left) <= 2:
            score -= 80
        # 5) 左右バランス（中央に近いほど読みやすい）
        score -= abs(i - target) * 6.0

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx if best_idx is not None else max_fit


def wrap_japanese_telop(text: str, draw, font, stroke_w: int, max_width: int) -> list[str]:
    """明示的な \n を尊重しつつ、幅超過時のみ日本語の文節・バランスで改行する"""
    raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    wrapped: list[str] = []
    for ln in raw_lines:
        cur = ln
        while cur:
            bbox = draw.textbbox((0, 0), cur, font=font, stroke_width=stroke_w)
            if (bbox[2] - bbox[0]) <= max_width:
                wrapped.append(cur)
                break
            idx = _find_best_break(cur, draw, font, stroke_w, max_width)
            if idx <= 0 or idx >= len(cur):
                wrapped.append(cur)
                break
            wrapped.append(cur[:idx].rstrip(" 　"))
            cur = cur[idx:].lstrip(" 　")
    return wrapped


def render_telop_png(
    text: str,
    font_path: str,
    out_png: str,
    pos_y: int = 1240,
    font_size: int = 64,
    fill_rgb: tuple[int, int, int] = (255, 255, 255),
    max_width: int = 720,
) -> dict:
    """1080x1920 透明PNGにテロップを描画し、実測幅(px)・改行品質・安全領域収まりを返す"""
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    stroke_w = 8
    line_gap = 14

    wrapped = wrap_japanese_telop(text, draw, font, stroke_w, max_width)

    y = pos_y
    max_measured_w = 0
    for ln in wrapped:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=stroke_w)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        max_measured_w = max(max_measured_w, tw)
        x = int((1080 - tw) / 2)
        draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 190), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 190))
        draw.text((x, y), ln, font=font, fill=(*fill_rgb, 255), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255))
        y += th + line_gap

    img.save(out_png, "PNG")

    # 改行品質の機械チェック
    break_issues = []
    if len(wrapped) >= 3:
        break_issues.append(f"3行以上（{len(wrapped)}行）になっています。1カット2行以内に収めてください")
    if len(wrapped) >= 2 and len(wrapped[-1]) <= 2:
        break_issues.append(f"最終行が孤立文字（'{wrapped[-1]}'）です。文節で改行位置を調整してください")
    for idx_l, ln in enumerate(wrapped):
        if idx_l > 0 and ln and ln[0] in KINSOKU_HEAD:
            break_issues.append(f"{idx_l+1}行目の先頭が禁則文字（'{ln[0]}'）です")

    return {
        "lines": wrapped,
        "max_width_px": max_measured_w,
        "y_start": pos_y,
        "y_end": y,
        "within_x180_900": max_measured_w <= max_width,
        "above_y1500": y <= 1500,
        "break_issues": break_issues,
    }


def escape_drawtext_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def measure_ebur128(mp4_path: str) -> dict:
    res = subprocess.run(
        ["ffmpeg", "-i", mp4_path, "-af", "ebur128=peak=true", "-f", "null", "-"],
        text=True,
        capture_output=True,
    )
    txt = res.stderr
    i_match = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", txt)
    p_match = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", txt)
    return {
        "integrated_lufs": float(i_match[-1]) if i_match else None,
        "true_peak_dbfs": float(p_match[-1]) if p_match else None,
    }


ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def validate_real_video_source(src: str, cid: int) -> None:
    """AI生成静止画スライドやffmpeg合成入力(lavfi等)の混入をコードレベルで拒否する"""
    if not src or src.startswith(("lavfi:", "color=", "testsrc", "smptebars")):
        raise ValueError(f"Cut {cid}: 合成・ダミー映像の生成は禁止されています（実写動画ファイルを指定してください）: {src}")
    if not os.path.isfile(src):
        raise ValueError(f"Cut {cid}: 実在する動画ファイルが見つかりません（勝手に生成せず依頼者へ不足素材を伝えてください）: {src}")
    ext = os.path.splitext(src)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTS:
        raise ValueError(
            f"Cut {cid}: 静止画や非動画ファイル（{ext}）は素材として禁止です。実写動画ファイル（{sorted(ALLOWED_VIDEO_EXTS)}）のみ使用してください。"
        )


def render(plan: dict, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    speed = float(plan.get("speed", 1.2))
    color_mode = plan.get("color_mode", "sdr").lower()
    voice = plan.get("voice", "ja-JP-NanamiNeural")
    title = re.sub(r"[^\w\-]+", "_", plan.get("title", "tiktok_output"))
    font_path = detect_jp_font(plan.get("font_path", ""))
    cuts = plan.get("cuts") or []
    if not cuts:
        raise ValueError("cuts が空です。")

    use_pil_overlay = HAS_PIL
    has_drawtext = ffmpeg_has_filter("drawtext")
    if not use_pil_overlay and not has_drawtext:
        raise RuntimeError(
            "テロップ描画手段がありません。pip install pillow を実行するか libfreetype 有効な ffmpeg を使ってください。"
        )

    with tempfile.TemporaryDirectory(prefix="tts_render_") as work:
        cut_metas = []
        total_pre_speed = 0.0
        for c in cuts:
            validate_real_video_source(str(c.get("source") or ""), c["id"])
            zoom = float(c.get("zoom", 1.0))
            slow = float(c.get("slow_pts", 1.0))
            if zoom > 2.0 + 1e-6:
                raise ValueError(f"Cut {c['id']}: zoom={zoom} は上限 2.0 倍を超えています。")
            if slow > 1.1 + 1e-6:
                raise ValueError(f"Cut {c['id']}: slow_pts={slow} は上限 1.1 倍を超えています。")
            wav = ensure_cut_audio(c, voice, work)
            dur = ffprobe_duration(wav)
            cut_metas.append({"cut": c, "wav": wav, "dur": dur, "start_timeline": total_pre_speed})
            total_pre_speed += dur

        est_final_sec = total_pre_speed / speed
        warnings = []
        if est_final_sec < 10.0:
            warnings.append(f"完成見込み尺 {est_final_sec:.2f}秒 が10秒未満です")

        clip_list_file = os.path.join(work, "clips.txt")
        audio_list_file = os.path.join(work, "audios.txt")
        fill_rgb = (191, 191, 191) if color_mode == "hlg" else (255, 255, 255)
        text_color_hex = "#BFBFBF" if color_mode == "hlg" else "#FFFFFF"
        telop_checks = []

        with open(clip_list_file, "w", encoding="utf-8") as cf, open(audio_list_file, "w", encoding="utf-8") as af:
            for meta in cut_metas:
                c = meta["cut"]
                cid = c["id"]
                dur = meta["dur"]
                zoom = float(c.get("zoom", 1.0))
                slow = float(c.get("slow_pts", 1.0))
                sw = int(1080 * zoom // 2) * 2
                sh = int(1920 * zoom // 2) * 2
                pos_y = int(c.get("telop_y", 1240))
                telop_text = (c.get("telop") or "").strip()

                base_vf = [
                    f"setpts={slow}*PTS",
                    "fps=30",
                    f"scale={sw}:{sh}:force_original_aspect_ratio=increase",
                    "crop=1080:1920",
                ]
                if color_mode == "hlg" and not c.get("source_is_hlg", False):
                    base_vf += [
                        "zscale=tin=bt709:pin=bt709:min=bt709:rin=limited:t=linear:p=bt2020",
                        "format=gbrpf32le",
                        "colorchannelmixer=rr=2.0:gg=2.0:bb=2.0",
                        "zscale=tin=linear:t=arib-std-b67:m=bt2020nc:r=limited",
                        "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc:range=tv",
                    ]

                clip_out = os.path.join(work, f"cut_{cid:02d}.mp4")
                v_enc = (
                    ["-c:v", "libx265", "-profile:v", "main10", "-pix_fmt", "yuv420p10le", "-crf", "18", "-tag:v", "hvc1",
                     "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-color_range", "tv"]
                    if color_mode == "hlg"
                    else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18"]
                )

                overlay_path = (c.get("overlay_path") or "").strip()
                has_overlay = bool(overlay_path and os.path.isfile(overlay_path))
                ov_x = int(c.get("overlay_x", 0))
                ov_y = int(c.get("overlay_y", 0))

                if (telop_text and use_pil_overlay) or has_overlay:
                    cmd = [
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", str(c.get("start_sec", 0.0)), "-t", f"{dur:.4f}", "-i", c["source"],
                    ]
                    fc_parts = [f"[0:v]{','.join(base_vf)}[bg]"]
                    cur_label = "[bg]"
                    next_idx = 1

                    # 編集用エフェクト・透過GIF/PNGオーバーレイ（実写ベース映像の上に乗せる用途のみ許可）
                    if has_overlay:
                        ov_ext = os.path.splitext(overlay_path)[1].lower()
                        if ov_ext == ".gif":
                            cmd += ["-ignore_loop", "0", "-t", f"{dur:.4f}", "-i", overlay_path]
                        elif ov_ext in {".png", ".webp"}:
                            cmd += ["-loop", "1", "-t", f"{dur:.4f}", "-i", overlay_path]
                        else:
                            cmd += ["-stream_loop", "-1", "-t", f"{dur:.4f}", "-i", overlay_path]
                        fc_parts.append(f"{cur_label}[{next_idx}:v]overlay={ov_x}:{ov_y}:shortest=1[ov{next_idx}]")
                        cur_label = f"[ov{next_idx}]"
                        next_idx += 1

                    if telop_text and use_pil_overlay:
                        png_path = os.path.join(work, f"telop_{cid:02d}.png")
                        t_info = render_telop_png(telop_text, font_path, png_path, pos_y=pos_y, fill_rgb=fill_rgb)
                        telop_checks.append({"cut": cid, **t_info})
                        if not t_info["above_y1500"]:
                            warnings.append(f"Cut {cid}: テロップ下端 y={t_info['y_end']} が y1500 を超えています")
                        for bi in t_info.get("break_issues", []):
                            warnings.append(f"Cut {cid}: {bi}")
                        cmd += ["-loop", "1", "-t", f"{dur:.4f}", "-i", png_path]
                        fc_parts.append(f"{cur_label}[{next_idx}:v]overlay=0:0:shortest=1[vout]")
                        cur_label = "[vout]"
                    elif telop_text and has_drawtext:
                        txt_file = os.path.join(work, f"telop_{cid:02d}.txt")
                        with open(txt_file, "w", encoding="utf-8") as tf:
                            tf.write(telop_text)
                        fc_parts.append(
                            f"{cur_label}drawtext=fontfile='{escape_drawtext_path(font_path)}':"
                            f"textfile='{escape_drawtext_path(txt_file)}':"
                            f"fontsize=68:fontcolor={text_color_hex}:borderw=8:bordercolor=black:"
                            f"shadowx=3:shadowy=3:line_spacing=12:x=(w-text_w)/2:y={pos_y}[vout]"
                        )
                        cur_label = "[vout]"

                    cmd += ["-filter_complex", ";".join(fc_parts), "-map", cur_label, "-t", f"{dur:.4f}", "-an", *v_enc, clip_out]
                else:
                    if telop_text and has_drawtext:
                        txt_file = os.path.join(work, f"telop_{cid:02d}.txt")
                        with open(txt_file, "w", encoding="utf-8") as tf:
                            tf.write(telop_text)
                        base_vf.append(
                            f"drawtext=fontfile='{escape_drawtext_path(font_path)}':"
                            f"textfile='{escape_drawtext_path(txt_file)}':"
                            f"fontsize=68:fontcolor={text_color_hex}:borderw=8:bordercolor=black:"
                            f"shadowx=3:shadowy=3:line_spacing=12:x=(w-text_w)/2:y={pos_y}"
                        )
                    cmd = [
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", str(c.get("start_sec", 0.0)), "-t", f"{dur:.4f}", "-i", c["source"],
                        "-vf", ",".join(base_vf), "-t", f"{dur:.4f}", "-an", *v_enc, clip_out,
                    ]

                run(cmd)
                cf.write(f"file '{clip_out}'\n")
                af.write(f"file '{meta['wav']}'\n")

        concat_vid = os.path.join(work, "concat_vid.mp4")
        concat_nar = os.path.join(work, "concat_nar.wav")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", clip_list_file, "-c", "copy", concat_vid])
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", audio_list_file, "-c:a", "pcm_f32le", concat_nar])

        sfx_entries = [m for m in cut_metas if m["cut"].get("sfx_path") and os.path.isfile(m["cut"]["sfx_path"])]
        if len(sfx_entries) > 6:
            warnings.append(f"効果音数が {len(sfx_entries)} か所です（目安4〜6か所）")

        mixed_wav = os.path.join(work, "mixed_sfx.wav")
        if sfx_entries:
            inputs = ["-i", concat_nar]
            fc = ["[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono[nar]"]
            mix_labels = ["[nar]"]
            for idx, m in enumerate(sfx_entries, start=1):
                inputs += ["-i", m["cut"]["sfx_path"]]
                delay_ms = int(round(m["start_timeline"] * 1000))
                gain_db = float(m["cut"].get("sfx_gain_db", -5.0))
                fc.append(
                    f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono,"
                    f"volume={gain_db}dB,adelay={delay_ms}|{delay_ms}[s{idx}]"
                )
                mix_labels.append(f"[s{idx}]")
            fc.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:normalize=0:duration=first[mix]")
            run(
                ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
                 "-map", "[mix]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_f32le", mixed_wav]
            )
        else:
            shutil.copyfile(concat_nar, mixed_wav)

        out_main = os.path.join(out_dir, f"{title}_main_sfx.mp4")
        out_nar = os.path.join(out_dir, f"{title}_nar_only.mp4")
        for wav_in, mp4_out in [(mixed_wav, out_main), (concat_nar, out_nar)]:
            v_enc = (
                ["-c:v", "libx265", "-profile:v", "main10", "-pix_fmt", "yuv420p10le", "-crf", "18", "-tag:v", "hvc1",
                 "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-color_range", "tv"]
                if color_mode == "hlg"
                else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18"]
            )
            run(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", concat_vid, "-i", wav_in,
                    "-filter_complex", f"[0:v]setpts=PTS/{speed},fps=30[v];[1:a]atempo={speed},alimiter=limit=0.84:attack=1:release=50[a]",
                    "-map", "[v]", "-map", "[a]", *v_enc,
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", mp4_out,
                ]
            )

        final_dur = ffprobe_duration(out_main)
        rows = max(3, int((final_dur + 4) // 5) + 1)
        contact_png = os.path.join(out_dir, f"{title}_contact_sheet.png")
        run(["ffmpeg", "-y", "-v", "error", "-i", out_main, "-vf", f"fps=1,scale=270:-1,tile=5x{rows}", "-frames:v", "1", contact_png])

        loud_main = measure_ebur128(out_main)
        loud_nar = measure_ebur128(out_nar)

        report = {
            "title": title,
            "telop_engine": "pillow_overlay" if use_pil_overlay else "ffmpeg_drawtext",
            "color_mode": color_mode,
            "font_used": font_path,
            "speed": speed,
            "final_duration_sec": round(final_dur, 2),
            "outputs": {
                "main_sfx_mp4": out_main,
                "nar_only_mp4": out_nar,
                "contact_sheet_png": contact_png,
            },
            "telop_checks": telop_checks,
            "loudness_main": loud_main,
            "loudness_nar_only": loud_nar,
            "sfx_count": len(sfx_entries),
            "warnings": warnings,
            "notes": "HLG書き出しの場合、コンタクトシートPNGはSDR表示のため実物より明るく見えることがあります。" if color_mode == "hlg" else "",
        }
        report_path = os.path.join(out_dir, f"{title}_inspect.json")
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(report, rf, ensure_ascii=False, indent=2)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok Shop OS JSON-driven video renderer")
    parser.add_argument("--plan", required=True, help="Path to plan.json")
    parser.add_argument("--out-dir", default="./output", help="Output directory")
    args = parser.parse_args()
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    rep = render(plan, args.out_dir)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
