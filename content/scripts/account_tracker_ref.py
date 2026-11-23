#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：自アカウント自動集計・48h PDCA & ローカル勝ち型自動蓄積トラッカー（Skill 01/02/07）

使い方:
  # 1) 公開投稿の自動集計 & 48h勝ち型の自動昇格（local_patterns.json連動）
  python3 account_tracker_ref.py sync --handle @your_account --state ./ledger/account_state.json --report ./ledger/account_report.md --patterns ./ledger/local_patterns.json

  # 2) 投稿に「型・仮説・注文数(CV)」を紐づける（48h勝ち型なら自動で verified 昇格）
  python3 account_tracker_ref.py annotate --state ./ledger/account_state.json --report ./ledger/account_report.md --patterns ./ledger/local_patterns.json --video-id 7700... --pattern "G07xS08" --genre "ガジェット" --hypothesis "弱点先出しで保存率改善" --changed "型" --channel organic --orders 2

  # 3) Skill 01 の自律リサーチで見つけた新ジャンル固有の仮型をローカル保存
  python3 account_tracker_ref.py learn-pattern --patterns ./ledger/local_patterns.json --id "L01" --name "充電ケーブル絡まり一発解消" --genre "ガジェット" --hook "カバンの中まだこれでイラついてない？" --visual "絡まったコード→マグネット吸着の1秒カット" --source-note "公開TikTok競合調査より"

  # 4) 公開OS本体へ還元できる強い型（verified かつ根拠2本以上）をMarkdown出力
  python3 account_tracker_ref.py export-candidates --patterns ./ledger/local_patterns.json --out ./ledger/os_pattern_proposals.md
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import urllib.parse
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))


def fetch_public_posts(handle: str, count: int = 30) -> list[dict]:
    clean = handle.strip().lstrip("@")
    url = f"https://www.tikwm.com/api/user/posts?unique_id={urllib.parse.quote(clean)}&count={count}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"tikwm API returned error: {data.get('msg') or data}")
    videos = (data.get("data") or {}).get("videos") or []
    out = []
    for v in videos:
        vid = str(v.get("video_id") or v.get("aweme_id") or "")
        ts = int(v.get("create_time") or 0)
        created_jst = dt.datetime.fromtimestamp(ts, tz=JST).isoformat() if ts else ""
        out.append(
            {
                "video_id": vid,
                "url": f"https://www.tiktok.com/@{clean}/video/{vid}" if vid else "",
                "title": (v.get("title") or "").strip(),
                "created_at_ts": ts,
                "created_at_jst": created_jst,
                "duration_sec": v.get("duration"),
                "play_count": int(v.get("play_count") or 0),
                "digg_count": int(v.get("digg_count") or 0),
                "comment_count": int(v.get("comment_count") or 0),
                "share_count": int(v.get("share_count") or 0),
                "collect_count": int(v.get("collect_count") or 0),
                "is_ad": bool(v.get("is_ad")),
            }
        )
    return out


def judge_3stage(post: dict, now_ts: float) -> tuple[str, str]:
    """3段階評価軸（00-os-principles.md 準拠）"""
    created = post.get("created_at_ts") or 0
    age_h = (now_ts - created) / 3600.0 if created else 0.0
    channel = post.get("channel") or ("ad" if post.get("is_ad") else "organic")

    if channel == "ad":
        orders = post.get("orders")
        return ("広告配信（別枠評価）", f"注文:{orders if orders is not None else '未確認'} / 有機判定には使わない")

    if created and age_h < 48.0:
        return (f"計測中（経過{age_h:.1f}h）", "48時間到達後に最終判定")
    if not created and post.get("play_count", 0) == 0:
        return ("計測中（投稿前/未同期）", "投稿後48時間で最終判定")

    plays = int(post.get("play_count") or 0)
    likes = int(post.get("digg_count") or 0)
    saves = int(post.get("collect_count") or 0)
    orders = post.get("orders")
    like_rate = (likes / plays * 100.0) if plays > 0 else 0.0
    save_rate = (saves / plays * 100.0) if plays > 0 else 0.0

    hook_ok = plays >= 1000
    body_ok = (like_rate >= 0.5) or (save_rate >= 0.15)
    cv_ok = (orders is not None and orders > 0)

    if hook_ok and (body_ok or cv_ok):
        if orders == 0:
            return ("④ CV導線不足", "冒頭・中盤固定。商品パートの情景化・理由重ね・CTAを改修")
        return ("① 勝ち型（横展開）", "同型で1変数だけ変えて横展開＋Spark Ads候補")
    if (not hook_ok) and (body_ok or cv_ok):
        return ("② フック不足", "型・中盤・商品パート固定。冒頭0〜2秒だけ差し替え")
    if hook_ok and (not body_ok) and (not cv_ok):
        return ("③ 中盤・訴求不足", "冒頭固定。中盤テンポ(1.5sカット)・絵と主語・認識転換を改修")
    return ("⑤ 全面未達（撤退）", "この型は撤退。Skill 02で別系統の型へ変更")


