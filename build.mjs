import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONTENT_DIR = path.join(__dirname, 'content');
const DIST_DIR = path.join(__dirname, 'dist');

const args = process.argv.slice(2);
const baseUrlIdx = args.indexOf('--base-url');
const BASE_URL = (baseUrlIdx !== -1 && args[baseUrlIdx + 1]
  ? args[baseUrlIdx + 1]
  : 'https://fukushima-cyber.github.io/tiktok-shop-ai-os'
).replace(/\/+$/, '');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyDir(src, dest) {
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function readContent(relPath) {
  return fs.readFileSync(path.join(CONTENT_DIR, relPath), 'utf8');
}

// Clean & copy raw content to dist/
fs.rmSync(DIST_DIR, { recursive: true, force: true });
copyDir(CONTENT_DIR, DIST_DIR);
fs.writeFileSync(path.join(DIST_DIR, '.nojekyll'), '');

// Expand relative URLs in dist/llms.txt to absolute URLs so any AI agent can fetch directly
const rawLlms = readContent('llms.txt');
const expandedLlms = rawLlms.replace(/`\.\/([^`]+)`/g, (_, p) => `\`${BASE_URL}/${p}\``);
fs.writeFileSync(path.join(DIST_DIR, 'llms.txt'), expandedLlms, 'utf8');

// Collect all docs for embedding into the zero-dependency SPA portal
const DOCS = [
  { id: 'llms', group: 'AI入口', title: 'llms.txt（ドキュメント目次・制作ガイド）', path: 'llms.txt', badge: 'AI入口', raw: expandedLlms },
  { id: 'muse-skill', group: 'AI入口', title: 'muse/SKILL.md（エージェント運用設定ガイド）', path: 'muse/SKILL.md', badge: 'Muse用', raw: readContent('muse/SKILL.md') },
  { id: 'core-00', group: '定数OS・共有素材', title: '00 定数OS・伸びる原理8つ・標準プリセット', path: 'core/00-os-principles.md', badge: '必読', raw: readContent('core/00-os-principles.md') },
  { id: 'case-assets', group: '定数OS・共有素材', title: '標準の共有素材置き場（Google Drive：TTSオートフロー）', path: 'cases/assets-index.md', badge: 'Drive', raw: readContent('cases/assets-index.md') },
  { id: 'skill-01', group: '7つのSkill', title: 'Skill 01：商材リサーチ & 実素材インベントリ', path: 'skills/01-onboarding.md', badge: '導入', raw: readContent('skills/01-onboarding.md') },
  { id: 'skill-02', group: '7つのSkill', title: 'Skill 02：企画発散 & 選別（素材フィルター）', path: 'skills/02-planning.md', badge: 'ゲートA', raw: readContent('skills/02-planning.md') },
  { id: 'skill-03', group: '7つのSkill', title: 'Skill 03：話の骨格 & 1.5秒ビートシート', path: 'skills/03-beat-sheet.md', badge: '構成', raw: readContent('skills/03-beat-sheet.md') },
  { id: 'skill-04', group: '7つのSkill', title: 'Skill 04：TikTok口語台本 & 改行・TTS最適化', path: 'skills/04-script-tts.md', badge: '台本', raw: readContent('skills/04-script-tts.md') },
  { id: 'skill-05', group: '7つのSkill', title: 'Skill 05：独立レビュー基準（即FAILゲート）', path: 'skills/05-red-team.md', badge: 'ゲートB', raw: readContent('skills/05-red-team.md') },
  { id: 'skill-06', group: '7つのSkill', title: 'Skill 06：自動動画編集 & 機械検査', path: 'skills/06-editing.md', badge: 'ゲートC', raw: readContent('skills/06-editing.md') },
  { id: 'skill-07', group: '7つのSkill', title: 'Skill 07：投稿パッケージ & 48h PDCA', path: 'skills/07-post-pdca.md', badge: '運用', raw: readContent('skills/07-post-pdca.md') },
  { id: 'case-senseware', group: '実例リファレンス（見本）', title: '実例1：センスウェア（お手本台本・素材管理）', path: 'cases/senseware.md', badge: '見本', raw: readContent('cases/senseware.md') },
  { id: 'case-calm7', group: '実例リファレンス（見本）', title: '実例2：カームセブン（266本リサーチ・主語一致）', path: 'cases/calm7.md', badge: '見本', raw: readContent('cases/calm7.md') },
  { id: 'tpl-exemplars', group: '任意上書きテンプレ', title: 'Good/Bad 対照ペア学習台帳テンプレ（exemplars.md）', path: 'templates/exemplars-template.md', badge: '学習', raw: readContent('templates/exemplars-template.md') },
  { id: 'tpl-account', group: '任意上書きテンプレ', title: 'アカウント上書きテンプレ（任意）', path: 'templates/account-template.md', badge: '任意', raw: readContent('templates/account-template.md') },
  { id: 'tpl-product', group: '任意上書きテンプレ', title: '別商材用・案件ルールテンプレ', path: 'templates/product-template.md', badge: 'コピー用', raw: readContent('templates/product-template.md') },
  { id: 'tpl-assets', group: '任意上書きテンプレ', title: '独自素材用・素材一覧テンプレ', path: 'templates/assets-template.md', badge: 'コピー用', raw: readContent('templates/assets-template.md') },
  { id: 'script-preflight', group: '自動化スクリプト', title: 'preflight_muse.sh（環境診断・日本語フォント確認）', path: 'scripts/preflight_muse.sh', badge: 'Bash', raw: '```bash\n' + readContent('scripts/preflight_muse.sh') + '\n```' },
  { id: 'script-frame-sheet', group: '自動化スクリプト', title: 'frame_sheet.py（0.5秒精密フレームシート & 参考動画構造抽出）', path: 'scripts/frame_sheet.py', badge: 'Python', raw: '```python\n' + readContent('scripts/frame_sheet.py') + '\n```' },
  { id: 'script-broll', group: '自動化スクリプト', title: 'broll_hunter.py（Mixkit/Pexels/RED実写B-roll収集・検品・吹き出し生成）', path: 'scripts/broll_hunter.py', badge: 'Python', raw: '```python\n' + readContent('scripts/broll_hunter.py') + '\n```' },
  { id: 'script-render', group: '自動化スクリプト', title: 'render_video.py（本番レンダリング・Whisper照合・フック3案一括）', path: 'scripts/render_video.py', badge: 'Python', raw: '```python\n' + readContent('scripts/render_video.py') + '\n```' },
  { id: 'script-ffmpeg', group: '自動化スクリプト', title: 'edit_pipeline_ref.sh（Drive/RED収集・自動検品・カット）', path: 'scripts/edit_pipeline_ref.sh', badge: 'Bash', raw: '```bash\n' + readContent('scripts/edit_pipeline_ref.sh') + '\n```' },
  { id: 'script-tracker', group: '自動化スクリプト', title: 'account_tracker_ref.py（自アカウント自動集計・48h PDCA）', path: 'scripts/account_tracker_ref.py', badge: 'Python', raw: '```python\n' + readContent('scripts/account_tracker_ref.py') + '\n```' },
];

