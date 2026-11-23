---
name: tiktok-shop-os
description: TikTok Shopアフィリエイトの自アカウント自動集計・商材/競合リサーチ・企画発散・1.5秒ビートシート・口語台本・独立レッドチーム審査・Google Drive/RED素材収集・ffmpeg自動編集・48h PDCAを一貫実行する運用OS。TikTok動画制作、商材リサーチ、台本作成、動画編集、アカウント数値集計やPDCAの依頼時に起動する。
compatibility: Meta Muse (Secure Linux VM) / GrokBot / Claude / Codex. Python 3.10+, ffmpeg recommended.
metadata:
  version: "2.1"
  os_url: "https://fukushima-cyber.github.io/tiktok-shop-ai-os/llms.txt"
---

# TikTok Shop AI運用OS（Muse.ai ネイティブ統合スキル）

このファイルは **Meta Muse (`muse.ai`) のカスタムスキル領域（`~/workspace/custom-skills/tiktok-shop-os/SKILL.md`）** にそのまま配置して永続運用するための本体定義です。

---

## 1. 初回セットアップ（Muse VMに1回だけ実行）

ユーザーが初めてこのOSを渡したとき、次の4ステップを自動で実行して永続環境を作ります。2回目以降はURLを貼られなくても記憶とローカル環境から即座に動きます。

1. **ローカル作業フォルダとスキル配置**：
   - 作業ディレクトリ：`~/workspace/tiktok-shop-ops/`（配下に `assets/`, `sfx/`, `work/`, `output/`, `ledger/` を作成）
   - この `SKILL.md` と補助スクリプト（`preflight_muse.sh`, `render_video.py`, `account_tracker_ref.py`）を `~/workspace/custom-skills/tiktok-shop-os/` へ保存。
2. **環境チェック & 自動修復（`preflight_muse.sh`）**：
   - `ffmpeg` / `ffprobe` / `python3` / 日本語ゴシックフォント（`Noto Sans CJK` 等） / `edge-tts` / `yt-dlp` / `gdown` の有無を確認し、不足ツールを導入する。
   - **重要**：日本語フォントがないまま `ffmpeg` でテロップを焼くと文字化け（豆腐文字）になるため、必ず有効な日本語フォントパスを `config.json` に記録する。
3. **Google Drive & 効果音キャッシュの準備**：
   - Museの **Google Drive Connector** が接続済みか確認する（大容量動画はチャット添付より Google Drive Connector 経由の読み書きが安定）。未接続なら「共有リンク（`gdown` / `uc?export=download`）」で代替する。
   - 効果音ラボの標準7種は、毎回DLし直さず初回に `~/workspace/tiktok-shop-ops/sfx/` へキャッシュする（再配布禁止・自分のVM内利用のみ）。もしSentinelプロキシ等で取得できない場合は、依頼者に効果音ラボの7曲URLを提示してGoogle Driveの `sfx` フォルダへ置いてもらう。
4. **ユーザー設定の永続化（`~/workspace/tiktok-shop-ops/config.json`）**：
   - ユーザーに聞くのは最小限（未指定ならスキップ可）：
     - 運用するTikTokアカウント（`@handle`）
     - 素材置き場（Google Driveフォルダ名／URL）
     - 毎日定時の48h自動集計・PDCA通知をオンにするか
   - 決定した内容と「投稿・広告・外部送信・購入は必ず事前承認を取る」ルールを永続メモリに保存する。

---

## 2. Muse 特有のつまづき対策（暴走防止 & フォールバック規約）

### 最重要ルール：ベース映像のAI生成は完全禁止 ／ 編集エフェクト・GIFオーバーレイはOK
- **完全禁止（ベース映像の自作）**：AI動画生成ツール、AI画像生成（＋ズーム/パンのスライド動画化）、単色背景・仮画面で「実写カットの代わり」を自作すること。不足カットをMuseが生成で埋めると低品質動画が量産されるため厳禁。
- **許可（編集演出・オーバーレイ）**：実写ベース映像の上に乗せる **編集エフェクト・透過GIF/PNGアニメーション（左下白矢印、コメント吹き出し、強調ハイライト等）の作成と合成はOK**（ただし禁止演出の赤矢印連打・白フラッシュ・色加工・左右反転はNG）。
- **実写素材が足りないときの唯一の正解**：①ユーザーのGoogle Drive内の別実写カット／別区間 → ②実写の公開REDまたはPexels/Mixkitフリー素材 → ③それでも足りない場合は **編集を止め、「不足している具体的なカット内容（例：塗布シーン2秒）」を依頼者へ伝えてDriveへ追加してもらう**。

