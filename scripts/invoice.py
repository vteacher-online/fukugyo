#!/usr/bin/env python3
"""
fukugyo invoice
timecardの月次集計から請求書を生成する

freee MCPが接続されている場合はfreeeに直接登録する。
未接続の場合はMarkdownファイルとして出力する。

freee MCP連携:
  Claude Codeから実行する場合、Claude Codeが自動的に
  freee MCPツール（freee_auth_status, freee_api_post等）を
  呼び出してfreeeへの登録を行う。
  このスクリプトはMCP未接続時のMarkdownフォールバックを担当する。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

CONFIG_PATH   = Path(".fukugyo/config.json")
INVOICES_PATH = Path(".fukugyo/invoices.json")
INVOICE_DIR   = Path(".fukugyo/invoices")


# ---- 設定 ----------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("❌ .fukugyo/config.json が見つかりません。")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_month_data(month_str: str) -> dict:
    path = Path(f".fukugyo/month_{month_str}.json")
    if not path.exists():
        print(f"❌ {path} が見つかりません。")
        print(f"   先に `python3 scripts/timecard.py month {month_str}` を実行してください。")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


# ---- 請求書番号 -----------------------------------------------------------

def next_invoice_id(month_str: str) -> str:
    """INV-YYYY-MM-001 形式の連番を生成"""
    existing = load_invoices()
    prefix = f"INV-{month_str}-"
    nums = [
        int(inv["id"].split("-")[-1])
        for inv in existing.get("invoices", [])
        if inv["id"].startswith(prefix)
    ]
    seq = max(nums, default=0) + 1
    return f"{prefix}{seq:03d}"


def load_invoices() -> dict:
    if INVOICES_PATH.exists():
        return json.loads(INVOICES_PATH.read_text(encoding="utf-8"))
    return {"invoices": []}


def save_invoices(data: dict) -> None:
    INVOICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    INVOICES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ---- 支払期限の計算 -------------------------------------------------------

def calc_due_date(issued: date, terms: str) -> date:
    """
    '月末締め翌月末払い' などの文字列から支払期限を計算する
    対応: 月末締め翌月末払い / 月末締め翌々月末払い / 当月末払い
    """
    import calendar

    if "翌々月末" in terms:
        m = issued.month + 2
        y = issued.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        last = calendar.monthrange(y, m)[1]
        return date(y, m, last)
    elif "翌月末" in terms:
        m = issued.month + 1
        y = issued.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        last = calendar.monthrange(y, m)[1]
        return date(y, m, last)
    else:  # 当月末
        last = calendar.monthrange(issued.year, issued.month)[1]
        return date(issued.year, issued.month, last)


# ---- Markdown生成 --------------------------------------------------------

def render_invoice_md(
    inv_id: str,
    client_name: str,
    client_info: dict,
    me: dict,
    issued: date,
    due: date,
    hours: float,
    rate: int | None,
    fixed_amount: int | None,
    tax_rate: float,
    invoice_number: str | None,
    description: str,
) -> str:
    # 金額計算
    if rate and not fixed_amount:
        subtotal = int(hours * rate)
        qty_str  = f"{hours}時間"
        unit_str = f"{rate:,}円"
        item_label = description
    elif fixed_amount:
        subtotal = fixed_amount
        qty_str  = "1式"
        unit_str = f"{fixed_amount:,}円"
        item_label = description
    else:
        subtotal = 0
        qty_str = unit_str = item_label = "（未設定）"

    tax     = int(subtotal * tax_rate)
    total   = subtotal + tax

    # インボイス表記
    invoice_line = ""
    if invoice_number:
        invoice_line = f"\n適格請求書発行事業者登録番号: {invoice_number}"

    # クライアント住所
    client_addr = client_info.get("address", "")

    # インボイス制度対応: 税率区分ごとの合計・税額（国税庁要件⑤⑥）
    # 業務委託費は軽減税率(8%)対象外のため10%のみ
    tax_section = f"""| 10%対象合計 | | | {subtotal:,}円 |
| 消費税（10%） | | | {tax:,}円 |
| **合計（税込）** | | | **{total:,}円** |"""

    # 適格請求書の表題（登録番号がある場合のみ）
    title = "適格請求書（請求書）" if invoice_number else "請　求　書"
    inv_num_line = f"\n適格請求書発行事業者登録番号: {invoice_number}" if invoice_number else ""

    lines = f"""# {title}

請求書番号: {inv_id}
発行日: {issued.strftime('%Y年%-m月%-d日')}
支払期限: {due.strftime('%Y年%-m月%-d日')}

---

## 請求先

{client_name}  
{client_addr}  
御中

## 請求元

{me['name']}  
{me.get('address', '')}  {inv_num_line}

---

## 請求内容

| 件名 | 数量 | 単価 | 税率 | 金額（税抜） |
|------|------|------|------|------------|
| {item_label} | {qty_str} | {unit_str} | 10% | {subtotal:,}円 |

|  |  |  |  |  |
|--|--|--|--|--|
{tax_section}

---

