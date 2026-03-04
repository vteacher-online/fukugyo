#!/usr/bin/env python3
"""
fukugyo payment
請求書の入金状況を管理し、督促メールを生成する
"""

from __future__ import annotations

import argparse
import webbrowser
import json
import sys
from datetime import date, datetime
from pathlib import Path

INVOICES_PATH = Path(".fukugyo/invoices.json")

# 入金確認ブラウザURL（config.jsonのpayment_check_urlで上書き可能）
DEFAULT_PAYMENT_CHECK_URL = "https://secure.freee.co.jp/"


# ---- データ操作 ----------------------------------------------------------

def load_invoices() -> dict:
    if not INVOICES_PATH.exists():
        print("❌ invoices.json が見つかりません。先に /invoice create を実行してください。")
        sys.exit(1)
    return json.loads(INVOICES_PATH.read_text(encoding="utf-8"))


def save_invoices(data: dict) -> None:
    INVOICES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def find_invoice(data: dict, inv_id: str) -> dict | None:
    for inv in data["invoices"]:
        if inv["id"] == inv_id:
            return inv
    return None


# ---- 入金状況の確認 -------------------------------------------------------

def run_check() -> None:
    data   = load_invoices()
    config = _load_config()
    invs   = data.get("invoices", [])
    today  = date.today()

    # ブラウザで入金確認
    check_url = config.get("payment_check_url", "")
    use_freee = config.get("freee", {}).get("enabled", False)
    url = check_url or (DEFAULT_PAYMENT_CHECK_URL if use_freee else "")

    if url:
        ans = input(f"  ブラウザで入金状況を確認しますか？ [{url}] [Y/n]: ").strip().lower()
        if ans != "n":
            webbrowser.open(url)
            print(f"  ✓ ブラウザを開きました。確認後、入金済みのものは `payment paid [ID]` で記録してください。\n")
    else:
        ans = input("  ブラウザで通帳・口座を確認しますか？ [y/N]: ").strip().lower()
        if ans == "y":
            print("  💡 config.json に \"payment_check_url\" を設定すると次回から自動で開けます。")
            print("     例: \"payment_check_url\": \"https://secure.freee.co.jp/\"")
        print()

    paid     = [i for i in invs if i["status"] == "入金済"]
    pending  = [i for i in invs if i["status"] != "入金済" and date.fromisoformat(i["due_at"]) >= today]
    overdue  = [i for i in invs if i["status"] != "入金済" and date.fromisoformat(i["due_at"]) <  today]

    print(f"\n💰 入金状況  ({today.strftime('%Y年%-m月%-d日')} 現在)\n")

    if paid:
        print("✅ 入金済み")
        for inv in paid:
            print(f"   {inv['id']}  {inv['client']}  {inv['total']:,}円  {inv['paid_at']} 入金")
        print()

    if pending:
        print("⏳ 入金待ち（期日前）")
        for inv in pending:
            due = date.fromisoformat(inv["due_at"])
            days_left = (due - today).days
            print(f"   {inv['id']}  {inv['client']}  {inv['total']:,}円  期限: {inv['due_at']}（残{days_left}日）")
        print()

    if overdue:
        print("🔴 期日超過")
        for inv in overdue:
            due       = date.fromisoformat(inv["due_at"])
            days_over = (today - due).days
            reminded  = len(inv.get("reminders", []))
            print(f"   {inv['id']}  {inv['client']}  {inv['total']:,}円  期限: {inv['due_at']}（{days_over}日超過）  督促{reminded}回")

            # 次のアクションを提案
            if reminded == 0:
                ans = input(f"   → 督促メール（1回目）を生成しますか？ [y/n]: ").strip().lower()
                if ans == "y":
                    run_remind(inv["id"], _data=data)
            elif reminded >= 3:
                print(f"   → 督促3回済。`python3 scripts/escalate.py start {inv['id']}` を検討してください。")
        print()

    if not invs:
        print("請求書がありません。")


# ---- 入金済みマーク -------------------------------------------------------

def run_paid(inv_id: str) -> None:
    data = load_invoices()
    inv  = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    inv["status"]  = "入金済"
    inv["paid_at"] = date.today().isoformat()
    save_invoices(data)
    print(f"✓ {inv_id}（{inv['client']}）を入金済みにしました。")


# ---- 督促メール生成 -------------------------------------------------------