Muse は専用Linux VM＋Sentinelネットワーク監視（データセンターIP）で動くため、外部サイトアクセスや動画処理で特有の詰まりが起きます。以下を厳守します。

| 起きやすい詰まり | 絶対NG | 正しいフォールバック手順 |
|---|---|---|
| **使いたいシーンの映像素材が足りない** | **AI動画/画像生成やプログラム描画で仮素材を自作して埋める** | ①Drive内実写の別区間 → ②実写フリー素材（Pexels/Mixkit）→ ③編集を止めて依頼者へ不足カットの追加を依頼。 |
| **RED（小紅書）やTikTokがCAPTCHA / 403ブロックになる** | Cookie偽装・CAPTCHA突破・ログイン突破・AI生成での代用 | 即座に諦め、①ユーザーのGoogle Drive素材 → ②公開実写フリー素材（Pexels/Mixkit）→ ③依頼者へ「不足カットだけDriveへ追加」を依頼。 |
| **公開API（tikwm等）で自アカウント集計がブロックされる** | 再生・いいね数を推測で作る | 依頼者へ「TikTokインサイト画面（またはTikTok Shop売上画面）のスクショを1枚貼ってください」と依頼し、Visionで数値を読み取って `account_state.json` へ自動登録する。 |
| **`edge-tts` がネットワーク制限で失敗する** | 無音のまま納品する／別の英語音声でごまかす | 接続エラーを正直に報告し、依頼者へ代替TTS指定または音声ファイル提供を仰ぐ。 |
| **チャット経由で完成mp4が重くて送れない** | ローカルVM内に置いたままパスだけ書いて終わる | Google Drive Connector 経由で `tiktok-shop-ops/output/` にアップロードし、直接開けるリンク＋コンタクトシート画像をチャットへ貼る。 |
| **複雑なffmpegコマンド文字列で記号・改行エラーが出る** | その場で長大なワンライナーを手組みする | 必ず `render_video.py` に `plan.json` を渡して実行する（`textfile=` 方式で日本語記号・改行バグを回避）。 |

---

## 3. 毎回の実行フロー（Progressive Disclosure）

全Skillを一度に読まず、必要な工程のファイルだけ参照して進めます（ベースURL：`https://fukushima-cyber.github.io/tiktok-shop-ai-os/`）。

1. **準備**：`core/00-os-principles.md` を参照（編集指定がなければ標準プリセットを自動適用）。アカウント登録済みなら `account_tracker_ref.py sync` で過去投稿と撤退型・勝ち型を最新化。
2. **調査＆企画（ゲートA）**：`skills/01-onboarding.md`（自律リサーチ）→ `skills/02-planning.md`（5〜8案発散→上位2〜3案提示）。人間の返事は「A / B / C」だけ。
3. **構成・台本・審査（ゲートB）**：`skills/03-beat-sheet.md` → `skills/04-script-tts.md` → `skills/05-red-team.md`（独立レッドチーム審査＋不合格箇所を自動リライト）まで一気に通し、合格版だけ提示。人間の返事は「OK / 修正Cut番号」だけ。
4. **素材収集・編集・検査（ゲートC）**：`skills/06-editing.md` と `render_video.py` で、本線mp4・ナレのみmp4・1秒コンタクトシート・音量/尺ログを生成し、Google Driveへ保存して共有。
5. **投稿＆48h自動PDCA**：`skills/07-post-pdca.md` で投稿パッケージ出力＋48時間後に自動集計・3段階判定・注文数1行確認→次回企画へ自動還流。
