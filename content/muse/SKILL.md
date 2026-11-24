---
name: tiktok-shop-os
description: TikTok Shop向けショート動画の商材リサーチ、企画発散、1.5秒ビートシート、口語台本、品質レビュー、動画編集、投稿後の48h振り返りを一貫して進めるための運用ガイド。
compatibility: Meta Muse / GrokBot / Claude / Codex. Python 3.10+, ffmpeg recommended.
metadata:
  version: "2.3"
  guide_url: "https://fukushima-cyber.github.io/tiktok-shop-ai-os/llms.txt"
---

# TikTok Shop 制作運用ガイド（エージェント設定リファレンス）

ユーザーがローカル環境やカスタムスキルとしてこの制作フローを運用する際の推奨設定と、環境ごとの注意点をまとめています。

---

## 1. 推奨する初期設定（ユーザーの依頼に応じて構成）

1. **作業フォルダ構成（任意の作業ディレクトリ配下）**：
   - `brief/`（`research_brief.md`・`asset_inventory.md`）、`assets/`（素材一時保存）、`sfx/`（効果音）、`work/`（中間ファイル）、`output/`（完成mp4・コンタクトシート）、`ledger/`（アカウント実績・ローカル型記録）
2. **環境確認（`scripts/preflight_muse.sh`）**：
   - `ffmpeg` / `ffprobe` / `python3` / `pillow` / `edge-tts` / 日本語ゴシックフォントの有無を事前に確認します。
   - 日本語フォントが未導入の環境ではテロップが文字化けするため、利用可能な日本語ゴシックフォントのパスを控えておきます。
3. **共有Google Driveと素材管理**：
   - デフォルトの共有素材置き場は Google Drive「TTSオートフロー」（`https://drive.google.com/drive/folders/1OPd1eGR5EpWh3-QVqDrG1W86MjlGoMuW`）です。
   - まず `素材一覧_全商品.md`（`https://drive.google.com/uc?export=download&id=1ypjOJlJQbRdsYdpx1JzLuTinDahbXFbI`）とDrive内の対象商材フォルダを確認します。
   - 共有フォルダ内のファイル移動・削除・共有設定変更は、依頼者の明示的な承認なしに行いません。
   - Google Drive Connector が連携されている環境では、大容量動画の読み書きや完成mp4の共有にコネクタを使うと安定します。
4. **効果音の扱い**：
   - 効果音ラボの標準7種（`core/00-os-principles.md` 参照）を使用する場合は、ローカル作業フォルダの `sfx/` に保存して再利用します（再配布は不可）。外部サイトから直接取得できない環境では、依頼者にGoogle Driveの `sfx` フォルダへ配置してもらいます。

---

## 2. 運用上の注意点と代替手段

### ベース映像の素材ポリシー
- **ベース映像は実写のみ**：AI動画生成、AI画像生成のスライド動画化、単色背景や仮画面での実写カット代用は行いません。
- **編集エフェクト・GIFオーバーレイは可**：実写ベース映像の上に乗せる左下白矢印の動くGIF、コメント吹き出し、控えめな強調演出の作成・合成は可能です（赤矢印連打・白フラッシュ・色加工・左右反転は不可）。
- **実写素材が不足する場合**：①共有Google Drive内の別実写カット・別区間 → ②公開実写フリー素材（Pexels / Mixkit）→ ③編集を止めて依頼者へ不足カットの追加を相談します。

### 外部サイト・ツール制限時の代替手順

| 状況 | 避けること | 推奨する代替手順 |
|---|---|---|
| **外部動画サイトが開けない・取得制限がある** | 認証情報の不正利用やアクセス制限の回避、AI映像での代用 | Google Drive内素材または実写フリー素材（Pexels / Mixkit）を使い、不足分は依頼者へ共有を依頼する。 |
| **公開データからアカウント数値が取得できない** | 再生数やいいね数を推測で記入する | 依頼者へTikTokインサイトやTikTok Shop管理画面のスクリーンショット共有を依頼し、画像から読み取って記録する。 |
| **指定の音声合成ツールが使えない** | 無音のまま納品する、別言語の音声へ勝手に切り替える | 状況をそのまま報告し、代替音声またはナレーション提供を相談する。 |
| **完成動画の容量が大きくチャット送信できない** | ローカルに置いたまま終了する | Google Drive等の共有先へ保存し、確認用リンクとコンタクトシート画像を添えて渡す。 |
| **ffmpegのコマンド引数で日本語や記号エラーが出る** | 長大なワンライナーを手組みする | `scripts/render_video.py` に `plan.json` を渡して実行する（Pillow透過PNG合成により `drawtext` 不在環境や記号でも安定動作）。 |

---

## 3. 各工程の参照先（ベースURL：`https://fukushima-cyber.github.io/tiktok-shop-ai-os/`）

1. 共通ガイド：`core/00-os-principles.md` ＋ 共有素材案内：`cases/assets-index.md`
2. 商材リサーチ：`skills/01-onboarding.md`
3. 企画発散・選別（ゲートA）：`skills/02-planning.md` ＋ 型インデックス：`index/patterns.md`
4. 1.5秒ビートシート：`skills/03-beat-sheet.md`
5. 口語台本・読み上げ：`skills/04-script-tts.md`
6. 独立レビュー（ゲートB）：`skills/05-red-team.md`
7. 素材検品・編集・検査（ゲートC）：`skills/06-editing.md` ＋ `scripts/render_video.py`
8. 投稿準備・48h振り返り：`skills/07-post-pdca.md` ＋ `scripts/account_tracker_ref.py`
