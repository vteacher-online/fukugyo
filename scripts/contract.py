#!/usr/bin/env python3
"""
fukugyo contract
既存の契約書ファイル（txt/md/pdf対応）を読み込み、
Claude Code（AI）が内容を解析して報酬・契約形態などを抽出・保存する

【使い方】
  python3 scripts/contract.py read   契約書.txt   # 契約書を読み込んで解析
  python3 scripts/contract.py list                # 読み込み済み契約書の一覧
  python3 scripts/contract.py show   株式会社A   # 特定クライアントの契約情報
  python3 scripts/contract.py sync   株式会社A   # 抽出情報を config.json に反映

【Claude Code との連携】
  このスクリプトは contracts/*.json に保存された解析済みデータを
  読み書きするだけです。
  実際の契約書テキストの解析（AI抽出）は SKILL.md の指示に従い
  Claude Code が行い、結果を --data オプションで渡します。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

CONFIG_PATH  = Path(".fukugyo/config.json")
CONTRACT_DIR = Path(".fukugyo/contracts")

# 抽出するフィールドの定義
CONTRACT_FIELDS = {
    "client":              "クライアント名",
    "contract_type":       "契約形態（hourly=時間単価 / fixed=固定報酬 / mixed=複合）",
    "hourly_rate":         "時間単価（円）",
    "min_hours":           "月間最低稼働時間",
    "max_hours":           "月間最大稼働時間",
    "fixed_amount":        "固定報酬額（円）",
    "payment_terms":       "支払条件（例: 月末締め翌月末払い）",
    "contract_start":      "契約開始日（YYYY-MM-DD）",
    "contract_end":        "契約終了日（YYYY-MM-DD または null）",
    "auto_renewal":        "自動更新あり（true/false）",
    "renewal_notice_days": "更新停止の通知期間（日）",
    "ip_ownership":        "著作権の帰属（client=クライアント / contractor=受託者 / unclear=不明）",
    "nda":                 "秘密保持義務あり（true/false）",
    "nda_duration_years":  "秘密保持の存続期間（年）",
    "non_compete":         "競業避止義務あり（true/false）",
    "non_compete_scope":   "競業避止の範囲・期間（文字列）",
    "subcontract_ok":      "再委託可能（true/false）",
    "liability_cap":       "損害賠償の上限（文字列、例: 報酬額1ヶ月分）",
    "side_job_forbidden":  "副業禁止条項あり（true/false）",
    "risks":               "リスク箇所の要約リスト",
    "notes":               "その他の特記事項",
    "source_file":         "元の契約書ファイルパス",
    "analyzed_at":         "解析日（YYYY-MM-DD）",
}


# ---- ユーティリティ -------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("❌ .fukugyo/config.json が見つかりません。先に setup.py を実行してください。")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def contract_path(client: str) -> Path:
    safe = client.replace("/", "_").replace(" ", "_")
    return CONTRACT_DIR / f"{safe}.json"


def load_contract(client: str) -> dict | None:
    p = contract_path(client)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_contracts() -> list[dict]:
    if not CONTRACT_DIR.exists():
        return []
    result = []
    for f in sorted(CONTRACT_DIR.glob("*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def read_contract_text(filepath: str) -> str:
    """契約書ファイルを読み込む（txt / md / pdf対応）"""
    p = Path(filepath)
    if not p.exists():
        # contracts/ フォルダを自動補完
        fallback = Path("contracts") / p.name
        if fallback.exists():
            p = fallback
        else:
            print(f"❌ ファイルが見つかりません: {filepath}")
            sys.exit(1)

    if p.suffix.lower() == ".pdf":
        # pdfminer がインストールされている場合のみ対応
        try:
            from pdfminer.high_level import extract_text
            return extract_text(str(p))
        except ImportError:
            print("⚠️  PDF読み込みには pdfminer.six が必要です:")
            print("   pip install pdfminer.six --break-system-packages")
            sys.exit(1)

    # txt / md / その他テキスト
    for enc in ("utf-8", "cp932", "shift_jis"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue

    print(f"❌ ファイルのエンコーディングを判定できませんでした: {filepath}")
    sys.exit(1)


# ---- read コマンド -------------------------------------------------------

def run_read(filepath: str, data_json: str | None = None) -> None:
    """
    契約書を読み込み、解析結果を保存する。

    Claude Code の動作:
      1. このスクリプトが契約書テキストを読んで表示する
      2. Claude Code が内容を解析して CONTRACT_FIELDS を抽出する
      3. --data オプションで JSON を渡して再実行し、結果を保存する
    """
    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)

    # --data が渡された場合 → 保存モード
    if data_json:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            print(f"❌ --data の JSON が不正です: {e}")
            sys.exit(1)

        data["source_file"] = filepath
        data["analyzed_at"] = date.today().isoformat()

        client = data.get("client", Path(filepath).stem)
        out = contract_path(client)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n✓ 解析結果を保存しました: {out}")
        _print_summary(data)

        print("\n💡 config.json に反映しますか？")
        print(f"   python3 scripts/contract.py sync {client}")
        return

    # --data なし → 契約書を読み込んで表示（Claude Code が解析する）
    text = read_contract_text(filepath)

    print(f"\n{'='*60}")
    print(f"📄 契約書の内容（{filepath}）")
    print(f"{'='*60}")
    print(text)
    print(f"{'='*60}")

    # Claude Code への指示（SKILL.md が読む）
    print(f"""
