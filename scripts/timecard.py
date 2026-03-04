#!/usr/bin/env python3
"""
fukugyo timecard
Slack MCP（Claude Code経由）+ Chrome履歴 から勤怠を自動生成する

【Slackデータの受け取り方】
  このスクリプトは Slack API を直接叩きません。
  Claude Code が Slack MCP を通じてメッセージを取得し、
  環境変数 FUKUGYO_SLACK_DATA（JSON）に格納してからこのスクリプトを呼び出します。

  FUKUGYO_SLACK_DATA の形式:
    {
      "株式会社A": { "checkin": "2026-03-04T09:12:00", "checkout": "2026-03-04T18:30:00" },
      "株式会社B": { "checkin": "2026-03-04T10:00:00", "checkout": null }
    }

【Slack Bot Token の設定】
  README の「Slack MCP のセットアップ」を参照してください。
  Bot Token は Claude Code の MCP 設定ファイル（~/.claude/settings.json）に書きます。
  config.json には書きません。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ---- 設定 ----------------------------------------------------------------

CONFIG_PATH   = Path(".fukugyo/config.json")
TIMECARD_PATH = Path(".fukugyo/timecard.json")
CHROME_TMP    = Path("/tmp/fukugyo_chrome_history")

LOCAL_TZ = ZoneInfo("Asia/Tokyo")


# ---- 設定ファイル ---------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("❌ .fukugyo/config.json が見つかりません。")
        print("   先に python3 scripts/setup.py を実行してください。")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


# ---- Slack データ（Claude Code + Slack MCP から環境変数で注入） ----------

def fetch_slack_times(
    target_date: date,
    config: dict,
) -> dict[str, tuple[datetime | None, datetime | None]]:
    """
    Claude Code が Slack MCP を通じて取得したデータを環境変数から受け取る。

    Claude Code は SKILL.md の指示に従い以下を行う：
      1. config.json の slack.channels に登録されたチャンネルIDを確認
      2. 各チャンネルで自分（slack.my_user_id）の当日投稿を Slack MCP で取得
      3. checkin_keywords / checkout_keywords に一致する投稿の時刻を抽出
      4. FUKUGYO_SLACK_DATA 環境変数に JSON で格納してこのスクリプトを呼び出す

    スタンドアロン実行（環境変数なし）の場合は空を返し、Chrome 履歴のみで動作する。
    """
    slack_json = os.environ.get("FUKUGYO_SLACK_DATA")
    if not slack_json:
        return {}

    try:
        raw = json.loads(slack_json)
        result: dict[str, tuple[datetime | None, datetime | None]] = {}
        for client, times in raw.items():
            checkin  = datetime.fromisoformat(times["checkin"])  if times.get("checkin")  else None
            checkout = datetime.fromisoformat(times["checkout"]) if times.get("checkout") else None
            result[client] = (checkin, checkout)
            status = []
            if checkin:  status.append(f"出勤 {checkin.strftime('%H:%M')}")
            if checkout: status.append(f"退勤 {checkout.strftime('%H:%M')}")
            if status:
                print(f"  Slack [{client}] {' / '.join(status)}")
        return result
    except Exception as e:
        print(f"⚠️  FUKUGYO_SLACK_DATA の解析に失敗しました: {e}")
        return {}


# ---- Chrome 履歴 ----------------------------------------------------------

def chrome_history_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library/Application Support/Google/Chrome"
    elif system == "Windows":
        base = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data"
    else:
        base = Path.home() / ".config/google-chrome"

    # Default を最初に試す
    default = base / "Default" / "History"
    if default.exists():
        return default

    # Default がなければ最終更新が最も新しいプロファイルを使う
    candidates = sorted(
        base.glob("Profile */History"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    return default  # 存在しなくても元のパスを返してエラーを出す


def fetch_chrome_history(target_date: date) -> list[dict]:
    src = chrome_history_path()
    if not src.exists():
        print(f"⚠️  Chrome履歴が見つかりません: {src}")
        return []

    try:
        shutil.copy2(src, CHROME_TMP)
    except PermissionError:
        print("⚠️  Chrome履歴をコピーできません。Chromeを閉じてから再実行してください。")
        return []

    date_str = target_date.isoformat()
    query = f"""
        SELECT
            datetime(last_visit_time/1000000 - 11644473600, 'unixepoch', 'localtime') AS visited_at,
            url,
            title,
            visit_count
        FROM urls
        WHERE visited_at >= '{date_str} 00:00:00'
          AND visited_at <  '{date_str} 23:59:59'
          AND url NOT LIKE 'chrome://%'
          AND url NOT LIKE 'chrome-extension://%'
          AND url NOT LIKE 'about:%'
        ORDER BY last_visit_time ASC
    """

    entries = []
    try:
        con = sqlite3.connect(str(CHROME_TMP))
        for row in con.execute(query):
            visited_at_str, url, title, visit_count = row
            try:
                dt = datetime.strptime(visited_at_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            try:
                hostname = url.split("/")[2].removeprefix("www.")
            except Exception:
                hostname = ""
            entries.append({
                "visited_at": dt,
                "url":        url,
                "title":      title or "",
                "domain":     hostname,
            })
        con.close()
    except sqlite3.Error as e:
        print(f"⚠️  Chrome履歴の読み取りエラー: {e}")

    return entries


# ---- クライアント特定 -----------------------------------------------------

def identify_client(url: str, url_patterns: list[dict]) -> str | None:
    for pat in url_patterns:
        if pat["pattern"] in url:
            return pat["client"]
    return None


def group_chrome_by_client(entries: list[dict], url_patterns: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for e in entries:
        client = identify_client(e["url"], url_patterns)
        if client:
            result.setdefault(client, []).append(e)
    return result


# ---- 作業内容の推定 -------------------------------------------------------

DOMAIN_LABELS = [
    ("github.com",        lambda url, title: _github_label(url, title)),
    ("atlassian.net",     lambda url, title: f"チケット対応 ({_jira_key(url)})"),
    ("figma.com",         lambda url, title: "デザイン確認"),
    ("docs.google.com",   lambda url, title: "ドキュメント作業"),
    ("sheets.google.com", lambda url, title: "スプレッドシート作業"),
    ("localhost",         lambda url, title: "ローカル開発・動作確認"),
    ("127.0.0.1",         lambda url, title: "ローカル開発・動作確認"),
    ("vercel.app",        lambda url, title: "ステージング確認"),
    ("netlify.app",       lambda url, title: "ステージング確認"),
    ("slack.com",         lambda url, title: "Slackコミュニケーション"),
    ("notion.so",         lambda url, title: "ドキュメント作業"),
    ("linear.app",        lambda url, title: "チケット対応"),
]

def _github_label(url: str, title: str) -> str:
    if "/pull/"    in url: return "PRレビュー・マージ"
    if "/issues/"  in url: return "Issue対応"
    if "/commit/"  in url: return "コードレビュー"
    if "/actions/" in url: return "CI/CD確認"
    return "GitHub作業"

def _jira_key(url: str) -> str:
    parts = url.split("/browse/")
    return parts[1].split("?")[0] if len(parts) > 1 else ""

def summarize_work(entries: list[dict]) -> str:
    labels = []
    seen = set()
    for e in entries:
        for d, fn in DOMAIN_LABELS:
            if d in e["domain"]:
                label = fn(e["url"], e["title"])
                if label not in seen:
                    labels.append(label)
                    seen.add(label)
                break
    return "、".join(labels) if labels else "作業内容不明"


# ---- 時刻解決ロジック -----------------------------------------------------

def resolve_times(
    slack_checkin: datetime | None,
    slack_checkout: datetime | None,
    chrome_entries: list[dict],
) -> tuple[datetime | None, str, datetime | None, str]:
    chrome_first = chrome_entries[0]["visited_at"]  if chrome_entries else None
    chrome_last  = chrome_entries[-1]["visited_at"] if chrome_entries else None

    start, start_src = _pick_time(slack_checkin,  chrome_first, "早い方優先")
    end,   end_src   = _pick_time(slack_checkout, chrome_last,  "遅い方優先")

    return start, start_src, end, end_src


def _pick_time(
    slack_dt: datetime | None,
    chrome_dt: datetime | None,
    strategy: str,
) -> tuple[datetime | None, str]:
    if slack_dt and chrome_dt:
        diff = abs((slack_dt - chrome_dt).total_seconds())
        if diff <= 1800:  # 30分以内 → Chrome優先（より正確）
            return chrome_dt, "Chrome履歴"
        if strategy == "早い方優先":
            return (chrome_dt, "Chrome履歴") if chrome_dt < slack_dt else (slack_dt, "Slack投稿")
        else:
            return (chrome_dt, "Chrome履歴") if chrome_dt > slack_dt else (slack_dt, "Slack投稿")
    if slack_dt:  return slack_dt,  "Slack投稿"
    if chrome_dt: return chrome_dt, "Chrome履歴"
    return None, "取得不可"


# ---- メイン処理 -----------------------------------------------------------

def run_timecard(target_date: date, dry_run: bool = False, yes: bool = False) -> None:
    config       = load_config()
    url_patterns = config.get("url_patterns", [])

    print(f"\n📅 {target_date.strftime('%Y-%m-%d')} の勤怠を取得中...\n")

    # Slack データ（Claude Code + Slack MCP が環境変数に注入）
    slack_times = fetch_slack_times(target_date, config)
    if not slack_times:
        slack_cfg = config.get("slack", {})
        if slack_cfg.get("channels"):
            print("  ℹ️  Slack MCP 未接続 → Chrome履歴のみで動作します")
            print("     Slack連携: README の「Slack MCP のセットアップ」を参照してください")
    if slack_times:
        print()

    # Chrome 履歴
    chrome_entries   = fetch_chrome_history(target_date)
    chrome_by_client = group_chrome_by_client(chrome_entries, url_patterns)

    all_clients = sorted(set(chrome_by_client.keys()) | set(slack_times.keys()))

    if not all_clients:
        print("⚠️  この日の作業記録が見つかりませんでした。")
        print("   ・Slack MCP が接続されているか確認してください")
        print("   ・config.json の url_patterns を確認してください")
        return

    entries  = []
    warnings = []

    for client in all_clients:
        c_entries          = chrome_by_client.get(client, [])
        slack_ci, slack_co = slack_times.get(client, (None, None))

        start, start_src, end, end_src = resolve_times(slack_ci, slack_co, c_entries)

        if start is None or end is None:
            warnings.append(f"{client}: 開始または終了時刻が取得できませんでした")
            continue

        minutes = int((end - start).total_seconds() / 60)
        if minutes <= 0:
            warnings.append(f"{client}: 開始と終了が逆転しています（スキップ）")
            continue

        work_desc = summarize_work(c_entries)
        entries.append({
            "client":      client,
            "start":       start,
            "start_src":   start_src,
            "end":         end,
            "end_src":     end_src,
            "minutes":     minutes,
            "description": work_desc,
        })

        h, m = divmod(minutes, 60)
        print(f"【{client}】")
        print(f"  開始: {start.strftime('%H:%M')}  ({start_src})")
        print(f"  終了: {end.strftime('%H:%M')}  ({end_src})")
        print(f"  稼働: {h}時間{m:02d}分")
        print(f"  作業: {work_desc}")
        print()

    total_min = sum(e["minutes"] for e in entries)
    th, tm = divmod(total_min, 60)
    print(f"合計稼働: {th}時間{tm:02d}分")

    if warnings:
        print()
        for w in warnings:
            print(f"⚠️  {w}")

    if dry_run or not entries:
        return

    print()
    if yes:
        answer = "y"
    else:
        answer = input("この内容で保存しますか？ [y/n/修正(e)]: ").strip().lower()
    if answer == "e":
        entries = interactive_fix(entries)
        answer = "y"
    if answer != "y":
        print("保存をキャンセルしました。")
        return

    save_entries(target_date, entries)
    print(f"✓ .fukugyo/timecard.json に保存しました")


def interactive_fix(entries: list[dict]) -> list[dict]:
    print("\n--- 修正モード ---")
    for i, e in enumerate(entries):
        print(f"\n[{i+1}] {e['client']}")
        print(f"  開始: {e['start'].strftime('%H:%M')}  終了: {e['end'].strftime('%H:%M')}")
        if input("  修正しますか？ [y/n]: ").strip().lower() == "y":
            new_start = input(f"  新しい開始時刻 (HH:MM) [{e['start'].strftime('%H:%M')}]: ").strip()
            new_end   = input(f"  新しい終了時刻 (HH:MM) [{e['end'].strftime('%H:%M')}]: ").strip()
            date_part = e["start"].date()
            if new_start:
                h, m = map(int, new_start.split(":"))
                e["start"] = datetime(date_part.year, date_part.month, date_part.day, h, m)
                e["start_src"] = "手動修正"
            if new_end:
                h, m = map(int, new_end.split(":"))
                e["end"] = datetime(date_part.year, date_part.month, date_part.day, h, m)
                e["end_src"] = "手動修正"
            e["minutes"] = int((e["end"] - e["start"]).total_seconds() / 60)
    return entries


def save_entries(target_date: date, entries: list[dict]) -> None:
    TIMECARD_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = {"entries": []}
    if TIMECARD_PATH.exists():
        existing = json.loads(TIMECARD_PATH.read_text(encoding="utf-8"))

    date_str = target_date.isoformat()
    existing["entries"] = [e for e in existing["entries"] if e["date"] != date_str]

    for e in entries:
        existing["entries"].append({
            "date":        date_str,
            "client":      e["client"],
            "start":       e["start"].strftime("%H:%M"),
            "end":         e["end"].strftime("%H:%M"),
            "minutes":     e["minutes"],
            "description": e["description"],
            "sources": {
                "start_source": e["start_src"],
                "end_source":   e["end_src"],
                "note":         "",
            }
        })

    TIMECARD_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ---- 月次集計 ------------------------------------------------------------

def run_month_summary(year: int, month: int) -> None:
    if not TIMECARD_PATH.exists():
        print("❌ timecard.json が見つかりません。先に timecard.py today を実行してください。")
        return

    data    = json.loads(TIMECARD_PATH.read_text(encoding="utf-8"))
    prefix  = f"{year:04d}-{month:02d}"
    entries = [e for e in data["entries"] if e["date"].startswith(prefix)]

    if not entries:
        print(f"⚠️  {prefix} の記録がありません。")
        return

    summary: dict[str, dict] = {}
    for e in entries:
        c = e["client"]
        summary.setdefault(c, {"total_minutes": 0, "entries": []})
        summary[c]["total_minutes"] += e["minutes"]
        summary[c]["entries"].append(e)

    print(f"\n📊 {prefix} 月次集計\n")
    for client, data_c in summary.items():
        h, m = divmod(data_c["total_minutes"], 60)
        print(f"【{client}】 {h}時間{m:02d}分")

    result = {
        "month":   prefix,
        "summary": [
            {
                "client":        c,
                "total_minutes": v["total_minutes"],
                "total_hours":   round(v["total_minutes"] / 60, 2),
                "entries":       v["entries"],
            }
            for c, v in summary.items()
        ]
    }
    out = Path(f".fukugyo/month_{prefix}.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {out} に保存しました（invoice.py create {prefix} で使用可能）")


# ---- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="fukugyo timecard",
        epilog="Slack連携: README の「Slack MCP のセットアップ」を参照してください"
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("today",     help="今日の勤怠を取得・保存")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップして保存")

    p = sub.add_parser("yesterday", help="昨日の勤怠を取得・保存")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップして保存")

    p = sub.add_parser("date",      help="指定日の勤怠を取得・保存（YYYY-MM-DD）")
    p.add_argument("date_str")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップして保存")

    sub.add_parser("week",          help="今週の集計を表示（保存なし）")

    p = sub.add_parser("month",     help="月次集計（省略で先月）")
    p.add_argument("month_str", nargs="?", help="YYYY-MM")

    args = parser.parse_args()

    if args.cmd in ("today", None):
        run_timecard(date.today(), dry_run=getattr(args, "dry_run", False), yes=getattr(args, "yes", False))
    elif args.cmd == "yesterday":
        run_timecard(date.today() - timedelta(days=1), dry_run=args.dry_run, yes=args.yes)
    elif args.cmd == "date":
        run_timecard(date.fromisoformat(args.date_str), dry_run=args.dry_run, yes=args.yes)
    elif args.cmd == "week":
        today  = date.today()
        monday = today - timedelta(days=today.weekday())
        for i in range((today - monday).days + 1):
            run_timecard(monday + timedelta(days=i), dry_run=True)
    elif args.cmd == "month":
        if args.month_str:
            y, m = map(int, args.month_str.split("-"))
        else:
            today = date.today()
            m = today.month - 1 or 12
            y = today.year if today.month > 1 else today.year - 1
        run_month_summary(y, m)


if __name__ == "__main__":
    main()
