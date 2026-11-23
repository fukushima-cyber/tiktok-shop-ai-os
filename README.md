# TikTok Shop アフィリエイト AI運用OS

Muse / GrokBot / Claude / ChatGPT などのAIエージェントに、**URLを1行貼るだけで** TikTok Shopアフィリエイトの企画・台本・編集・48h PDCAまで一貫して任せるための運用OSサイトです。

## 使い方（人間がやることは1行貼るだけ）
AIに次の1文を貼るだけで、自律起動プロトコルに沿って自動で進行します。
```text
https://fukushima-cyber.github.io/tiktok-shop-ai-os/llms.txt を読んで、このOSどおりに進めてください。
```

## ローカルビルド・確認
```bash
npm run build
npm run serve
```

## ディレクトリ構成
- `content/llms.txt` : AIが最初に読む唯一の入口（自律起動プロトコル＋ルーター）
- `content/core/00-os-principles.md` : 全工程共通の定数OS＆編集標準プリセット
- `content/skills/01〜07.md` : 工程別の7 Skill
- `content/index/patterns.md` : 企画21型×台本20型×カームセブン固有型の1枚軽量インデックス
- `content/patterns/S01〜S20.md` : 個別台本型の詳細
- `content/cases/` : 実例リファレンス（練り香水・美容液のリサーチ/お手本台本/素材管理の見本）
- `content/templates/` : 別商材・上書き設定用の任意テンプレート
- `content/scripts/edit_pipeline_ref.sh` : Google Drive/RED素材収集・自動検品・カット・寄せ・テロップ・1.2x・音量検査コマンド集
- `content/scripts/account_tracker_ref.py` : 自アカウントの公開投稿自動集計・24h/48hスナップ・3段階PDCA台帳スクリプト
