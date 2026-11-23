#!/usr/bin/env bash
# TikTok Shop AI運用OS：素材収集・カット・編集・音声ミックス・検査 フルリファレンス（Skill 06 準拠）
# すべてのコマンドはローカル/仮想環境でそのまま参照・応用できる標準形です。
# ※ログイン不要の公開URL・自身のGoogle Drive素材のみを対象とします。
set -euo pipefail

# ==============================================================================
# 0. 素材収集：Google Drive（単体ファイル / 共有フォルダ）＆ 公開RED動画
# ==============================================================================

# 0-a. Google Drive 単体ファイル直接DL（ファイルID指定）
download_gdrive_file() {
  local file_id="$1"
  local out_path="$2"
  curl -fsSL "https://drive.google.com/uc?export=download&id=${file_id}" -o "$out_path"
}

# 0-b. Google Drive 共有フォルダ丸ごとDL（gdown利用）
download_gdrive_folder() {
  local folder_url="$1"
  local out_dir="$2"
  mkdir -p "$out_dir"
  gdown --folder "$folder_url" -O "$out_dir" --remaining-ok
}

# 0-c. 公開動画ページから動画のみ取得（認証不要の公開ページのみ）
download_public_video() {
  local public_url="$1"
  local out_template="$2" # 例: ./raw_red/%(id)s.%(ext)s
  yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mp4 -o "$out_template" "$public_url"
}

# 0-d. 取得した全素材の自動検品（ffprobe仕様一覧 + 頭・中・終わりの3フレーム抽出）
inspect_assets_dir() {
  local src_dir="$1"
  local out_dir="$2"
  mkdir -p "$out_dir"
  echo "| ファイル名 | 尺(秒) | 解像度 | fps | 色空間(trc/primaries) | 音声 |" > "$out_dir/asset_probe.md"
  echo "|---|---:|---|---:|---|---|" >> "$out_dir/asset_probe.md"
  find "$src_dir" -maxdepth 2 -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" \) | sort | while read -r f; do
    local base; base="$(basename "$f")"
    local dur w h fps trc pri a_cnt
    dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" | awk '{printf "%.2f", $1}')
    w=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 "$f")
    h=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 "$f")
    fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 "$f")
    trc=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of default=nw=1:nk=1 "$f" || echo "unknown")
    pri=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_primaries -of default=nw=1:nk=1 "$f" || echo "unknown")
    a_cnt=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$f" | wc -l | tr -d ' ')
    echo "| \`${base}\` | ${dur} | ${w}x${h} | ${fps} | ${trc:-sdr}/${pri:-bt709} | $([ "$a_cnt" -gt 0 ] && echo あり || echo なし) |" >> "$out_dir/asset_probe.md"

    # 頭(10%)・中(50%)・終わり(90%)の3枚を横に並べて中身・顔・透かしを目視確認
    local t1 t2 t3
    t1=$(awk -v d="$dur" 'BEGIN{printf "%.2f", d*0.10}')
    t2=$(awk -v d="$dur" 'BEGIN{printf "%.2f", d*0.50}')
    t3=$(awk -v d="$dur" 'BEGIN{printf "%.2f", d*0.90}')
    ffmpeg -y -v error \
      -ss "$t1" -i "$f" -ss "$t2" -i "$f" -ss "$t3" -i "$f" \
      -filter_complex "[0:v]scale=270:-1[a];[1:v]scale=270:-1[b];[2:v]scale=270:-1[c];[a][b][c]hstack=inputs=3" \
      -frames:v 1 "$out_dir/${base}.preview.jpg" || true
  done
  echo "Inspect done: $out_dir/asset_probe.md"
}

# ==============================================================================
# 1. カット切り出し＆寄せクロップ（2.0倍以内・反転なし・色加工なし）
#    zoom=1.0〜2.0, offset_x/offset_y で顔・透かし・元字幕を画面外へ出す
#    target_mode: "sdr"（全SDR統一時）または "hlg"（HLG自社素材に揃える時）
# ==============================================================================
cut_and_prep_clip() {
  local in_file="$1"
  local start_sec="$2"
  local dur_sec="$3"
  local zoom="${4:-1.0}"          # 上限 2.0
  local slow_pts="${5:-1.0}"      # 尺不足時のみ上限 1.1（口元・手の動きには使わない）
  local target_mode="${6:-sdr}"   # "sdr" or "hlg"
  local out_file="$7"

  # zoom に応じて 1080x1920 へ拡大後クロップ（左右反転は絶対にしない）
  local sw sh
  sw=$(awk -v z="$zoom" 'BEGIN{printf "%d", int(1080*z/2)*2}')
  sh=$(awk -v z="$zoom" 'BEGIN{printf "%d", int(1920*z/2)*2}')
  local vf="setpts=${slow_pts}*PTS,fps=30,scale=${sw}:${sh}:force_original_aspect_ratio=increase,crop=1080:1920"

  if [ "$target_mode" = "hlg" ]; then
    # SDR(BT.709) -> HDR HLG(BT.2020) 検証済み変換式（白信号約75%基準）
    vf="${vf},zscale=tin=bt709:pin=bt709:min=bt709:rin=limited:t=linear:p=bt2020,format=gbrpf32le,colorchannelmixer=rr=2.0:gg=2.0:bb=2.0,zscale=tin=linear:t=arib-std-b67:m=bt2020nc:r=limited,setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc:range=tv,format=yuv420p10le"
    ffmpeg -y -v error -ss "$start_sec" -t "$dur_sec" -i "$in_file" -vf "$vf" \
      -c:v libx265 -profile:v main10 -pix_fmt yuv420p10le -crf 18 -tag:v hvc1 \
      -color_primaries bt2020 -color_trc arib-std-b67 -colorspace bt2020nc -color_range tv \
      -an "$out_file"
  else
    ffmpeg -y -v error -ss "$start_sec" -t "$dur_sec" -i "$in_file" -vf "${vf},format=yuv420p" \
      -c:v libx264 -pix_fmt yuv420p -crf 18 -an "$out_file"
  fi
}

