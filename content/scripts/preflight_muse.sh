#!/usr/bin/env bash
# TikTok Shop AI運用OS：Muse.ai (Linux VM) / ローカル環境 事前診断 & 自動セットアップ
# 初回起動時に1回だけ実行し、ffmpeg・日本語フォント・Pythonツール・作業フォルダを整えます。
set -euo pipefail

WORK_ROOT="${HOME}/workspace/tiktok-shop-ops"
mkdir -p "${WORK_ROOT}"/{assets,sfx,work,output,ledger}

echo "=== 1. 基本コマンド確認 ==="
for cmd in python3 ffmpeg ffprobe curl; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[OK] $cmd -> $(command -v "$cmd")"
  else
    echo "[MISSING] $cmd (インストールが必要)"
  fi
done

echo ""
echo "=== 2. Python補助ツール確認（edge-tts / yt-dlp / gdown） ==="
for pkg in edge-tts yt-dlp gdown; do
  if command -v "$pkg" >/dev/null 2>&1; then
    echo "[OK] $pkg"
  else
    echo "[INFO] $pkg 未導入。pip 導入を試みます..."
    python3 -m pip install --user --quiet "$pkg" 2>/dev/null && echo "[INSTALLED] $pkg" || echo "[WARN] $pkg の自動導入に失敗（オフラインまたは権限制限）"
  fi
done

echo ""
echo "=== 3. 日本語ゴシックフォント検出（テロップ豆腐文字防止） ==="
FONT_FOUND=""
for candidate in \
  "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" \
  "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc" \
  "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" \
  "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf" \
  "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf" \
  "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc" \
  "/System/Library/Fonts/Hiragino Sans GB.ttc" \
  "/Library/Fonts/NotoSansJP-Bold.ttf"; do
  if [ -f "$candidate" ]; then
    FONT_FOUND="$candidate"
    break
  fi
done

if [ -z "$FONT_FOUND" ] && command -v fc-list >/dev/null 2>&1; then
  FONT_FOUND=$(fc-list :lang=ja file | head -n 1 | cut -d: -f1 | tr -d ' ' || true)
fi

if [ -n "$FONT_FOUND" ]; then
  echo "[OK] 日本語フォント検出: $FONT_FOUND"
else
  echo "[MISSING] 日本語フォントが見つかりません！"
  echo "  Ubuntu/Debian なら: sudo apt-get update && sudo apt-get install -y fonts-noto-cjk"
  echo "  または Google Fonts から NotoSansJP-Bold.ttf を ${WORK_ROOT}/NotoSansJP-Bold.ttf へ配置してください。"
fi

echo ""
echo "=== 4. 初期設定ファイル生成 ==="
CFG="${WORK_ROOT}/config.json"
if [ ! -f "$CFG" ]; then
  cat > "$CFG" <<EOF
{
  "work_root": "${WORK_ROOT}",
  "jp_font_path": "${FONT_FOUND}",
  "tiktok_handle": "",
  "drive_folder_ref": "",
  "voice": "ja-JP-NanamiNeural",
  "speed": 1.2,
  "target_lufs": -14.0
}
EOF
  echo "[CREATED] $CFG"
else
  echo "[EXISTS] $CFG（既存設定を保持）"
fi

echo ""
echo "=== 診断完了 ==="