┌─────────────────────────────────────────────────────┐
│  Claude Code: 上記の契約書から以下を抽出してください  │
└─────────────────────────────────────────────────────┘

抽出項目:
""")
    for field, desc in CONTRACT_FIELDS.items():
        if field not in ("source_file", "analyzed_at"):
            print(f"  {field:<25} {desc}")

    print(f"""
抽出結果を JSON にまとめ、以下のコマンドで保存してください:

  python3 scripts/contract.py read {filepath} --data '{{抽出したJSON}}'
""")


# ---- list コマンド -------------------------------------------------------

def run_list() -> None:
    contracts = list_contracts()
    if not contracts:
        print("📋 読み込み済みの契約書はありません。")
        print("   python3 scripts/contract.py read <契約書ファイル>")
        return

    print(f"\n{'='*60}")
    print("📋 読み込み済み契約書一覧")
    print(f"{'='*60}\n")

    for c in contracts:
        client = c.get("client", "不明")
        ct     = c.get("contract_type", "不明")
        ct_label = {"hourly": "時間単価制", "fixed": "固定報酬", "mixed": "複合"}.get(ct, ct)

        rate_str = ""
        if c.get("hourly_rate"):
            rate_str = f"{c['hourly_rate']:,}円/時"
        elif c.get("fixed_amount"):
            rate_str = f"固定 {c['fixed_amount']:,}円"

        risks = c.get("risks", [])
        risk_flag = f"  ⚠️  リスク{len(risks)}件" if risks else ""

        print(f"  {client}")
        print(f"    契約形態: {ct_label}  報酬: {rate_str}  支払: {c.get('payment_terms', '不明')}")
        print(f"    期間: {c.get('contract_start', '?')} 〜 {c.get('contract_end', '定めなし')}{risk_flag}")
        print()


# ---- show コマンド -------------------------------------------------------

def run_show(client: str) -> None:
    data = load_contract(client)
    if not data:
        # 部分一致検索
        contracts = list_contracts()
        matches = [c for c in contracts if client in c.get("client", "")]
        if len(matches) == 1:
            data = matches[0]
        elif len(matches) > 1:
            print(f"⚠️  複数のクライアントが一致します:")
            for c in matches:
                print(f"   - {c.get('client')}")
            return
        else:
            print(f"❌ '{client}' の契約情報が見つかりません。")
            print(f"   python3 scripts/contract.py list  で確認してください")
            return

    print(f"\n{'='*60}")
    print(f"📄 {data.get('client')} の契約情報")
    print(f"{'='*60}\n")
    _print_summary(data)


def _print_summary(data: dict) -> None:
    ct = data.get("contract_type", "不明")
    ct_label = {"hourly": "時間単価制", "fixed": "固定報酬", "mixed": "複合"}.get(ct, ct)

    print(f"【基本情報】")
    print(f"  クライアント:   {data.get('client', '不明')}")
    print(f"  契約形態:       {ct_label}")
    print(f"  契約期間:       {data.get('contract_start', '?')} 〜 {data.get('contract_end', '定めなし')}")
    auto = "あり" if data.get("auto_renewal") else "なし"
    if data.get("auto_renewal") and data.get("renewal_notice_days"):
        auto += f"（{data['renewal_notice_days']}日前通知で停止）"
    print(f"  自動更新:       {auto}")
    print()

    print(f"【報酬・支払い】")
    if data.get("hourly_rate"):
        print(f"  時間単価:       {data['hourly_rate']:,}円/時（税別）")
    if data.get("min_hours") is not None:
        print(f"  月間稼働:       {data.get('min_hours', 0)}〜{data.get('max_hours', '?')}時間")
    if data.get("fixed_amount"):
        print(f"  固定報酬:       {data['fixed_amount']:,}円/月（税別）")
    print(f"  支払条件:       {data.get('payment_terms', '不明')}")
    print()

    print(f"【権利・義務】")
    ip = {"client": "クライアントに帰属", "contractor": "受託者に帰属", "unclear": "不明（要確認）"}.get(
        data.get("ip_ownership", ""), data.get("ip_ownership", "不明"))
    nda_str = f"あり（終了後{data['nda_duration_years']}年）" if data.get("nda") and data.get("nda_duration_years") else \
              "あり" if data.get("nda") else "なし"
    print(f"  著作権の帰属:   {ip}")
    print(f"  秘密保持:       {nda_str}")
    print(f"  競業避止:       {'あり（' + data.get('non_compete_scope', '') + '）' if data.get('non_compete') else 'なし'}")
    print(f"  再委託:         {'可能' if data.get('subcontract_ok') else '不可'}")
    print(f"  賠償の上限:     {data.get('liability_cap', '設定なし（要交渉）')}")
    print(f"  副業禁止条項:   {'⚠️ あり（要確認）' if data.get('side_job_forbidden') else 'なし'}")
    print()

    risks = data.get("risks", [])
    if risks:
        print(f"【⚠️  リスク項目（{len(risks)}件）】")
        for r in risks:
            print(f"  • {r}")
        print()

    if data.get("notes"):
        print(f"【特記事項】")
        print(f"  {data['notes']}")
        print()

    print(f"  解析日: {data.get('analyzed_at', '不明')}  元ファイル: {data.get('source_file', '不明')}")


# ---- sync コマンド -------------------------------------------------------

def run_sync(client: str, yes: bool = False) -> None:
    """
    契約書から抽出した報酬情報を config.json の clients セクションに反映する
    """
    data = load_contract(client)
    if not data:
        print(f"❌ '{client}' の契約情報が見つかりません。先に read コマンドで読み込んでください。")
        return

    cfg     = load_config()
    clients = cfg.setdefault("clients", {})
    c_name  = data.get("client", client)

    existing = clients.get(c_name, {})

    updates: dict = {}
    if data.get("hourly_rate"):
        updates["hourly_rate"] = data["hourly_rate"]
    if data.get("contract_start"):
        updates["contract_date"] = data["contract_start"]
    if data.get("payment_terms"):
        updates["payment_terms"] = data["payment_terms"]

    if not updates:
        print(f"⚠️  '{c_name}' に反映できる情報がありませんでした。")
        return

    print(f"\n以下を config.json の clients.{c_name} に反映します：\n")
    for k, v in updates.items():
        old = existing.get(k, "（未設定）")
        print(f"  {k}: {old} → {v}")

    if yes:
        ans = "y"
    else:
        ans = input("\n  反映しますか？ [Y/n]: ").strip().lower()
    if ans == "n":
        print("キャンセルしました。")
        return

    existing.update(updates)
    clients[c_name] = existing
    save_config(cfg)
    print(f"✓ config.json を更新しました")
    print(f"  次回の請求書作成から新しい単価・支払条件が使用されます")


# ---- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="fukugyo contract — 既存契約書の読み込みと情報抽出",
        epilog="相談: フリーランス・トラブル110番 0120-532-110（無料）https://freelance110.mhlw.go.jp/"
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("read",  help="契約書ファイルを読み込んでAIで解析する")
    p.add_argument("file",      help="契約書ファイルのパス（txt / md / pdf）")
    p.add_argument("--data",    help="Claude Codeが抽出したJSON（内部用）", default=None)

    sub.add_parser("list",      help="読み込み済み契約書の一覧を表示")

    p = sub.add_parser("show",  help="特定クライアントの契約情報を表示")
    p.add_argument("client",    help="クライアント名")

    p = sub.add_parser("sync",  help="抽出した報酬・支払条件をconfig.jsonに反映")
    p.add_argument("client",    help="クライアント名")
    p.add_argument("--yes", "-y", action="store_true", help="確認をスキップして反映")

    args = parser.parse_args()

    if args.cmd == "read":
        run_read(args.file, args.data)
    elif args.cmd == "list":
        run_list()
    elif args.cmd == "show":
        run_show(args.client)
    elif args.cmd == "sync":
        run_sync(args.client, yes=args.yes)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