REMIND_TEMPLATES = {
    1: {
        "subject": "【ご確認】請求書のお支払いについて（{inv_id}）",
        "body": """{client_salutation}

いつもお世話になっております。{sender}です。

{issued_date}付でお送りした請求書（{inv_id}、{total_yen}）について、
本日時点でご入金の確認ができておりません。

お手続き中でしたら恐れ入ります。
お手すきの際にご確認いただけますと幸いです。

ご不明な点がございましたら、お気軽にご連絡ください。
よろしくお願いいたします。

{sender}
{sender_email}"""
    },
    2: {
        "subject": "【再送・ご確認】請求書のお支払いについて（{inv_id}）",
        "body": """{client_salutation}

お世話になっております。{sender}です。

先般（{first_remind_date}）お送りしたご連絡について、
ご返信・ご入金をまだ確認できておりません。

改めてご確認いただけますでしょうか。

■ 請求書情報
  請求書番号: {inv_id}
  請求金額:   {total_yen}
  支払期限:   {due_date}（{days_over}日超過）
  振込先:     {bank_info}

ご対応が難しい事情がございましたら、ご一報いただけると助かります。
引き続きよろしくお願いいたします。

{sender}
{sender_email}"""
    },
    3: {
        "subject": "【重要】請求書未払いのご対応について（{inv_id}）",
        "body": """{client_salutation}

お世話になっております。{sender}です。

{inv_id}（{total_yen}、支払期限: {due_date}）について、
{days_over}日が経過した現在もご入金が確認できておりません。
また、過去2回のご連絡（{first_remind_date}、{second_remind_date}）に対しても
ご返答をいただけていない状況です。

誠に恐れ入りますが、{deadline}までにご入金またはご連絡いただけない場合、
法的措置を含む対応を検討せざるを得ない状況です。

お早めのご対応をお願いいたします。

{sender}
{sender_email}"""
    },
}


def run_remind(inv_id: str, _data: dict | None = None) -> None:
    data = _data or load_invoices()
    inv  = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    config  = _load_config()
    me      = config.get("me", {})
    clients = config.get("clients", {})

    reminders  = inv.get("reminders", [])
    level      = len(reminders) + 1

    if level > 3:
        print(f"⚠️  督促は3回までです。`python3 scripts/escalate.py start {inv_id}` を実行してください。")
        return

    today    = date.today()
    due      = date.fromisoformat(inv["due_at"])
    days_over = (today - due).days
    deadline = date(today.year, today.month + 1 if today.month < 12 else 1,
                    today.day).isoformat()

    bank = me.get("bank", {})
    bank_info = (f"{bank.get('bank_name','')} {bank.get('branch_name','')} "
                 f"{bank.get('account_type','')} {bank.get('account_number','')}"
                 f"（{bank.get('account_holder','')}）")

    tmpl = REMIND_TEMPLATES[level]

    ctx = {
        "inv_id":            inv_id,
        "client_salutation": f"{inv['client']}\nご担当者様",
        "sender":            me.get("name", ""),
        "sender_email":      me.get("email", ""),
        "issued_date":       inv.get("issued_at", ""),
        "total_yen":         f"{inv['total']:,}円",
        "due_date":          inv["due_at"],
        "days_over":         str(days_over),
        "bank_info":         bank_info,
        "first_remind_date": reminders[0]["sent_at"] if len(reminders) >= 1 else "",
        "second_remind_date": reminders[1]["sent_at"] if len(reminders) >= 2 else "",
        "deadline":          deadline,
    }

    subject = tmpl["subject"].format(**ctx)
    body    = tmpl["body"].format(**ctx)

    print(f"\n{'='*60}")
    print(f"督促メール（{level}回目）")
    print(f"{'='*60}")
    print(f"件名: {subject}")
    print(f"{'-'*60}")
    print(body)
    print(f"{'='*60}\n")

    # 送信済みとして記録
    inv.setdefault("reminders", []).append({
        "sent_at": today.isoformat(),
        "level":   level,
    })
    inv["status"] = "督促中"
    save_invoices(data)
    print(f"✓ 督促{level}回目を記録しました（{inv_id}）")

    if level == 3:
        print(f"\n⚠️  3回目の督促です。")
        print(f"   次のステップ: python3 scripts/escalate.py start {inv_id}")


def _load_config() -> dict:
    p = Path(".fukugyo/config.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


# ---- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="fukugyo payment")
    sub    = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="入金状況を確認")

    p_paid = sub.add_parser("paid", help="入金済みにマーク")
    p_paid.add_argument("inv_id")

    p_remind = sub.add_parser("remind", help="督促メールを生成")
    p_remind.add_argument("inv_id")

    args = parser.parse_args()

    if args.cmd == "check" or args.cmd is None:
        run_check()
    elif args.cmd == "paid":
        run_paid(args.inv_id)
    elif args.cmd == "remind":
        run_remind(args.inv_id)


if __name__ == "__main__":
    main()
