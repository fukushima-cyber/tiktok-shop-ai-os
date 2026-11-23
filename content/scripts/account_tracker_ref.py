#!/usr/bin/env python3
"""
TikTok Shop AI運用OS：自アカウント自動集計 & 48h PDCA トラッカー（Skill 07 用）

使い方:
  # 1) 初回・定期の公開投稿集計（ログイン不要の公開APIを利用）
  python3 account_tracker_ref.py sync --handle @your_account --state ./account_state.json --report ./account_report.md

  # 2) 投稿前・投稿後に「型・仮説・注文数(CV)」を台帳へ紐づける
  python3 account_tracker_ref.py annotate --state ./account_state.json --video-id 7700... --pattern "P15xS08" --hypothesis "弱点3つ先出しで保存率改善" --changed "型" --channel organic --orders 2

注意点（制約）:
  - 再生・いいね・保存・シェア・コメント・投稿日時は公開データ（tikwm公開API）から自動取得します。
  - TikTok Shopの注文数（CV）・カートクリック数は非公開データのため自動取得できません。
    annotate コマンド（またはチャットでの1行回答）で追記して3段階PDCA判定を完成させます。
  - 公開APIがWAFや仕様変更で一時的に取得できない場合は、推測で数値を埋めずエラーを返します。
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys
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

    if age_h < 48.0:
        return (f"計測中（経過{age_h:.1f}h）", "48時間到達後に最終判定")

    plays = int(post.get("play_count") or 0)
    likes = int(post.get("digg_count") or 0)
    saves = int(post.get("collect_count") or 0)
    orders = post.get("orders")  # None if unconfirmed
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


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"handle": "", "updated_at_jst": "", "posts": {}, "retired_patterns": [], "winning_patterns": []}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def write_report(state: dict, report_path: str) -> None:
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
        if ("48時間" not in status) and (orders is None):
            need_orders.append(f"`{p['video_id']}` ({p['title'][:24]})")

        date_s = (p.get("created_at_jst") or "")[:16].replace("T", " ")
        title_s = (p.get("title") or "(無題)").replace("|", "／")[:30]
        lines.append(
            f"| {date_s} | {title_s} | {ch} | `{pat}` | {plays:,} | {lr} | {sr} | {orders_str} | {status} | {action} |"
        )

    state["retired_patterns"] = sorted(retired)
    state["winning_patterns"] = sorted(winning)

    lines += [
        "",
        "## 次回企画（Skill 02）へ自動引き継ぎする制約",
        f"- **勝ち型（横展開候補）**：{', '.join(state['winning_patterns']) or 'まだなし'}",
        f"- **撤退済み型（二度と使わない）**：{', '.join(state['retired_patterns']) or 'まだなし'}",
        f"- **直近使用型（新規企画では避ける）**：{', '.join(used_recent[:5]) or '未記録'}",
        "",
        "## 依頼者への確認（非公開の注文数だけ）",
        f"- TikTok Shop管理画面の注文数が未確認の動画：{', '.join(need_orders[:5]) if need_orders else 'なし'}",
    ]

    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok account tracker for 48h PDCA")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Fetch public posts and update PDCA ledger/report")
    p_sync.add_argument("--handle", required=True, help="TikTok handle e.g. @example")
    p_sync.add_argument("--state", default="./account_state.json")
    p_sync.add_argument("--report", default="./account_report.md")
    p_sync.add_argument("--count", type=int, default=30)

    p_ann = sub.add_parser("annotate", help="Record pattern/hypothesis/orders for a video")
    p_ann.add_argument("--state", default="./account_state.json")
    p_ann.add_argument("--report", default="./account_report.md")
    p_ann.add_argument("--video-id", required=True)
    p_ann.add_argument("--pattern")
    p_ann.add_argument("--hypothesis")
    p_ann.add_argument("--changed")
    p_ann.add_argument("--channel", choices=["organic", "ad"])
    p_ann.add_argument("--orders", type=int)

    args = parser.parse_args()
    state = load_state(args.state)
    now = dt.datetime.now(tz=JST)

    if args.cmd == "sync":
        clean = args.handle.strip().lstrip("@")
        state["handle"] = clean
        state["updated_at_jst"] = now.strftime("%Y-%m-%d %H:%M JST")
        fetched = fetch_public_posts(clean, args.count)
        for item in fetched:
            vid = item["video_id"]
            if not vid:
                continue
            prev = state["posts"].get(vid, {})
            # Preserve manual annotations (pattern, hypothesis, orders, 24h/48h snapshots)
            merged = {**prev, **item}
            age_h = (now.timestamp() - item["created_at_ts"]) / 3600.0 if item["created_at_ts"] else 0.0
            if 22 <= age_h <= 30 and "snap_24h" not in merged:
                merged["snap_24h"] = {"plays": item["play_count"], "likes": item["digg_count"], "saves": item["collect_count"], "at": state["updated_at_jst"]}
            if 46 <= age_h <= 60 and "snap_48h" not in merged:
                merged["snap_48h"] = {"plays": item["play_count"], "likes": item["digg_count"], "saves": item["collect_count"], "at": state["updated_at_jst"]}
            state["posts"][vid] = merged
        write_report(state, args.report)
        save_state(args.state, state)
        print(f"Synced {len(fetched)} posts for @{clean} -> {args.report}")

    elif args.cmd == "annotate":
        post = state["posts"].setdefault(args.video_id, {"video_id": args.video_id, "title": "(手動登録)"})
        if args.pattern is not None:
            post["pattern"] = args.pattern
        if args.hypothesis is not None:
            post["hypothesis"] = args.hypothesis
        if args.changed is not None:
            post["changed"] = args.changed
        if args.channel is not None:
            post["channel"] = args.channel
        if args.orders is not None:
            post["orders"] = args.orders
        state["updated_at_jst"] = now.strftime("%Y-%m-%d %H:%M JST")
        write_report(state, args.report)
        save_state(args.state, state)
        print(f"Annotated video {args.video_id} -> {args.report}")


if __name__ == "__main__":
    main()
