#!/usr/bin/env python3
"""
fukugyo setup
.fukugyo/config.json を対話形式で作成する
"""

import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path(".fukugyo/config.json")
SAMPLE_PATH = Path(".fukugyo")


def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val or default
    else:
        return input(f"  {prompt}: ").strip()


def ask_yn(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    val = input(f"  {prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val.startswith("y")


def section(title: str) -> None:
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")


def run_setup() -> None:
    print("""
╔══════════════════════════════════════════════╗
║         fukugyo セットアップ                 ║
║  副業管理スキルの初期設定を行います          ║
╚══════════════════════════════════════════════╝
""")

    config = {}

    # ---- 自分の情報 ----
    section("① あなたの情報")
    name    = ask("氏名（請求書に記載される名前）")
    address = ask("住所（例: 〒150-0001 東京都渋谷区...）")
    email   = ask("メールアドレス")
    phone   = ask("電話番号（任意）", default="")

    config["me"] = {
        "name":    name,
        "address": address,
        "email":   email,
        "phone":   phone,
    }

    # ---- インボイス登録番号 ----
    section("② インボイス登録番号（任意）")
    print("  適格請求書発行事業者の場合のみ入力してください。")
    print("  未登録の場合は空欄でOKです。")
    inv_num = ask("登録番号（例: T1234567890123）", default="")
    if inv_num:
        config["me"]["invoice_number"] = inv_num

    # ---- 銀行口座 ----
    section("③ 振込先口座")
    bank_name    = ask("銀行名（例: 三菱UFJ銀行）")
    branch_name  = ask("支店名（例: 渋谷支店）")
    account_type = ask("口座種別", default="普通")
    account_num  = ask("口座番号")
    account_holder = ask("口座名義（カタカナ）")

    config["me"]["bank"] = {
        "bank_name":       bank_name,
        "branch_name":     branch_name,
        "account_type":    account_type,
        "account_number":  account_num,
        "account_holder":  account_holder,
    }

    # ---- クライアント ----
    section("④ クライアント情報")
    print("  副業先のクライアントを登録します。後から config.json を直接編集して追加できます。")
    clients = {}
    url_patterns = []

    while True:
        print(f"\n  [{len(clients)+1}社目] ※ 登録しない場合はそのままEnter")
        client_name = ask("クライアント名（例: 株式会社A）", default="")
        if not client_name:
            break

        client_address = ask("住所（請求書の宛先）", default="")
        hourly_rate    = ask("時間単価（円）", default="")
        url_pattern    = ask("よく使うURL・ドメイン（例: github.com/client-a）", default="")

        clients[client_name] = {
            "address":         client_address,
            "hourly_rate":     int(hourly_rate.replace(",", "")) if hourly_rate else None,
            "freee_partner_id": None,
        }
        if url_pattern:
            url_patterns.append({"pattern": url_pattern, "client": client_name})

        if not ask_yn("もう1社登録しますか？", default=False):
            break

    config["clients"]     = clients
    config["url_patterns"] = url_patterns

    # ---- Slack ----
    section("⑤ Slack連携")
    use_slack = ask_yn("Slackを勤怠管理に使いますか？")
    if use_slack:
        print("\n  チャンネルIDとクライアントの対応を登録します。")
        print("  チャンネルIDはSlackのチャンネルURLから確認できます。")
        print("  （例: https://app.slack.com/client/T0000/C01234ABCD → C01234ABCD）")

        slack_user_id = ask("あなたのSlack UserID（例: U01234ABCD）", default="")
        config["me"]["slack_user_id"] = slack_user_id

        slack_channels = {}
        for client_name in clients:
            ch_id = ask(f"  {client_name} のチャンネルID（不明ならEnter）", default="")
            if ch_id:
                slack_channels[ch_id] = client_name

        config["slack_channels"] = slack_channels
        config["checkin_keywords"]  = ["おはよう", "おはようございます", "出勤", "始めます", "よろしくお願いします"]
        config["checkout_keywords"] = ["おつかれ", "おつかれさまでした", "退勤", "終わります", "上がります", "失礼します"]
    else:
        config["slack_channels"]    = {}
        config["checkin_keywords"]  = []
        config["checkout_keywords"] = []

    # ---- freee ----
    section("⑥ freee連携（任意）")
    print("  freee MCPが接続されている場合、請求書をfreeeに直接登録できます。")
    print("  セットアップ: npx freee-mcp configure")
    use_freee = ask_yn("freeeを使いますか？", default=False)
    config["freee"] = {
        "enabled":   use_freee,
        "company_id": None,
        "item_name": "業務委託費",
        "tax_code":  1,
    }

    # ---- 支払条件 ----
    section("⑦ 支払条件")
    terms = ask("デフォルトの支払条件", default="月末締め翌月末払い")
    config["default_payment_terms"] = terms
    config["default_tax_rate"]      = 0.10

    # ---- 保存 ----
    section("確認")
    print()
    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()

    if not ask_yn("この内容で保存しますか？"):
        print("セットアップをキャンセルしました。")
        sys.exit(0)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"""
✅ セットアップ完了！

  設定ファイル: {CONFIG_PATH}

次のステップ:
  python3 scripts/timecard.py today      # 今日の勤怠を取得
  python3 scripts/invoice.py create      # 先月の請求書を発行
  python3 scripts/payment.py check       # 入金状況を確認
""")


if __name__ == "__main__":
    run_setup()
