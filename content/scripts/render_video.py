#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：Muse.ai / GrokBot 向け JSON駆動 本番動画レンダリングエンジン（Skill 06）

ffmpeg の長大なコマンド文字列をAIが手組みして記号・改行・色空間・音量で失敗する事故を防ぐため、
ビートシート＋台本JSON（plan.json）から以下を一発で自動実行します。
  1. 日本語フォント自動検出（豆腐文字防止）
  2. カット切り出し・2.0倍以内寄せクロップ・1.1倍以内スロー・SDR/HLG色空間統一（色加工・反転なし）
  3. textfile= 方式によるフレーム厳密テロップ焼き込み（記号・改行でのクラッシュ根絶）
  4. 音声（TTS生成済みWAVまたは自動edge-tts）＋効果音32bit線形ミックス
  5. 全体1.2倍速で「本線mp4（効果音あり）」と「ナレのみmp4」の2本書き出し
  6. 1秒コンタクトシートPNG・ebur128音量測定・完成尺/解像度チェックレポートJSON出力

使い方:
  python3 render_video.py --plan ./plan.json --out-dir ./output

plan.json の最小構造:
{
  "title": "sample_cut",
  "color_mode": "sdr",           # "sdr" or "hlg"（自社素材がHDR HLGなら "hlg"）
  "speed": 1.2,                  # 仕上げ全体倍速（標準1.2）
  "voice": "ja-JP-NanamiNeural",
  "font_path": "",               # 空なら日本語フォントを自動検出
  "cuts": [
    {
      "id": 1,
      "source": "/path/to/clip1.mp4",
      "source_is_hlg": false,
      "start_sec": 0.5,
      "zoom": 1.0,               # 上限 2.0
      "slow_pts": 1.0,           # 上限 1.1（口元・手の動きには使わない）
      "telop": "練り香水、男が買って\\n後悔するところ3つ。",
      "reading": "ねりこうすい、おとこが かってこうかい するところ みっつ",
      "audio_wav": "",           # 既存WAVがあれば指定。空なら edge-tts で自動生成
      "telop_y": 1240,           # 有機: <1500 / 広告安全領域: 240..1260
      "sfx_path": "",            # 効果音WAV/MP3（任意・要所4〜6か所のみ）
      "sfx_gain_db": -5.0        # ナレより3〜6dB低く
    }
  ]
}
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

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
    # 前後の無音を詰める（1.0x標準速のまま）
    run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", tmp_mp3,
            "-af", "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_f32le", out_wav,
        ]
    )
    return out_wav


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

    with tempfile.TemporaryDirectory(prefix="tts_render_") as work:
        # 1) 全カットのナレ音声を先に生成し、実測尺を確定
        cut_metas = []
        total_pre_speed = 0.0
        for c in cuts:
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
        if est_final_sec > 25.5:
            warnings.append(f"完成見込み尺 {est_final_sec:.2f}秒 が上限25秒を超過しています（台本削減推奨）")
        elif est_final_sec < 14.5:
            warnings.append(f"完成見込み尺 {est_final_sec:.2f}秒 が目安15秒未満です")

        # 2) 各カットの映像切り出し＋寄せ＋色統一＋フレーム厳密テロップ
        clip_list_file = os.path.join(work, "clips.txt")
        audio_list_file = os.path.join(work, "audios.txt")
        text_color = "#BFBFBF" if color_mode == "hlg" else "#FFFFFF"

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

                # textfile 書き出し（記号・改行・クォート安全）
                txt_file = os.path.join(work, f"telop_{cid:02d}.txt")
                with open(txt_file, "w", encoding="utf-8") as tf:
                    tf.write((c.get("telop") or "").strip())

                vf_parts = [
                    f"setpts={slow}*PTS",
                    "fps=30",
                    f"scale={sw}:{sh}:force_original_aspect_ratio=increase",
                    "crop=1080:1920",
                ]
                if color_mode == "hlg" and not c.get("source_is_hlg", False):
                    vf_parts += [
                        "zscale=tin=bt709:pin=bt709:min=bt709:rin=limited:t=linear:p=bt2020",
                        "format=gbrpf32le",
                        "colorchannelmixer=rr=2.0:gg=2.0:bb=2.0",
                        "zscale=tin=linear:t=arib-std-b67:m=bt2020nc:r=limited",
                        "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc:range=tv",
                    ]
                if (c.get("telop") or "").strip():
                    vf_parts.append(
                        f"drawtext=fontfile='{escape_drawtext_path(font_path)}':"
                        f"textfile='{escape_drawtext_path(txt_file)}':"
                        f"fontsize=68:fontcolor={text_color}:borderw=8:bordercolor=black:"
                        f"shadowx=3:shadowy=3:line_spacing=12:x=(w-text_w)/2:y={pos_y}"
                    )

                clip_out = os.path.join(work, f"cut_{cid:02d}.mp4")
                cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", str(c.get("start_sec", 0.0)),
                    "-t", f"{dur:.4f}",
                    "-i", c["source"],
                    "-vf", ",".join(vf_parts),
                    "-t", f"{dur:.4f}",
                    "-an",
                ]
                if color_mode == "hlg":
                    cmd += [
                        "-c:v", "libx265", "-profile:v", "main10", "-pix_fmt", "yuv420p10le",
                        "-crf", "18", "-tag:v", "hvc1",
                        "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                        "-colorspace", "bt2020nc", "-color_range", "tv",
                    ]
                else:
                    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18"]
                cmd.append(clip_out)
                run(cmd)
                cf.write(f"file '{clip_out}'\n")
                af.write(f"file '{meta['wav']}'\n")

        # 3) 映像連結 & ナレ連結
        concat_vid = os.path.join(work, "concat_vid.mp4")
        concat_nar = os.path.join(work, "concat_nar.wav")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", clip_list_file, "-c", "copy", concat_vid])
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", audio_list_file, "-c:a", "pcm_f32le", concat_nar])

        # 4) 効果音 32bit線形ミックス（指定がある場合のみ）
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

        # 5) 全体倍速で2本書き出し（本線＋ナレのみ）
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

        # 6) コンタクトシート＆機械検査レポート
        contact_png = os.path.join(out_dir, f"{title}_contact_sheet.png")
        run(["ffmpeg", "-y", "-v", "error", "-i", out_main, "-vf", "fps=1,scale=270:-1,tile=5x5", "-frames:v", "1", contact_png])

        final_dur = ffprobe_duration(out_main)
        loud_main = measure_ebur128(out_main)
        loud_nar = measure_ebur128(out_nar)

        report = {
            "title": title,
            "color_mode": color_mode,
            "font_used": font_path,
            "speed": speed,
            "final_duration_sec": round(final_dur, 2),
            "duration_ok_15_25": 15.0 <= final_dur <= 25.0,
            "outputs": {
                "main_sfx_mp4": out_main,
                "nar_only_mp4": out_nar,
                "contact_sheet_png": contact_png,
            },
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