## お振込先

銀行名: {me.get('bank', {}).get('bank_name', '')}  
支店名: {me.get('bank', {}).get('branch_name', '')}  
口座種別: {me.get('bank', {}).get('account_type', '')}  
口座番号: {me.get('bank', {}).get('account_number', '')}  
口座名義: {me.get('bank', {}).get('account_holder', '')}  

---

*本請求書に関するお問い合わせは {me.get('email', me['name'])} までご連絡ください。*
"""
    return lines, subtotal, tax, total


# ---- メイン処理 ----------------------------------------------------------

def run_create(month_str: str) -> None:
    config   = load_config()
    me       = config["me"]
    tax_rate = config.get("default_tax_rate", 0.10)
    terms    = config.get("default_payment_terms", "月末締め翌月末払い")
    clients  = config.get("clients", {})  # クライアント詳細情報

    month_data = load_month_data(month_str)
    issued     = date.today()
    due        = calc_due_date(issued, terms)

    INVOICE_DIR.mkdir(parents=True, exist_ok=True)
    invoices_db = load_invoices()

    print(f"\n📄 {month_str} の請求書を作成します\n")
    print(f"  発行日:   {issued.strftime('%Y年%-m月%-d日')}")
    print(f"  支払期限: {due.strftime('%Y年%-m月%-d日')}  ({terms})\n")

    created = []

    def next_id() -> str:
        prefix = f"INV-{month_str}-"
        existing_nums = [
            int(inv["id"].split("-")[-1])
            for inv in invoices_db.get("invoices", [])
            if inv["id"].startswith(prefix)
        ]
        seq = max(existing_nums, default=0) + 1
        return f"{prefix}{seq:03d}"

    for summary in month_data["summary"]:
        client_name = summary["client"]
        total_hours = summary["total_hours"]
        client_info = clients.get(client_name, {})

        print(f"【{client_name}】 {total_hours}時間")

        rate = client_info.get("hourly_rate")
        if not rate:
            rate_input = input(f"  時間単価 (円): ").strip()
            if rate_input:
                rate = int(rate_input.replace(",", ""))
            else:
                print("  ⚠️  単価未入力のためスキップします")
                continue

        inv_id = next_id()
        inv_num = me.get("invoice_number")

        # 作業内容の説明文
        desc = f"業務委託費（{month_str.replace('-', '年')}月分）"

        md, subtotal, tax, total = render_invoice_md(
            inv_id       = inv_id,
            client_name  = client_name,
            client_info  = client_info,
            me           = me,
            issued       = issued,
            due          = due,
            hours        = total_hours,
            rate         = rate,
            fixed_amount = None,
            tax_rate     = tax_rate,
            invoice_number = inv_num,
            description  = desc,
        )

        # 保存
        filename = INVOICE_DIR / f"{inv_id}_{client_name}.md"
        filename.write_text(md, encoding="utf-8")

        # 台帳に追記
        invoices_db["invoices"].append({
            "id":        inv_id,
            "client":    client_name,
            "month":     month_str,
            "amount":    subtotal,
            "tax":       tax,
            "total":     total,
            "issued_at": issued.isoformat(),
            "due_at":    due.isoformat(),
            "status":    "未入金",
            "paid_at":   None,
            "reminders": [],
            "file":      str(filename),
        })

        print(f"  請求書番号: {inv_id}")
        print(f"  請求金額:   {subtotal:,}円 + 消費税{tax:,}円 = {total:,}円")
        print(f"  保存先:     {filename}\n")
        created.append(inv_id)

    save_invoices(invoices_db)

    if created:
        print(f"✓ {len(created)}件の請求書を作成しました")
        print(f"  入金管理: python3 scripts/payment.py check")


def run_list() -> None:
    data = load_invoices()
    invs = data.get("invoices", [])
    if not invs:
        print("請求書がありません。")
        return

    print(f"\n{'ID':<20} {'クライアント':<15} {'合計':>10} {'期限':<12} {'状態'}")
    print("-" * 72)
    for inv in sorted(invs, key=lambda x: x["id"], reverse=True):
        status_icon = {"未入金": "⏳", "入金済": "✅", "督促中": "🔴"}.get(inv["status"], "❓")
        print(f"{inv['id']:<20} {inv['client']:<15} {inv['total']:>9,}円  {inv['due_at']:<12} {status_icon} {inv['status']}")


# ---- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="fukugyo invoice")
    sub    = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create", help="請求書を作成")
    p_create.add_argument("month_str", nargs="?", help="YYYY-MM（省略で先月）")

    sub.add_parser("list", help="請求書一覧")

    args = parser.parse_args()

    if args.cmd == "create" or args.cmd is None:
        if hasattr(args, "month_str") and args.month_str:
            month_str = args.month_str
        else:
            d = date.today()
            m = d.month - 1 or 12
            y = d.year if d.month > 1 else d.year - 1
            month_str = f"{y:04d}-{m:02d}"
        run_create(month_str)

    elif args.cmd == "list":
        run_list()


if __name__ == "__main__":
    main()