def load_json(path: str, default: dict) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def promote_local_patterns(state: dict, patterns_path: str, now_str: str) -> dict:
    """48h判定で勝ち型になった投稿を local_patterns.json へ自動昇格・実績蓄積する"""
    lp = load_json(patterns_path, {"updated_at_jst": now_str, "patterns": {}})
    now_ts = dt.datetime.now(tz=JST).timestamp()
    for vid, post in state.get("posts", {}).items():
        pat_id = (post.get("pattern") or "").strip()
        if not pat_id:
            continue
        status, _ = judge_3stage(post, now_ts)
        entry = lp["patterns"].setdefault(
            pat_id,
            {
                "id": pat_id,
                "name": post.get("pattern_name") or pat_id,
                "genre": post.get("genre") or "未指定",
                "hook": post.get("hook") or "",
                "visual": post.get("visual") or "",
                "status": "candidate",
                "verified_videos": [],
                "retired_videos": [],
                "best_plays": 0,
                "total_orders": 0,
                "updated_at_jst": now_str,
            },
        )
        plays = int(post.get("play_count") or 0)
        entry["best_plays"] = max(int(entry.get("best_plays") or 0), plays)
        if post.get("genre") and entry.get("genre") == "未指定":
            entry["genre"] = post["genre"]

        if "勝ち型" in status:
            if vid not in entry["verified_videos"]:
                entry["verified_videos"].append(vid)
                entry["total_orders"] = int(entry.get("total_orders") or 0) + int(post.get("orders") or 0)
            entry["status"] = "verified"
            entry["updated_at_jst"] = now_str
        elif "撤退" in status:
            if vid not in entry["retired_videos"]:
                entry["retired_videos"].append(vid)
            if not entry["verified_videos"]:
                entry["status"] = "retired"
            entry["updated_at_jst"] = now_str

    lp["updated_at_jst"] = now_str
    save_json(patterns_path, lp)
    return lp


