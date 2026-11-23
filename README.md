# TikTok Shop アフィリエイト AI運用OS

Muse / GrokBot / Claude / ChatGPT などのAIエージェントに、TikTok Shopアフィリエイトの **案件オンボーディング → 企画発散 → 1.5秒ビートシート → 口語台本＆TTS → 独立レッドチーム審査 → 自動編集＆検査 → 投稿＆48h PDCA** まで一貫して任せるための運用OSサイトです。

## AIへの渡し方
AIには公開URLの `/llms.txt` だけを渡します。プレーンテキストのため、Notion公開ページのJS描画・文字切れ・DB非表示の制約なしに、必要なSkillと型だけオンデマンドで読み込めます。

## ローカルビルド・確認
```bash
npm run build
npm run serve
```

## ディレクトリ構成
- `content/llms.txt` : AIが最初に読む唯一の入口（30行ルーター）
- `content/core/00-os-principles.md` : 全工程共通の定数OS（伸びる原理8つ・3段階CV評価軸・薬機法）
- `content/skills/01〜07.md` : 工程別の7 Skill
- `content/index/patterns.md` : 企画21型×台本20型×カームセブン5型の1枚軽量インデックス
- `content/patterns/S01〜S20.md` : 個別台本型の詳細
- `content/cases/` : センスウェア・カームセブン・`@iinioisuki`・共有素材案内
- `content/templates/` : 第三者・新商材持ち込み用の変数A/B/Cテンプレート
- `content/scripts/edit_pipeline_ref.sh` : ffmpeg編集・HLG変換・音量測定・コンタクトシート生成コマンド集
- `dist/` : 静的サイト出力一式（GitHub Pages / Cloudflare Pages対応）