# ==============================================================================
# 2. カット連結（隙間・無音・静止フレームゼロ）
# ==============================================================================
concat_clips() {
  local list_txt="$1" # 各行: file '/abs/path/cut01.mp4'
  local out_mp4="$2"
  ffmpeg -y -v error -f concat -safe 0 -i "$list_txt" -c copy "$out_mp4"
}

# ==============================================================================
# 3. TTS音声生成（標準速 1.0x・前後無音カット）
# ==============================================================================
generate_tts() {
  local text="$1"
  local out_wav="$2"
  local voice="${3:-ja-JP-NanamiNeural}"
  edge-tts --voice "$voice" --text "$text" --write-media "${out_wav}.mp3"
  ffmpeg -y -v error -i "${out_wav}.mp3" \
    -af "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,areverse" \
    -ar 48000 -ac 1 -c:a pcm_f32le "$out_wav"
  rm -f "${out_wav}.mp3"
}

# ==============================================================================
# 4. テロップ焼き込み（フレーム番号指定・白RGB191・黒縁・中央ぞろえ）
#    ※HLG書き出し時は白を #BFBFBF (RGB 191 = 信号約75%) に合わせて白飛び防止
# ==============================================================================
burn_telop_frame_exact() {
  local in_mp4="$1"
  local font_path="$2"    # 例: /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
  local text="$3"         # 改行は \n で事前に折り返す（小さくせず改行）
  local start_frame="$4"
  local end_frame="$5"
  local pos_y="${6:-1280}" # 有機: <1500 / 広告安全領域: 240〜1260
  local color_hex="${7:-#BFBFBF}" # HLG基準白=#BFBFBF / SDR=#FFFFFF
  local out_mp4="$8"

  ffmpeg -y -v error -i "$in_mp4" \
    -vf "drawtext=fontfile='${font_path}':text='${text}':fontsize=68:fontcolor=${color_hex}:borderw=8:bordercolor=black:shadowx=3:shadowy=3:x=(w-text_w)/2:y=${pos_y}:enable='between(n\,${start_frame}\,${end_frame})'" \
    -c:v libx264 -crf 18 -c:a copy "$out_mp4"
}

# ==============================================================================
# 5. ナレ＋効果音の32bit線形ミックス＆全体1.2倍速仕上げ（本線＋ナレのみ2本生成）
#    - 強いloudnormでナレを潰さず、線形ゲイン＋最終速いピークリミッター(-1.5dB)のみ
#    - 効果音ピークはナレより 3〜6dB 低くする
# ==============================================================================
finalize_speed_120() {
  local in_video="$1"
  local in_audio_wav="$2"
  local out_mp4="$3"
  local speed="${4:-1.2}"
  ffmpeg -y -v error -i "$in_video" -i "$in_audio_wav" \
    -filter_complex "[0:v]setpts=PTS/${speed},fps=30[v];[1:a]atempo=${speed},alimiter=limit=0.84:attack=1:release=50[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 \
    -c:a aac -b:a 192k -movflags +faststart "$out_mp4"
}

# ==============================================================================
# 6. 機械検査（音量 -14LUFS / ピーク <= -1dBFS / コンタクトシート / 尺）
# ==============================================================================
measure_loudness() {
  local target="$1"
  ffmpeg -i "$target" -af "ebur128=peak=true" -f null - 2>&1 | tail -n 15
}

make_contact_sheet() {
  local in_mp4="$1"
  local out_png="$2"
  ffmpeg -y -v error -i "$in_mp4" \
    -vf "fps=1,scale=270:-1,tile=5x5" \
    -frames:v 1 "$out_png"
}

echo "Loaded edit_pipeline_ref.sh helper functions."
