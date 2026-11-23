#!/usr/bin/env bash
# TikTok Shop 制作ガイド：ローカル/VM環境の読み取り専用チェック（preflight）
# ffmpeg・Python・日本語フォント・補助ツールの有無を確認して一覧表示します。
set -euo pipefail

echo "=== 1. 基本コマンド確認 ==="
for cmd in python3 ffmpeg ffprobe curl; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[OK] $cmd -> $(command -v "$cmd")"
  else
    echo "[MISSING] $cmd"
  fi
done

echo ""
echo "=== 2. Pythonライブラリ・補助ツール確認 ==="
python3 -c "import PIL" 2>/dev/null && echo "[OK] pillow" || echo "[MISSING] pillow（透過PNGテロップ描画に使用）"
for pkg in edge-tts yt-dlp gdown; do
  if command -v "$pkg" >/dev/null 2>&1; then
    echo "[OK] $pkg"
  else
    echo "[MISSING] $pkg（必要な工程でのみ使用）"
  fi
done

echo ""
echo "=== 3. 日本語ゴシックフォント検出（テロップ文字化け防止） ==="
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
  echo "[OK] 日本語フォント: $FONT_FOUND"
else
  echo "[MISSING] 日本語フォント未検出（Noto Sans JP 等のフォントファイルを指定してください）"
fi

echo ""
echo "=== 環境チェック完了 ==="