def write_report(state: dict, report_path: str, lp: dict | None = None) -> None:
    now_ts = dt.datetime.now(tz=JST).timestamp()
    posts = sorted(state["posts"].values(), key=lambda x: x.get("created_at_ts") or 0, reverse=True)

    retired = set()
    winning = set()
    used_recent = []
    need_orders = []

    lines = [
        f"# アカウント自動集計 & 48h PDCAレポート（@{state['handle']}）",
        "",
        f"- **最終集計（JST）**：{state['updated_at_jst']}",
        f"- **集計本数**：{len(posts)}本",
        "",
        "## 投稿別 3段階判定一覧",
        "",
        "| 投稿日(JST) | タイトル | 区分 | 型 | 再生 | いいね率 | 保存率 | 注文(CV) | 判定 | 次の一手 |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]

    for p in posts:
        plays = int(p.get("play_count") or 0)
        likes = int(p.get("digg_count") or 0)
        saves = int(p.get("collect_count") or 0)
        lr = f"{(likes / plays * 100):.2f}%" if plays else "-"
        sr = f"{(saves / plays * 100):.2f}%" if plays else "-"
        pat = p.get("pattern") or "未記録"
        ch = p.get("channel") or ("広告" if p.get("is_ad") else "有機")
        orders = p.get("orders")
        orders_str = str(orders) if orders is not None else "未確認"
        status, action = judge_3stage(p, now_ts)

        if pat != "未記録":
            used_recent.append(pat)
            if "撤退" in status:
                retired.add(pat)
            elif "勝ち型" in status:
                winning.add(pat)
        if ("48時間" not in status) and ("投稿前" not in status) and (orders is None):
            need_orders.append(f"`{p['video_id']}` ({p['title'][:24]})")

        date_s = (p.get("created_at_jst") or "")[:16].replace("T", " ")
        title_s = (p.get("title") or "(無題)").replace("|", "／")[:30]
        lines.append(
            f"| {date_s} | {title_s} | {ch} | `{pat}` | {plays:,} | {lr} | {sr} | {orders_str} | {status} | {action} |"
        )

    state["retired_patterns"] = sorted(retired)
    state["winning_patterns"] = sorted(winning)

    verified_local = []
    promo_ready = []
    if lp:
        for pid, info in lp.get("patterns", {}).items():
            if info.get("status") == "verified":
                cnt = len(info.get("verified_videos") or [])
                verified_local.append(f"`{pid}` ({info.get('genre')}, 実績{cnt}本)")
                if cnt >= 2:
                    promo_ready.append(pid)

    lines += [
        "",
        "## 次回企画（Skill 02）へ自動引き継ぎする制約",
        f"- **勝ち型（横展開候補）**：{', '.join(state['winning_patterns']) or 'まだなし'}",
        f"- **撤退済み型（二度と使わない）**：{', '.join(state['retired_patterns']) or 'まだなし'}",
        f"- **直近使用型（新規企画では避ける）**：{', '.join(used_recent[:5]) or '未記録'}",
        f"- **ローカル検証済み型（`local_patterns.json`）**：{', '.join(verified_local) or 'まだなし'}",
        f"- **OS本体への還元候補（根拠2本以上）**：{', '.join(promo_ready) or 'なし'}",
        "",
        "## 依頼者への確認（非公開の注文数だけ）",
        f"- TikTok Shop管理画面の注文数が未確認の動画：{', '.join(need_orders[:5]) if need_orders else 'なし'}",
    ]

    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def export_os_candidates(patterns_path: str, out_md: str) -> int:
    lp = load_json(patterns_path, {"patterns": {}})
    eligible = [
        p for p in lp.get("patterns", {}).values()
        if p.get("status") == "verified" and len(p.get("verified_videos") or []) >= 2
    ]
    lines = [
        "# 公開OS本体への勝ち型還元提案（48h合格・根拠2本以上のみ抽出）",
        "",
        "管理者が確認・承認した型だけを `content/data/universal_patterns.json` に追加してください。",
        "",
        "| ID | 型名 | ジャンル | 根拠本数 | 最高再生 | 合計注文 | 冒頭フック例 | 強い画 |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for p in eligible:
        lines.append(
            f"| `{p['id']}` | {p['name']} | {p.get('genre','')} | {len(p.get('verified_videos') or [])} | {int(p.get('best_plays') or 0):,} | {int(p.get('total_orders') or 0)} | {p.get('hook','')} | {p.get('visual','')} |"
        )
    if not eligible:
        lines.append("| — | 該当なし（48h勝ち型が2本以上溜まると自動抽出されます） | — | 0 | 0 | 0 | — | — |")
    os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(eligible)


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok account tracker & local pattern learner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Fetch public posts, update PDCA report, and promote winning patterns")
    p_sync.add_argument("--handle", required=True)
    p_sync.add_argument("--state", default="./account_state.json")
    p_sync.add_argument("--report", default="./account_report.md")
    p_sync.add_argument("--patterns", default="./local_patterns.json")
    p_sync.add_argument("--count", type=int, default=30)

    p_ann = sub.add_parser("annotate", help="Record pattern/genre/hypothesis/orders for a video")
    p_ann.add_argument("--state", default="./account_state.json")
    p_ann.add_argument("--report", default="./account_report.md")
    p_ann.add_argument("--patterns", default="./local_patterns.json")
    p_ann.add_argument("--video-id", required=True)
    p_ann.add_argument("--pattern")
    p_ann.add_argument("--genre")
    p_ann.add_argument("--hypothesis")
    p_ann.add_argument("--changed")
    p_ann.add_argument("--channel", choices=["organic", "ad"])
    p_ann.add_argument("--orders", type=int)
    p_ann.add_argument("--plays", type=int)
    p_ann.add_argument("--likes", type=int)
    p_ann.add_argument("--saves", type=int)

    p_learn = sub.add_parser("learn-pattern", help="Save a newly researched genre pattern into local_patterns.json")
    p_learn.add_argument("--patterns", default="./local_patterns.json")
    p_learn.add_argument("--id", required=True)
    p_learn.add_argument("--name", required=True)
    p_learn.add_argument("--genre", required=True)
    p_learn.add_argument("--hook", default="")
    p_learn.add_argument("--visual", default="")
    p_learn.add_argument("--source-note", default="")

    p_exp = sub.add_parser("export-candidates", help="Export verified patterns (n>=2) for OS promotion")
    p_exp.add_argument("--patterns", default="./local_patterns.json")
    p_exp.add_argument("--out", default="./os_pattern_proposals.md")

    args = parser.parse_args()
    now = dt.datetime.now(tz=JST)
    now_str = now.strftime("%Y-%m-%d %H:%M JST")

    if args.cmd == "learn-pattern":
        lp = load_json(args.patterns, {"updated_at_jst": now_str, "patterns": {}})
        existing = lp["patterns"].get(args.id, {})
        lp["patterns"][args.id] = {
            **existing,
            "id": args.id,
            "name": args.name,
            "genre": args.genre,
            "hook": args.hook,
            "visual": args.visual,
            "source_note": args.source_note,
            "status": existing.get("status", "candidate"),
            "verified_videos": existing.get("verified_videos", []),
            "retired_videos": existing.get("retired_videos", []),
            "best_plays": existing.get("best_plays", 0),
            "total_orders": existing.get("total_orders", 0),
            "updated_at_jst": now_str,
        }
        lp["updated_at_jst"] = now_str
        save_json(args.patterns, lp)
        print(f"Saved local pattern {args.id} ({args.name}) -> {args.patterns}")
        return

    if args.cmd == "export-candidates":
        cnt = export_os_candidates(args.patterns, args.out)
        print(f"Exported {cnt} OS-ready patterns -> {args.out}")
        return

    state = load_json(args.state, {"handle": "", "updated_at_jst": "", "posts": {}, "retired_patterns": [], "winning_patterns": []})

    if args.cmd == "sync":
        clean = args.handle.strip().lstrip("@")
        state["handle"] = clean
        state["updated_at_jst"] = now_str
        fetched = fetch_public_posts(clean, args.count)
        for item in fetched:
            vid = item["video_id"]
            if not vid:
                continue
            prev = state["posts"].get(vid, {})
            merged = {**prev, **item}
            age_h = (now.timestamp() - item["created_at_ts"]) / 3600.0 if item["created_at_ts"] else 0.0
            if 22 <= age_h <= 30 and "snap_24h" not in merged:
                merged["snap_24h"] = {"plays": item["play_count"], "likes": item["digg_count"], "saves": item["collect_count"], "at": now_str}
            if 46 <= age_h <= 60 and "snap_48h" not in merged:
                merged["snap_48h"] = {"plays": item["play_count"], "likes": item["digg_count"], "saves": item["collect_count"], "at": now_str}
            state["posts"][vid] = merged
        lp = promote_local_patterns(state, args.patterns, now_str)
        write_report(state, args.report, lp)
        save_json(args.state, state)
        print(f"Synced {len(fetched)} posts for @{clean} -> {args.report}")

    elif args.cmd == "annotate":
        post = state["posts"].setdefault(args.video_id, {"video_id": args.video_id, "title": "(手動登録)"})
        for field in ("pattern", "genre", "hypothesis", "changed", "channel", "orders"):
            val = getattr(args, field, None)
            if val is not None:
                post[field] = val
        if args.plays is not None:
            post["play_count"] = args.plays
        if args.likes is not None:
            post["digg_count"] = args.likes
        if args.saves is not None:
            post["collect_count"] = args.saves
        state["updated_at_jst"] = now_str
        lp = promote_local_patterns(state, args.patterns, now_str)
        write_report(state, args.report, lp)
        save_json(args.state, state)
        print(f"Annotated video {args.video_id} -> {args.report}")


if __name__ == "__main__":
    main()