const patternsData = JSON.parse(readContent('data/patterns.json'));
const universalData = JSON.parse(readContent('data/universal_patterns.json'));
patternsData.universal = universalData.universal;
patternsData.adapters = universalData.adapters;
const patternDetails = {};
for (const s of patternsData.scripts) {
  patternDetails[s.id] = readContent(`patterns/${s.id}.md`);
}

const payload = {
  baseUrl: BASE_URL,
  builtAt: new Date().toISOString().slice(0, 10),
  docs: DOCS,
  patterns: patternsData,
  patternDetails,
};

const safeJson = JSON.stringify(payload).replace(/</g, '\\u003c');

const html = `<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TikTok Shop AI運用OS</title>
  <meta name="description" content="Muse / GrokBotにllms.txtを1行貼るだけで、TikTok Shopアフィリエイトの企画・台本・編集・48h PDCAが自律進行する公開OS" />
  <style>
    :root {
      --bg: #f6f6f3;
      --surface: #ffffff;
      --surface-subtle: #efefe9;
      --border: #dcdcd4;
      --border-strong: #bdbdb3;
      --text: #161614;
      --text-muted: #52524c;
      --accent: #183a6d;
      --accent-hover: #102a52;
      --accent-soft: #eaf0f8;
      --gate: #b83227;
      --gate-soft: #fdf0ee;
      --ok: #1a663d;
      --ok-soft: #ebf6ef;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --sans: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Noto Sans JP", "Yu Gothic", system-ui, -apple-system, sans-serif;
      --radius: 6px;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--sans); font-size: 15px; line-height: 1.7; -webkit-font-smoothing: antialiased; }
    a { color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }
    a:hover { color: var(--accent-hover); }
    code { font-family: var(--mono); font-size: 0.88em; background: var(--surface-subtle); padding: 0.14em 0.4em; border-radius: 4px; border: 1px solid var(--border); }
    pre { margin: 16px 0; padding: 14px 16px; background: #1a1b1e; color: #f1f1ef; border-radius: var(--radius); overflow-x: auto; font-family: var(--mono); font-size: 13px; line-height: 1.55; }
    pre code { background: none; border: none; padding: 0; color: inherit; font-size: inherit; }

    /* Topbar */
    .topbar {
      position: sticky; top: 0; z-index: 30;
      background: var(--surface); border-bottom: 1px solid var(--border);
      padding: 12px 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;
    }
    .brand { display: flex; align-items: baseline; gap: 10px; }
    .brand-title { font-size: 16px; font-weight: 700; letter-spacing: -0.01em; margin: 0; }
    .brand-sub { font-size: 12px; color: var(--text-muted); font-family: var(--mono); }

    /* Buttons */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 8px 14px; border-radius: var(--radius); border: 1px solid var(--border-strong);
      background: var(--surface); color: var(--text); font-family: var(--sans); font-size: 13.5px; font-weight: 600;
      cursor: pointer; text-decoration: none; transition: background 0.12s, border-color 0.12s;
    }
    .btn:hover { background: var(--surface-subtle); border-color: var(--text-muted); color: var(--text); }
    .btn-primary { background: var(--accent); border-color: var(--accent); color: #ffffff; }
    .btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); color: #ffffff; }
    .btn-lg { padding: 12px 22px; font-size: 15px; }
    .btn-sm { padding: 5px 10px; font-size: 12px; }

    /* Nav Tabs */
    .nav-tabs {
      background: var(--surface); border-bottom: 1px solid var(--border);
      padding: 0 20px; display: flex; gap: 4px; overflow-x: auto;
    }
    .nav-tab {
      padding: 12px 16px; font-size: 14px; font-weight: 600; color: var(--text-muted);
      background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; white-space: nowrap;
    }
    .nav-tab:hover { color: var(--text); }
    .nav-tab.active { color: var(--accent); border-bottom-color: var(--accent); }

    /* Container */
    .container { max-width: 1180px; margin: 0 auto; padding: 28px 20px 64px; }
    .view { display: none; }
    .view.active { display: block; }

    /* Minimal Hero (1-click only) */
    .hero-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 32px 28px; margin-bottom: 20px;
    }
    .hero-card h1 { margin: 0 0 10px; font-size: 24px; line-height: 1.35; letter-spacing: -0.015em; }
    .hero-lead { margin: 0 0 22px; color: var(--text-muted); max-width: 68ch; font-size: 15px; }

    .copy-box {
      display: flex; align-items: stretch; gap: 10px; flex-wrap: wrap;
      background: #1a1b1e; border-radius: var(--radius); padding: 14px 16px;
    }
    .copy-box-text {
      flex: 1; min-width: 240px; font-family: var(--mono); font-size: 14px; line-height: 1.6;
      color: #f4f4f1; word-break: break-all; display: flex; align-items: center;
    }
    .quick-row {
      display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; align-items: center;
    }
    .quick-label { font-size: 12.5px; color: var(--text-muted); margin-right: 4px; }

    /* 3-step summary for human */
    .human-steps {
      display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 22px;
      padding-top: 20px; border-top: 1px solid var(--border);
    }
    .h-step { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; }
    .h-step-num { font-family: var(--mono); font-size: 12px; font-weight: 700; color: var(--accent); margin-bottom: 4px; }
    .h-step-title { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
    .h-step-desc { font-size: 13px; color: var(--text-muted); margin: 0; line-height: 1.55; }

    /* Flow strip */
    .section-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 22px 24px;
    }
    .section-card h2 { margin: 0 0 6px; font-size: 16px; }
    .section-sub { margin: 0 0 16px; font-size: 13.5px; color: var(--text-muted); }
    .flow-strip {
      display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px;
    }
    .flow-step {
      border: 1px solid var(--border); background: var(--bg); border-radius: var(--radius);
      padding: 10px; cursor: pointer; transition: border-color 0.12s, background 0.12s;
    }
    .flow-step:hover { border-color: var(--accent); background: var(--accent-soft); }
    .flow-step .step-num { font-family: var(--mono); font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center; }
    .flow-step .step-name { font-size: 13px; font-weight: 700; margin-top: 4px; line-height: 1.35; }
    .tag-gate { font-size: 10px; font-weight: 700; color: var(--gate); background: var(--gate-soft); padding: 1px 5px; border-radius: 3px; border: 1px solid #efc6c1; }
    .tag-ok { font-size: 11px; font-weight: 600; color: var(--ok); background: var(--ok-soft); padding: 1px 6px; border-radius: 3px; border: 1px solid #c3e2cf; }
    .tag-neutral { font-size: 11px; font-weight: 600; color: var(--text-muted); background: var(--surface-subtle); padding: 1px 6px; border-radius: 3px; border: 1px solid var(--border); }

    /* Docs Reader */
    .docs-layout { display: grid; grid-template-columns: 290px 1fr; gap: 20px; align-items: start; }
    .sidebar {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 12px; position: sticky; top: 72px; max-height: 760px; overflow-y: auto;
    }
    .sidebar-group { margin-bottom: 14px; }
    .sidebar-group-title { font-size: 11px; font-weight: 700; color: var(--text-muted); padding: 4px 8px; letter-spacing: 0.04em; }
    .doc-item {
      width: 100%; text-align: left; display: flex; justify-content: space-between; align-items: center; gap: 6px;
      padding: 8px 10px; border: none; background: none; border-radius: 4px; cursor: pointer;
      font-family: var(--sans); font-size: 13px; color: var(--text); line-height: 1.35;
    }
    .doc-item:hover { background: var(--surface-subtle); }
    .doc-item.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }

    .doc-pane { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px 28px; min-width: 0; }
    .doc-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding-bottom: 14px; margin-bottom: 18px; border-bottom: 1px solid var(--border); }
    .doc-path { font-family: var(--mono); font-size: 12px; color: var(--text-muted); }
    .doc-actions { display: flex; gap: 8px; flex-wrap: wrap; }

    /* Markdown Rendering */
    .md h1 { font-size: 22px; margin: 0 0 14px; line-height: 1.35; }
    .md h2 { font-size: 17px; margin: 28px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
    .md h3 { font-size: 15px; margin: 20px 0 8px; }
    .md p { margin: 0 0 12px; }
    .md ul, .md ol { margin: 0 0 14px; padding-left: 22px; }
    .md li { margin-bottom: 5px; }
    .md blockquote { margin: 14px 0; padding: 10px 14px; border-left: 3px solid var(--accent); background: var(--accent-soft); color: var(--text); border-radius: 0 4px 4px 0; }
    .md blockquote p:last-child { margin-bottom: 0; }
    .md hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
    .md table { width: 100%; border-collapse: collapse; margin: 14px 0 18px; font-size: 13.5px; display: block; overflow-x: auto; }
    .md th, .md td { border: 1px solid var(--border); padding: 8px 10px; text-align: left; vertical-align: top; }
    .md th { background: var(--surface-subtle); font-weight: 700; white-space: nowrap; }

    /* Patterns Explorer */
    .filter-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 14px; }
    .filter-bar input { flex: 1; min-width: 220px; padding: 8px 12px; border: 1px solid var(--border-strong); border-radius: var(--radius); font-size: 14px; }
    .filter-bar select { padding: 8px 10px; border: 1px solid var(--border-strong); border-radius: var(--radius); background: var(--surface); font-size: 13px; }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
    .chip { padding: 5px 11px; border: 1px solid var(--border-strong); background: var(--surface); border-radius: 4px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
    .chip.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    .data-table { width: 100%; border-collapse: collapse; background: var(--surface); font-size: 13.5px; }
    .data-table th, .data-table td { border-bottom: 1px solid var(--border); padding: 10px 12px; text-align: left; vertical-align: top; }
    .data-table th { background: var(--surface-subtle); font-weight: 700; white-space: nowrap; }
    .data-table tr.clickable:hover { background: var(--accent-soft); cursor: pointer; }
    .num { text-align: right !important; font-family: var(--mono); white-space: nowrap; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }

    /* Drawer */
    .drawer-backdrop { position: fixed; inset: 0; background: rgba(20,20,18,0.45); z-index: 50; display: none; justify-content: flex-end; }
    .drawer-backdrop.open { display: flex; }
    .drawer { width: min(720px, 100%); height: 100%; background: var(--surface); padding: 24px; overflow-y: auto; box-shadow: -4px 0 24px rgba(0,0,0,0.16); }

    /* Toast */
    .toast {
      position: fixed; bottom: 20px; right: 20px; z-index: 100;
      background: #161614; color: #fff; padding: 10px 16px; border-radius: var(--radius);
      font-size: 13px; font-weight: 600; opacity: 0; pointer-events: none; transition: opacity 0.18s;
    }
    .toast.show { opacity: 1; }

    @media (max-width: 960px) {
      .hero-card { padding: 22px 18px; }
      .human-steps { grid-template-columns: 1fr; }
      .flow-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .docs-layout { grid-template-columns: 1fr; }
      .sidebar { position: static; max-height: none; }
      .doc-pane { padding: 18px 16px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <h1 class="brand-title">TikTok Shop AI運用OS</h1>
      <span class="brand-sub">Muse・GrokBot直読対応</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button class="btn btn-primary btn-sm" id="topCopyBtn">AIに渡す1文をコピー</button>
      <a class="btn btn-sm" id="openLlmsLink" target="_blank" rel="noopener">llms.txt</a>
    </div>
  </header>

  <nav class="nav-tabs" aria-label="メインナビゲーション">
    <button class="nav-tab active" data-view="home">使い方（1行貼るだけ）</button>
    <button class="nav-tab" data-view="docs">OS・7つのSkill・実例見本</button>
    <button class="nav-tab" data-view="patterns">型インデックス（全ジャンル24型＋実測41型）</button>
  </nav>

  <main class="container">
    <!-- VIEW 1: MINIMAL 1-CLICK START -->
    <section id="view-home" class="view active">
      <div class="hero-card">
        <h1>どの商材でも、この1行をMuse / GrokBotに貼るだけで動き出します</h1>
        <p class="hero-lead">
          サイト側での入力や設定は不要です。扱う商材もアカウントも自由で、AIが <code>/llms.txt</code> を読んで <strong>自アカウント自動集計 → 商材・競合リサーチ → 企画発散 → 1.5秒ビートシート → 口語台本＆独立審査 → Drive/RED素材収集・カット編集 → 48h自動PDCA</strong> まで一貫して回します。
        </p>

        <div class="copy-box">
          <div class="copy-box-text" id="oneLineCommand"></div>
          <button class="btn btn-primary btn-lg" id="mainCopyBtn">1クリックでコピー</button>
        </div>

        <div class="quick-row">
          <span class="quick-label">すぐ使えるコピー：</span>
          <button class="btn btn-sm" id="quickWithProduct">商材・アカウント・Driveを添えて開始</button>
          <button class="btn btn-sm" id="quickRoutine">毎日定時の自動集計・PDCAルーティン文</button>
          <button class="btn btn-sm" id="quickUrlOnly">URLだけコピー</button>
        </div>

        <div class="human-steps">
          <div class="h-step">
            <div class="h-step-num">STEP 1</div>
            <div class="h-step-title">AIに1行貼って商材・アカウントを渡す</div>
            <p class="h-step-desc">上の文をMuse / GrokBotに送り、商品名（またはURL）・自分の <code>@handle</code>・素材Drive URLを伝えるだけ。</p>
          </div>
          <div class="h-step">
            <div class="h-step-num">STEP 2</div>
            <div class="h-step-title">AIが調査・制作・編集・集計を自律実行</div>
            <p class="h-step-desc">過去投稿集計、競合リサーチ、企画5〜8案発散、口語台本＆独立審査、Drive/RED素材からのカット編集・48h集計までAIが自動で回します。</p>
          </div>
          <div class="h-step">
            <div class="h-step-num">STEP 3</div>
            <div class="h-step-title">人間は「選ぶ・OK・注文数共有」だけ</div>
            <p class="h-step-desc">ゲートA（企画）・B（台本）・C（動画）の確認と、非公開の注文数だけ必要に応じて伝えればPDCAが回り続けます。</p>
          </div>
        </div>
      </div>

      <div class="section-card">
        <h2>AIが自動で辿る7つのSkill（クリックで中身を確認）</h2>
        <p class="section-sub">アカウント固有の指定がない場合は、検証済みの標準プリセット（顔出し不可・Nanami声・1.2倍速・-14LUFS・効果音固定7種）が自動適用されます。</p>
        <div class="flow-strip" id="flowStrip"></div>
      </div>
    </section>

    <!-- VIEW 2: DOCS & SKILLS -->
    <section id="view-docs" class="view">
      <div class="docs-layout">
        <aside class="sidebar" id="docSidebar"></aside>
        <article class="doc-pane">
          <div class="doc-header">
            <div class="doc-path" id="docPath"></div>
            <div class="doc-actions">
              <button class="btn btn-sm" id="copyDocUrlBtn">URLをコピー</button>
              <button class="btn btn-sm" id="copyDocMdBtn">Markdownをコピー</button>
              <a class="btn btn-sm" id="openRawDocLink" target="_blank" rel="noopener">生ファイルを開く</a>
            </div>
          </div>
          <div class="md" id="docContent"></div>
        </article>
      </div>
    </section>

    <!-- VIEW 3: LIGHTWEIGHT PATTERN INDEX -->
    <section id="view-patterns" class="view">
      <div class="section-card">
        <div class="doc-header" style="margin-bottom:14px;">
          <h2 style="margin:0;">軽量型インデックス（全ジャンル汎用24型 ＋ 6ジャンル別ルール ＋ 実測21企画×20台本）</h2>
          <div class="doc-actions">
            <button class="btn btn-sm" id="copyPatternsUrlBtn">URLをコピー</button>
            <a class="btn btn-sm" id="openPatternsMdLink" target="_blank" rel="noopener">生patterns.mdを開く</a>
          </div>
        </div>
        <p class="section-sub">
          美容以外のガジェット・食品・日用品・アパレル・健康雑貨でもそのまま使える <strong>全ジャンル汎用24型（G01〜G24）</strong> と、Muse内で勝った型が自動で溜まる <code>local_patterns.json</code> を組み合わせて企画します。台本型（S01〜S20）の行をクリックすると詳細テンプレートを確認できます。
        </p>
        <div class="filter-bar">
          <input type="search" id="patSearch" placeholder="キーワード検索（例：ガジェット、食品、★1、逆張り、時短、Dupe、開封、コメント）" />
          <select id="patTab">
            <option value="universal">全ジャンル汎用 企画型（全24型：G01〜G24）</option>
            <option value="adapters">ジャンル別アダプター（6領域：強い画・NG境界）</option>
            <option value="planning">美容実測 企画型（全21型：P01〜P22）</option>
            <option value="scripts">台本骨組み型（全20型：S01〜S20・詳細あり）</option>
            <option value="calm7">カームセブン固有型（266本調査）</option>
          </select>
          <select id="patSort">
            <option value="id">ID順</option>
            <option value="views">再生中央値 高い順</option>
            <option value="like">いいね率 高い順</option>
            <option value="n">根拠本数 多い順</option>
          </select>
        </div>
        <div class="chip-row" id="productChips">
          <button class="chip active" data-prod="">すべて</button>
          <button class="chip" data-prod="ガジェット">ガジェット</button>
          <button class="chip" data-prod="食品">食品</button>
          <button class="chip" data-prod="日用品">日用品</button>
          <button class="chip" data-prod="アパレル">アパレル</button>
          <button class="chip" data-prod="美容">美容・香水</button>
          <button class="chip" data-prod="健康">健康雑貨</button>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="patTable"></table>
        </div>
      </div>
    </section>
  </main>

  <div class="drawer-backdrop" id="drawerBackdrop">
    <div class="drawer">
      <div class="doc-header">
        <span class="doc-path" id="drawerPath"></span>
        <div class="doc-actions">
          <button class="btn btn-sm" id="copyDrawerUrlBtn">URLコピー</button>
          <button class="btn btn-sm" id="copyDrawerMdBtn">Markdownコピー</button>
          <button class="btn btn-sm btn-primary" id="closeDrawerBtn">閉じる</button>
        </div>
      </div>
      <div class="md" id="drawerContent"></div>
    </div>
  </div>

  <div class="toast" id="toast">コピーしました</div>

  <script id="os-data" type="application/json">${safeJson}</script>
  <script>
    const DATA = JSON.parse(document.getElementById('os-data').textContent);
    const RUNTIME_BASE = (location.protocol === 'http:' || location.protocol === 'https:')
      ? (location.origin + location.pathname.replace(/\\/[^/]+\\.html$/, '').replace(/\\/+$/, ''))
      : DATA.baseUrl;
    const isLocalHost = location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname.endsWith('.localhost');
    const PUBLIC_BASE = isLocalHost ? DATA.baseUrl : RUNTIME_BASE;

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
    }

    async function copyText(txt, label = 'コピーしました') {
      try {
        await navigator.clipboard.writeText(txt);
        showToast(label);
      } catch {
        const ta = document.createElement('textarea');
        ta.value = txt; document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
        showToast(label);
      }
    }

    // Minimal Markdown renderer
    function esc(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
    function inlineMd(s) {
      let out = esc(s);
      out = out.replace(/\`([^\`]+)\`/g, '<code>$1</code>');
      out = out.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
      out = out.replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^)]+|\\.\\.\\/[^)]+|\\.\\/[^)]+)\\)/g, (_, label, href) => {
        const resolved = href.startsWith('http') ? href : (RUNTIME_BASE + '/' + href.replace(/^\\.\\.\\/|\\.\\//, ''));
        return '<a href="' + resolved + '" target="_blank" rel="noopener">' + label + '</a>';
      });
      return out;
    }
    function renderMd(md) {
      const lines = md.replace(/\\r\\n/g, '\\n').split('\\n');
      let html = '';
      let i = 0;
      while (i < lines.length) {
        const line = lines[i];
        if (line.startsWith('\`\`\`')) {
          const buf = []; i++;
          while (i < lines.length && !lines[i].startsWith('\`\`\`')) { buf.push(lines[i]); i++; }
          i++;
          html += '<pre><code>' + esc(buf.join('\\n')) + '</code></pre>';
          continue;
        }
        if (/^---+$/.test(line.trim())) { html += '<hr />'; i++; continue; }
        if (/^### /.test(line)) { html += '<h3>' + inlineMd(line.slice(4)) + '</h3>'; i++; continue; }
        if (/^## /.test(line)) { html += '<h2>' + inlineMd(line.slice(3)) + '</h2>'; i++; continue; }
        if (/^# /.test(line)) { html += '<h1>' + inlineMd(line.slice(2)) + '</h1>'; i++; continue; }
        if (/^> /.test(line)) {
          const buf = [];
          while (i < lines.length && /^> ?/.test(lines[i])) { buf.push(inlineMd(lines[i].replace(/^> ?/, ''))); i++; }
          html += '<blockquote><p>' + buf.join('<br />') + '</p></blockquote>';
          continue;
        }
        if (line.trim().startsWith('|') && i + 1 < lines.length && /^\\|[-:| ]+\\|$/.test(lines[i+1].trim())) {
          const parseRow = r => r.trim().replace(/^\\||\\|$/g, '').split('|').map(c => c.trim());
          const headers = parseRow(line);
          i += 2;
          const rows = [];
          while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(parseRow(lines[i])); i++; }
          html += '<table><thead><tr>' + headers.map(h => '<th>' + inlineMd(h) + '</th>').join('') + '</tr></thead><tbody>'
            + rows.map(r => '<tr>' + r.map(c => '<td>' + inlineMd(c) + '</td>').join('') + '</tr>').join('')
            + '</tbody></table>';
          continue;
        }
        if (/^[-*] /.test(line)) {
          html += '<ul>';
          while (i < lines.length && /^[-*] /.test(lines[i])) {
            const item = lines[i].replace(/^[-*] /, '');
            if (/^\\[[ x]\\] /.test(item)) {
              const checked = item.startsWith('[x]') ? '☑ ' : '☐ ';
              html += '<li>' + checked + inlineMd(item.slice(4)) + '</li>';
            } else {
              html += '<li>' + inlineMd(item) + '</li>';
            }
            i++;
          }
          html += '</ul>';
          continue;
        }
        if (/^\\d+\\. /.test(line)) {
          html += '<ol>';
          while (i < lines.length && /^\\d+\\. /.test(lines[i])) {
            html += '<li>' + inlineMd(lines[i].replace(/^\\d+\\. /, '')) + '</li>';
            i++;
          }
          html += '</ol>';
          continue;
        }
        if (line.trim() === '') { i++; continue; }
        const p = [];
        while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,3} |> |[-*] |\\d+\\. |\`\`\`|---+$|\\|)/.test(lines[i])) {
          p.push(inlineMd(lines[i])); i++;
        }
        html += '<p>' + p.join('<br />') + '</p>';
      }
      return html;
    }

    // 1-line AI commands
    const llmsPublicUrl = PUBLIC_BASE + '/llms.txt';
    const defaultCmd = llmsPublicUrl + ' を制作ガイドとして参照し、この手順に沿ってTikTok Shop動画の制作を進めてください。';
    document.getElementById('oneLineCommand').textContent = defaultCmd;
    document.getElementById('openLlmsLink').href = RUNTIME_BASE + '/llms.txt';
    document.getElementById('mainCopyBtn').onclick = () => copyText(defaultCmd, 'AIに渡す1文をコピーしました');
    document.getElementById('topCopyBtn').onclick = () => copyText(defaultCmd, 'AIに渡す1文をコピーしました');
    document.getElementById('quickWithProduct').onclick = () => copyText(llmsPublicUrl + ' を読んで進めてください。商材：【商品名やURL】／アカウント：【@handle】／素材Drive：【URLまたはなし】', '商材・アカウントつき開始文をコピーしました');
    document.getElementById('quickRoutine').onclick = () => copyText(llmsPublicUrl + ' を読み、Skill 07に従って私のアカウント（@handle）を自動集計してください。48時間経過した新規動画があれば3段階PDCA判定と次回企画ブリーフを作成して報告してください。投稿や広告操作はせず報告のみにしてください。', '定期PDCAルーティン文をコピーしました');
    document.getElementById('quickUrlOnly').onclick = () => copyText(llmsPublicUrl, 'llms.txt のURLをコピーしました');

    // View switching
    function switchView(viewName) {
      document.querySelectorAll('.nav-tab').forEach(b => b.classList.toggle('active', b.dataset.view === viewName));
      document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + viewName));
    }
    document.querySelectorAll('.nav-tab').forEach(btn => btn.onclick = () => switchView(btn.dataset.view));

    // Flow strip
    const flowSteps = [
      { id: 'skill-01', num: '01', name: '自律リサーチ・案件設計', tag: '' },
      { id: 'skill-02', num: '02', name: '企画発散・選別', tag: 'ゲートA' },
      { id: 'skill-03', num: '03', name: '1.5秒ビートシート', tag: '' },
      { id: 'skill-04', num: '04', name: '口語台本・TTS', tag: '' },
      { id: 'skill-05', num: '05', name: '独立レッドチーム審査', tag: 'ゲートB' },
      { id: 'skill-06', num: '06', name: '素材収集・カット編集', tag: 'ゲートC' },
      { id: 'skill-07', num: '07', name: '自動集計・48h PDCA', tag: '' },
    ];
    const flowEl = document.getElementById('flowStrip');
    flowSteps.forEach(s => {
      const div = document.createElement('div');
      div.className = 'flow-step';
      div.innerHTML = '<div class="step-num"><span>Skill ' + s.num + '</span>' + (s.tag ? '<span class="tag-gate">' + s.tag + '</span>' : '') + '</div><div class="step-name">' + s.name + '</div>';
      div.onclick = () => { switchView('docs'); selectDoc(s.id); };
      flowEl.appendChild(div);
    });

    // Docs Sidebar & Viewer
    let currentDoc = DATA.docs[0];
    const sidebar = document.getElementById('docSidebar');
    const groups = [...new Set(DATA.docs.map(d => d.group))];
    groups.forEach(g => {
      const sec = document.createElement('div');
      sec.className = 'sidebar-group';
      sec.innerHTML = '<div class="sidebar-group-title">' + esc(g) + '</div>';
      DATA.docs.filter(d => d.group === g).forEach(doc => {
        const b = document.createElement('button');
        b.className = 'doc-item';
        b.dataset.docId = doc.id;
        const badgeClass = doc.badge.includes('ゲート') ? 'tag-gate' : (doc.badge === '必読' || doc.badge === 'AI入口' ? 'tag-ok' : 'tag-neutral');
        b.innerHTML = '<span>' + esc(doc.title) + '</span><span class="' + badgeClass + '">' + esc(doc.badge) + '</span>';
        b.onclick = () => selectDoc(doc.id);
        sec.appendChild(b);
      });
      sidebar.appendChild(sec);
    });

    function selectDoc(id) {
      const doc = DATA.docs.find(d => d.id === id) || DATA.docs[0];
      currentDoc = doc;
      document.querySelectorAll('.doc-item').forEach(el => el.classList.toggle('active', el.dataset.docId === doc.id));
      const pubUrl = PUBLIC_BASE + '/' + doc.path;
      document.getElementById('docPath').textContent = pubUrl;
      document.getElementById('openRawDocLink').href = RUNTIME_BASE + '/' + doc.path;
      document.getElementById('docContent').innerHTML = renderMd(doc.raw);
    }
    selectDoc('llms');
    document.getElementById('copyDocUrlBtn').onclick = () => copyText(PUBLIC_BASE + '/' + currentDoc.path, 'URLをコピーしました');
    document.getElementById('copyDocMdBtn').onclick = () => copyText(currentDoc.raw, 'Markdownをコピーしました');

    // Patterns Explorer
    let activeProd = '';
    const patSearch = document.getElementById('patSearch');
    const patTab = document.getElementById('patTab');
    const patSort = document.getElementById('patSort');
    const patTable = document.getElementById('patTable');
    document.getElementById('openPatternsMdLink').href = RUNTIME_BASE + '/index/patterns.md';
    document.getElementById('copyPatternsUrlBtn').onclick = () => copyText(PUBLIC_BASE + '/index/patterns.md', '型インデックスURLをコピーしました');

    function parseNum(str) {
      return parseFloat(String(str || '0').replace(/[,%]/g, '')) || 0;
    }

    function renderPatterns() {
      const tab = patTab.value;
      const q = patSearch.value.trim().toLowerCase();
      const sort = patSort.value;
      document.getElementById('productChips').style.display = (tab === 'universal' || tab === 'planning') ? 'flex' : 'none';
      patSort.style.display = (tab === 'universal' || tab === 'adapters') ? 'none' : 'inline-block';

      let list = [...DATA.patterns[tab]];
      if (tab === 'universal' && activeProd) {
        list = list.filter(item => (item.genres || '').includes(activeProd) || (item.genres || '').includes('全ジャンル'));
      } else if (tab === 'planning' && activeProd) {
        list = list.filter(item => (item.products || '').includes(activeProd) || (activeProd === '美容' && /コスメ|スキンケア|香水|ヘアケア/.test(item.products || '')));
      }
      if (q) {
        list = list.filter(item => JSON.stringify(item).toLowerCase().includes(q));
      }
      if (tab !== 'universal' && tab !== 'adapters') {
        list.sort((a, b) => {
          if (sort === 'views') return parseNum(b.median_views) - parseNum(a.median_views);
          if (sort === 'like') return parseNum(b.median_like_rate) - parseNum(a.median_like_rate);
          if (sort === 'n') return (b.n || 0) - (a.n || 0);
          return String(a.id).localeCompare(String(b.id));
        });
      }

      if (tab === 'universal') {
        patTable.innerHTML = '<thead><tr><th>ID</th><th>群</th><th>企画型</th><th>合うジャンル</th><th>冒頭0〜2秒フック例</th><th>強い画（顔なし対応）</th><th>相性台本</th><th>主KPI</th></tr></thead><tbody>'
          + list.map(u => '<tr>'
            + '<td><code>' + esc(u.id) + '</code></td>'
            + '<td><span class="tag-neutral">' + esc(u.group) + '</span></td>'
            + '<td><strong>' + esc(u.name) + '</strong></td>'
            + '<td>' + esc(u.genres) + '</td>'
            + '<td>' + esc(u.hook) + '</td>'
            + '<td>' + esc(u.visual) + '</td>'
            + '<td>' + (u.scripts || []).map(x => '<code>' + esc(x) + '</code>').join(' ') + '</td>'
            + '<td><span class="tag-ok">' + esc(u.kpi) + '</span></td>'
            + '</tr>').join('') + '</tbody>';
      } else if (tab === 'adapters') {
        patTable.innerHTML = '<thead><tr><th>ジャンル</th><th>0〜3秒で勝てる強い画</th><th>買い手が必ず気にする納得要素</th><th>絶対NG境界（法務・信頼）</th></tr></thead><tbody>'
          + list.map(a => '<tr>'
            + '<td><strong>' + esc(a.genre) + '</strong></td>'
            + '<td>' + esc(a.strong_visual) + '</td>'
            + '<td>' + esc(a.must_answer) + '</td>'
            + '<td><span style="color:var(--gate);">' + esc(a.ng) + '</span></td>'
            + '</tr>').join('') + '</tbody>';
      } else if (tab === 'planning') {
        patTable.innerHTML = '<thead><tr><th>ID</th><th>企画型</th><th>誰に / 状況・悩み</th><th>切り口</th><th>合う商材</th><th class="num">再生中央値</th><th class="num">いいね率</th><th class="num">n</th><th>相性の良い台本型</th></tr></thead><tbody>'
          + list.map(p => '<tr>'
            + '<td><code>' + esc(p.id) + '</code></td>'
            + '<td><strong>' + esc(p.name) + '</strong></td>'
            + '<td>' + esc(p.who) + '<br /><span style="color:var(--text-muted);font-size:12px;">' + esc(p.pain) + '</span></td>'
            + '<td>' + esc(p.angle) + '</td>'
            + '<td>' + esc(p.products) + '</td>'
            + '<td class="num">' + esc(p.median_views) + '</td>'
            + '<td class="num">' + esc(p.median_like_rate) + '</td>'
            + '<td class="num">' + esc(p.n) + '</td>'
            + '<td>' + (p.combos || []).map(c => '<code>' + esc(c.script.split(' ')[0]) + '</code>').join(' ') + '</td>'
            + '</tr>').join('') + '</tbody>';
      } else if (tab === 'scripts') {
        patTable.innerHTML = '<thead><tr><th>ID</th><th>台本型（クリックで詳細）</th><th>状態</th><th>流れ</th><th>商品の出し方</th><th class="num">再生中央値</th><th class="num">いいね率</th><th class="num">n</th></tr></thead><tbody>'
          + list.map(s => '<tr class="clickable" data-sid="' + esc(s.id) + '">'
            + '<td><code>' + esc(s.id) + '</code></td>'
            + '<td><strong>' + esc(s.name) + '</strong></td>'
            + '<td><span class="' + (s.status === '使用中' ? 'tag-ok' : 'tag-neutral') + '">' + esc(s.status) + '</span></td>'
            + '<td>' + esc(s.flow) + '</td>'
            + '<td>' + esc(s.product_entry) + '</td>'
            + '<td class="num">' + esc(s.median_views) + '</td>'
            + '<td class="num">' + esc(s.median_like_rate) + '</td>'
            + '<td class="num">' + esc(s.n) + '</td>'
            + '</tr>').join('') + '</tbody>';
        patTable.querySelectorAll('tr.clickable').forEach(tr => {
          tr.onclick = () => openDrawer(tr.dataset.sid);
        });
      } else {
        patTable.innerHTML = '<thead><tr><th>ID</th><th>カームセブン固有型</th><th class="num">本数</th><th class="num">上位30内</th><th class="num">再生中央値</th><th class="num">いいね率</th><th>構造・素材条件</th></tr></thead><tbody>'
          + list.map(c => '<tr>'
            + '<td><code>' + esc(c.id) + '</code></td>'
            + '<td><strong>' + esc(c.name) + '</strong></td>'
            + '<td class="num">' + esc(c.n) + '</td>'
            + '<td class="num">' + esc(c.top30) + '</td>'
            + '<td class="num">' + esc(c.median_views) + '</td>'
            + '<td class="num">' + esc(c.median_like_rate) + '</td>'
            + '<td>' + esc(c.note) + '</td>'
            + '</tr>').join('') + '</tbody>';
      }
    }

    document.querySelectorAll('#productChips .chip').forEach(ch => {
      ch.onclick = () => {
        activeProd = ch.dataset.prod;
        document.querySelectorAll('#productChips .chip').forEach(c => c.classList.toggle('active', c === ch));
        renderPatterns();
      };
    });
    [patSearch, patTab, patSort].forEach(el => {
      el.addEventListener('input', renderPatterns);
      el.addEventListener('change', renderPatterns);
    });
    renderPatterns();

    // Drawer for S01..S20 details
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    let activeSid = '';
    function openDrawer(sid) {
      activeSid = sid;
      const md = DATA.patternDetails[sid] || '';
      document.getElementById('drawerPath').textContent = PUBLIC_BASE + '/patterns/' + sid + '.md';
      document.getElementById('drawerContent').innerHTML = renderMd(md);
      drawerBackdrop.classList.add('open');
    }
    document.getElementById('closeDrawerBtn').onclick = () => drawerBackdrop.classList.remove('open');
    drawerBackdrop.onclick = (e) => { if (e.target === drawerBackdrop) drawerBackdrop.classList.remove('open'); };
    document.getElementById('copyDrawerUrlBtn').onclick = () => copyText(PUBLIC_BASE + '/patterns/' + activeSid + '.md', activeSid + ' のURLをコピーしました');
    document.getElementById('copyDrawerMdBtn').onclick = () => copyText(DATA.patternDetails[activeSid] || '', activeSid + ' のMarkdownをコピーしました');
  </script>
</body>
</html>`;

fs.writeFileSync(path.join(DIST_DIR, 'index.html'), html, 'utf8');
console.log(`Built dist/ successfully (BASE_URL=${BASE_URL})`);
console.log(`- index.html: ${(Buffer.byteLength(html) / 1024).toFixed(1)} KB`);
console.log(`- llms.txt: ${(Buffer.byteLength(expandedLlms) / 1024).toFixed(1)} KB`);
console.log(`- docs embedded: ${DOCS.length}, S-patterns: ${Object.keys(patternDetails).length}`);
