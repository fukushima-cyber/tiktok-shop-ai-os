#!/usr/bin/env bash
# TikTok Shop AI運用OS：編集パイプライン・リファレンスコマンド集（Skill 06 準拠）
# 実際のカット番号・区間・ファイル名に合わせてAIまたはスクリプトから呼び出してください。
set -euo pipefail

# ==============================================================================
# 1. SDR (BT.709) -> HDR HLG (BT.2020) 色空間変換（色補正・LUT・反転は一切しない）
#    白い画面の信号が BT.2408 基準白（約75%）に揃う検証済み式
# ==============================================================================
convert_sdr_to_hlg() {
  local in_file="$1"
  local out_file="$2"
  ffmpeg -y -i "$in_file" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,zscale=tin=bt709:pin=bt709:min=bt709:rin=limited:t=linear:p=bt2020,format=gbrpf32le,colorchannelmixer=rr=2.0:gg=2.0:bb=2.0,zscale=tin=linear:t=arib-std-b67:m=bt2020nc:r=limited,setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc:range=tv,format=yuv420p10le" \
    -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le -crf 18 -tag:v hvc1 \
    -color_primaries bt2020 -color_trc arib-std-b67 -colorspace bt2020nc -color_range tv \
    -an "$out_file"
}

# ==============================================================================
# 2. TTS音声生成（標準速 1.0x で生成し、無音トリムする）
# ==============================================================================
generate_tts() {
  local text="$1"
  local out_wav="$2"
  local voice="${3:-ja-JP-NanamiNeural}"
  edge-tts --voice "$voice" --text "$text" --write-media "${out_wav}.mp3"
  ffmpeg -y -i "${out_wav}.mp3" \
    -af "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse" \
    -ar 48000 -ac 1 -c:a pcm_f32le "$out_wav"
  rm -f "${out_wav}.mp3"
}

# ==============================================================================
# 3. 全体1.2倍速仕上げ（映像＋音声まとめて適用。二重倍速にしないこと）
# ==============================================================================
apply_speed_120() {
  local in_video="$1"
  local in_audio="$2"
  local out_mp4="$3"
  ffmpeg -y -i "$in_video" -i "$in_audio" \
    -filter_complex "[0:v]setpts=PTS/1.2,fps=30[v];[1:a]atempo=1.2,alimiter=limit=0.84:attack=1:release=50[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le -crf 18 -tag:v hvc1 \
    -color_primaries bt2020 -color_trc arib-std-b67 -colorspace bt2020nc -color_range tv \
    -c:a aac -b:a 192k -movflags +faststart "$out_mp4"
}

# ==============================================================================
# 4. 音量・ピーク実測チェック（-14 LUFS 付近 / True Peak <= -1.0 dBFS）
# ==============================================================================
measure_loudness() {
  local target="$1"
  ffmpeg -i "$target" -af "ebur128=peak=true" -f null - 2>&1 | tail -n 15
}

# ==============================================================================
# 5. コンタクトシート生成（1秒ごとの一覧画像。ゲートC検査用）
#    ※HDRソースをSDR PNGへ落とすため、notesに「実物のHDRより明るく見える」旨を明記
# ==============================================================================
make_contact_sheet() {
  local in_mp4="$1"
  local out_png="$2"
  ffmpeg -y -i "$in_mp4" \
    -vf "fps=1,scale=270:-1,tile=5x5" \
    -frames:v 1 "$out_png"
}

echo "Loaded edit_pipeline_ref.sh helper functions."
