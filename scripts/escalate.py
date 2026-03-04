#!/usr/bin/env python3
"""
fukugyo escalate
未払いクライアントへの内容証明・少額訴訟・支払督促の申立書を生成する

免責: このスクリプトが生成する文書は参考用ドラフトです。
     提出前に以下の相談窓口への確認を推奨します。
     ・フリーランス・トラブル110番（無料）: https://freelance110.mhlw.go.jp/
       0120-532-110（平日9:30〜16:30）厚労省委託・弁護士対応・匿名OK
     ・法テラス（有料相談あり）: 0570-078374
"""

import json
import sys
from __future__ import annotations

import argparse
import webbrowser
from datetime import date, timedelta
from pathlib import Path

INVOICES_PATH = Path(".fukugyo/invoices.json")
ESCALATE_DIR  = Path(".fukugyo/escalate")

URL_NAIYOSHOMEI     = "https://webyubin.jpi.post.japanpost.jp/webyubin/"
URL_TOUKI           = "https://www.touki-kyoutaku-online.moj.go.jp/"
URL_TOKUSOKU_ONLINE = "https://www.courts.go.jp/saiban/tetuzuki/tokusoku/index.html"
URL_KANKATSU        = "https://www.courts.go.jp/saiban/tetuzuki/kankatsu/index.html"

SHOGAKU_LIMIT = 600_000  # 少額訴訟の請求上限


# ---- データ操作 ----------------------------------------------------------

def load_invoices() -> dict:
    if not INVOICES_PATH.exists():
        print("❌ invoices.json が見つかりません。")
        sys.exit(1)
    return json.loads(INVOICES_PATH.read_text(encoding="utf-8"))


def find_invoice(data: dict, inv_id: str) -> dict | None:
    for inv in data["invoices"]:
        if inv["id"] == inv_id:
            return inv
    return None


def load_config() -> dict:
    p = Path(".fukugyo/config.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_invoices(data: dict) -> None:
    INVOICES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---- 費用計算 ------------------------------------------------------------

def calc_stamp_suit(amount: int) -> int:
    """通常訴訟（第一審）の収入印紙額 - 民事訴訟費用等に関する法律 別表第一"""
    if amount <= 1_000_000:
        return max(1_000, ((amount + 99_999) // 100_000) * 1_000)
    elif amount <= 5_000_000:
        base = 10_000
        over = amount - 1_000_000
        return base + ((over + 199_999) // 200_000) * 1_000
    elif amount <= 10_000_000:
        base = 30_000
        over = amount - 5_000_000
        return base + ((over + 499_999) // 500_000) * 2_000
    elif amount <= 50_000_000:
        base = 50_000
        over = amount - 10_000_000
        return base + ((over + 999_999) // 1_000_000) * 3_000
    else:
        base = 170_000
        over = amount - 50_000_000
        return base + ((over + 4_999_999) // 5_000_000) * 10_000


def calc_stamp_tokusoku(amount: int) -> int:
    """支払督促の収入印紙額（通常訴訟の半額、100円単位切り捨て）"""
    return max(500, (calc_stamp_suit(amount) // 2 // 100) * 100)


def calc_stamp_shogaku(amount: int) -> int:
    """少額訴訟の収入印紙額（通常訴訟と同額）"""
    return calc_stamp_suit(amount)


def calc_postage_tokusoku(is_corp_debtor: bool = True) -> dict:
    """支払督促の郵便費用"""
    items = [
        {"item": "正本送達用封筒（債務者宛・角形2号・1,250円切手）", "amount": 1_250},
        {"item": "発付通知用封筒（自分宛・角形2号・140円切手）",     "amount": 140},
        {"item": "官製はがき（送達通知用・85円）",                    "amount": 85},
    ]
    if is_corp_debtor:
        items.append(
            {"item": "登記事項証明書（相手が法人・オンライン申請）", "amount": 500}
        )
    return {"items": items, "total": sum(i["amount"] for i in items)}


def calc_postage_shogaku(is_corp_debtor: bool = True) -> dict:
    """少額訴訟の郵便費用（予納郵券）"""
    items = [
        {"item": "予納郵券（裁判所への郵便切手）", "amount": 6_000},
    ]
    if is_corp_debtor:
        items.append(
            {"item": "登記事項証明書（相手が法人・オンライン申請）", "amount": 500}
        )
    return {"items": items, "total": sum(i["amount"] for i in items)}


# ---- 診断 ----------------------------------------------------------------

def run_start(inv_id: str) -> None:
    data   = load_invoices()
    inv    = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    today     = date.today()
    due       = date.fromisoformat(inv["due_at"])
    days_over = (today - due).days
    reminded  = len(inv.get("reminders", []))
    total     = inv["total"]
    can_shogaku = total <= SHOGAKU_LIMIT

    stamp_tok = calc_stamp_tokusoku(total)
    post_tok  = calc_postage_tokusoku(is_corp_debtor=True)
    cost_tok  = stamp_tok + post_tok["total"] + 800

    stamp_sho = calc_stamp_shogaku(total)
    post_sho  = calc_postage_shogaku(is_corp_debtor=True)
    cost_sho  = stamp_sho + post_sho["total"]

    print(f"\n{'='*60}")
    print("⚖️  エスカレーション診断")
    print(f"{'='*60}")
    print(f"請求書:       {inv_id}")
    print(f"クライアント: {inv['client']}")
    print(f"請求金額:     {total:,}円")
    print(f"支払期限:     {inv['due_at']}（{days_over}日超過）")
    print(f"督促回数:     {reminded}回")

    print(f"""
推奨手順:
  Step 1: 内容証明郵便を送付する（e内容証明でブラウザから送れます）
  Step 2: 2週間待つ
  Step 3: 法的手続きへ（下記から選択）
""")

    # 手続き比較表
    sho_available = "✅ 利用可能" if can_shogaku else f"❌ 60万円超のため利用不可"
    print("📋 法的手続きの比較")
    print(f"  {'項目':<18} {'支払督促':>14} {'少額訴訟':>14}")
    print(f"  {'─'*50}")
    print(f"  {'請求金額の上限':<18} {'上限なし':>14} {'60万円以下':>14}")
    print(f"  {'収入印紙':<18} {stamp_tok:>13,}円 {stamp_sho:>13,}円")
    print(f"  {'郵便費用等':<18} {post_tok['total']:>13,}円 {post_sho['total']:>13,}円")
    print(f"  {'合計概算':<18} {cost_tok:>13,}円 {cost_sho:>13,}円")
    print(f"  {'裁判所への出頭':<18} {'不要':>14} {'必要（1回）':>14}")
    print(f"  {'審理期間':<18} {'書面のみ':>14} {'1日で判決':>14}")
    print(f"  {'相手の異議':<18} {'→通常訴訟へ移行':>14} {'なし':>14}")
    print(f"  {'少額訴訟の可否':<18} {'─':>14} {sho_available:>14}")

    print(f"""
💡 選び方の目安:
  支払督促 → 裁判所に行きたくない・金額が60万円超・相手が払う可能性が高い
  少額訴訟 → 60万円以下・1日で決着させたい・証拠が揃っている

📞 迷ったらまず無料相談:
  フリーランス・トラブル110番 0120-532-110（平日9:30〜16:30）
  https://freelance110.mhlw.go.jp/
""")

    menu = "1: 内容証明を作成 → e内容証明をブラウザで開く\n"
    menu += "2: 支払督促の申立書を作成\n"
    if can_shogaku:
        menu += "3: 少額訴訟の申立書を作成\n"
    else:
        menu += f"3: 少額訴訟（{total:,}円は60万円超のため利用不可）\n"
    menu += "4: 登記簿謄本をオンラインで取得する\n"
    menu += "q: 終了"
    print(menu)

    choice = input("\n選択: ").strip()
    if choice == "1":
        run_letter(inv_id, _data=data)
    elif choice == "2":
        run_tokusoku(inv_id, _data=data)
    elif choice == "3" and can_shogaku:
        run_shogaku(inv_id, _data=data)
    elif choice == "3" and not can_shogaku:
        print(f"  ❌ 請求金額 {total:,}円 は60万円を超えているため少額訴訟は利用できません。")
        print("     支払督促（選択肢2）をご検討ください。")
    elif choice == "4":
        run_touki()


# ---- 内容証明 ------------------------------------------------------------

def run_letter(inv_id: str, _data: dict | None = None) -> None:
    data   = _data or load_invoices()
    config = load_config()
    inv    = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    me          = config.get("me", {})
    clients     = config.get("clients", {})
    client_info = clients.get(inv["client"], {})
    today       = date.today()
    deadline    = today + timedelta(days=14)

    letter = f"""通　知　書

                                        {today.strftime('%Y年%-m月%-d日')}

{inv['client']}
代表者 {client_info.get('representative', '御中')} 殿

        住所　{me.get('address', '')}
        氏名　{me.get('name', '')}


    通知人は、{inv['client']}（以下「貴社」といいます）との間で業務委託契約を締結し、
所定の業務を完了しました。

    当該業務に係る報酬として、{inv['issued_at']}付請求書（{inv_id}）において
金{inv['total']:,}円（消費税込）を請求し、支払期限を{inv['due_at']}と定めておりましたが、
本日現在に至るまでご入金が確認できておりません。

    つきましては、本書面到達後{deadline.strftime('%Y年%-m月%-d日')}までに
上記金員を下記口座へご送金いただけますよう通知いたします。

    万一、上記期日までにご入金またはご連絡をいただけない場合には、
支払督促の申立てその他の法的措置を講ずることをやむを得ず申し添えます。

                    記

    振込先
        銀行名：{me.get('bank', {}).get('bank_name', '')}
        支店名：{me.get('bank', {}).get('branch_name', '')}
        口座種別：{me.get('bank', {}).get('account_type', '')}
        口座番号：{me.get('bank', {}).get('account_number', '')}
        口座名義：{me.get('bank', {}).get('account_holder', '')}

                                        以　上
"""

    ESCALATE_DIR.mkdir(parents=True, exist_ok=True)
    out = ESCALATE_DIR / f"{inv_id}_内容証明.txt"
    out.write_text(letter, encoding="utf-8")

    print(f"\n{'='*60}")
    print("✉️  内容証明郵便ドラフト")
    print(f"{'='*60}")
    print(letter)
    print(f"{'='*60}")
    print(f"\n✓ {out} に保存しました")
    print("""
📮 e内容証明（郵便局Webサービス）で送れます:
   料金: 1,870円〜（配達証明付き）
   上記テキストをコピー&ペーストするだけでOKです。
""")
    ans = input("  今すぐブラウザで e内容証明 を開きますか？ [Y/n]: ").strip().lower()
    if ans != "n":
        webbrowser.open(URL_NAIYOSHOMEI)
        print(f"  ✓ ブラウザを開きました → {URL_NAIYOSHOMEI}")

    _append_timeline(inv_id, today, "内容証明郵便ドラフト作成")
    inv.setdefault("escalation", {})["letter_drafted_at"] = today.isoformat()
    save_invoices(data)


# ---- 支払督促 ------------------------------------------------------------

def run_tokusoku(inv_id: str, _data: dict | None = None) -> None:
    data   = _data or load_invoices()
    config = load_config()
    inv    = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    me          = config.get("me", {})
    clients     = config.get("clients", {})
    client_info = clients.get(inv["client"], {})
    today       = date.today()

    stamp      = calc_stamp_tokusoku(inv["total"])
    postage    = calc_postage_tokusoku(is_corp_debtor=True)
    total_cost = stamp + postage["total"] + 800

    petition = f"""支払督促申立書

請求の趣旨

１　債務者は債権者に対し、金{inv['total']:,}円を支払え。
２　申立費用は債務者の負担とする。
との支払督促を求める。


請求の原因

１　債権者は、債務者との間で{inv.get('contract_date', '（契約締結日）')}付業務委託契約を締結し、
    所定の業務を完了した。

２　債権者は、債務者に対し、{inv['issued_at']}付請求書（{inv_id}）において
    業務委託報酬として金{inv['total']:,}円（消費税込）を請求し、
    支払期限を{inv['due_at']}と定めた。

３　しかるに、債務者は支払期限を経過した現在も上記金員を支払わない。

４　よって、債権者は上記金員の支払を求めて本申立てに及ぶ。


申立手続費用

①　申立手数料（収入印紙）:         {stamp:,}円
②　正本送達費用（切手・封筒）:     1,250円
③　発付通知費用（切手・封筒）:       140円
④　申立書作成及び提出費用:           800円  ※相手方に請求可能
　　　　　　　　　　　　合計:  {stamp + 1_250 + 140 + 800:,}円


当事者目録

【債権者】
  住所: {me.get('address', '')}
  氏名: {me.get('name', '')}
  電話: {me.get('phone', '')}

【債務者】
  住所: {client_info.get('address', '（登記簿謄本で確認してください）')}
  名称: {inv['client']}
  代表者: 代表取締役 {client_info.get('representative', '（登記簿謄本で確認してください）')}
"""

    checklist = f"""# 支払督促 準備チェックリスト（{inv_id}）

## 特徴
- 請求金額の**上限なし**（少額訴訟は60万円以下のみ）
- **裁判所への出頭不要**（書面審査のみ）
- **オンライン申立可能**（督促手続オンラインシステム）
- 費用は通常訴訟の半額
- 相手が異議申立てをすると通常訴訟へ移行

## 費用まとめ

| 項目 | 金額 | 備考 |
|------|------|------|
| 申立手数料（収入印紙） | {stamp:,}円 | 通常訴訟の半額 |
| 正本送達用封筒（1,250円切手・角形2号） | 1,250円 | 債務者宛 |
| 発付通知用封筒（140円切手・角形2号） | 140円 | 自分宛 |
| 官製はがき（85円） | 85円 | 送達確認用（相手への請求不可） |
| 申立書作成及び提出費用 | 800円 | **勝訴時に相手方へ請求可能** |
| 登記事項証明書（相手が法人の場合） | 500〜600円 | 3ヶ月以内に取得 |
| **合計（概算）** | **{total_cost + 85:,}円〜** | |

## 書類チェックリスト

- [ ] 支払督促申立書（ドラフト: `.fukugyo/escalate/{inv_id}_支払督促/申立書.txt`）
- [ ] 業務委託契約書のコピー
- [ ] 請求書（{inv_id}）のコピー
- [ ] 督促メール・内容証明の記録
- [ ] 収入印紙 {stamp:,}円分（郵便局・コンビニで購入可）
- [ ] 角形2号封筒（白無地）× 2通
- [ ] 官製はがき × 1枚（表面に自分の住所・氏名を記載）
- [ ] 登記事項証明書（相手が法人の場合）← 「履歴事項全部証明書」または「代表者事項証明書」

## 申立先

相手方（{inv['client']}）の所在地を管轄する**簡易裁判所**
管轄検索: {URL_KANKATSU}

## 申立方法

| 方法 | 特徴 |
|------|------|
| **オンライン（推奨）** | 督促手続オンラインシステム。24時間・裁判所不要 |
| 郵送 | 申立書一式を郵送 |
| 窓口持参 | 簡易裁判所の窓口へ直接持参 |

## 手続きの流れ

```
申立て
  ↓（約2週間）
裁判所が支払督促を発付 → 相手方に送達
  ↓
  ├─ 相手が2週間以内に異議申立て → 通常訴訟に移行
  └─ 異議なし
        ↓（2週間後）「仮執行宣言の申立て」を行う
        ↓ 仮執行宣言付き支払督促が確定
        ↓ それでも払わない場合
        強制執行（銀行口座差押えなど）が可能
```

⚠️ 免責: この申立書は参考用ドラフトです。
📞 無料相談: フリーランス・トラブル110番 0120-532-110
   https://freelance110.mhlw.go.jp/（平日9:30〜16:30・匿名OK）
"""

    ESCALATE_DIR.mkdir(parents=True, exist_ok=True)
    suit_dir = ESCALATE_DIR / f"{inv_id}_支払督促"
    suit_dir.mkdir(exist_ok=True)
    (suit_dir / "申立書.txt").write_text(petition, encoding="utf-8")
    (suit_dir / "準備チェックリスト.md").write_text(checklist, encoding="utf-8")

    print(f"\n{'='*60}")
    print("⚖️  支払督促 申立書ドラフト")
    print(f"{'='*60}")
    print(petition)
    print(f"{'='*60}")
    print(f"✓ {suit_dir}/ に保存しました\n")
    print(f"💰 費用概算: 収入印紙 {stamp:,}円 + 郵便等 {postage['total'] + 85:,}円 = 合計 {total_cost + 85:,}円〜\n")

    ans = input("  督促手続オンラインシステムをブラウザで開きますか？ [Y/n]: ").strip().lower()
    if ans != "n":
        webbrowser.open(URL_TOKUSOKU_ONLINE)
        print(f"  ✓ ブラウザを開きました")

    ans2 = input("\n  相手方は法人ですか？登記簿謄本取得サイトを開きますか？ [Y/n]: ").strip().lower()
    if ans2 != "n":
        run_touki()

    _append_timeline(inv_id, today, "支払督促申立書ドラフト作成")
    inv.setdefault("escalation", {})["tokusoku_drafted_at"] = today.isoformat()
    save_invoices(data)


# ---- 少額訴訟 ------------------------------------------------------------

def run_shogaku(inv_id: str, _data: dict | None = None) -> None:
    data   = _data or load_invoices()
    config = load_config()
    inv    = find_invoice(data, inv_id)
    if not inv:
        print(f"❌ {inv_id} が見つかりません。")
        sys.exit(1)

    total = inv["total"]
    if total > SHOGAKU_LIMIT:
        print(f"❌ 請求金額 {total:,}円 は60万円を超えているため少額訴訟は利用できません。")
        print("   支払督促（`escalate tokusoku`）をご検討ください。")
        sys.exit(1)

    me          = config.get("me", {})
    clients     = config.get("clients", {})
    client_info = clients.get(inv["client"], {})
    today       = date.today()

    stamp      = calc_stamp_shogaku(total)
    postage    = calc_postage_shogaku(is_corp_debtor=True)
    total_cost = stamp + postage["total"]

    petition = f"""少額訴訟 訴状

                                        {today.strftime('%Y年%-m月%-d日')}

○○簡易裁判所 御中


原告  {me.get('address', '')}
      {me.get('name', '')}
      電話: {me.get('phone', '')}

被告  {client_info.get('address', '（登記簿謄本で確認してください）')}
      {inv['client']}
      代表者 代表取締役 {client_info.get('representative', '（登記簿謄本で確認してください）')}


訴訟物の価額    金{total:,}円
貼用印紙額      金{stamp:,}円


請求の趣旨

１　被告は原告に対し、金{total:,}円を支払え。
２　訴訟費用は被告の負担とする。
との判決及び仮執行宣言を求める。


請求の原因

１　原告は、被告との間で{inv.get('contract_date', '（契約締結日）')}付業務委託契約を締結し、
    所定の業務を完了した。

２　原告は、被告に対し、{inv['issued_at']}付請求書（{inv_id}）において
    業務委託報酬として金{total:,}円（消費税込）を請求し、
    支払期限を{inv['due_at']}と定めた。

３　しかるに、被告は支払期限を経過した現在も上記金員を支払わない。

４　よって、原告は上記金員の支払を求めて本訴提起に及ぶ。


証拠方法

１　甲第１号証  業務委託契約書
２　甲第２号証  請求書（{inv_id}）
３　甲第３号証  督促メール記録（スクリーンショット）
４　甲第４号証  内容証明郵便の控え


附属書類

１　訴状副本    １通
２　甲号証写し  各１通
"""

    checklist = f"""# 少額訴訟 準備チェックリスト（{inv_id}）

## 特徴
- 請求金額 **60万円以下のみ** 利用可能（今回: {total:,}円 ✅）
- **1回の審理で判決**（通常1〜2ヶ月で解決）
- 裁判所への**出頭が必要**（1回）
- 相手が出席しなければ**欠席判決**になることが多い
- 費用は通常訴訟と同額（支払督促より高い）
- 相手が「通常訴訟に移行してほしい」と申立てる権利あり

## 費用まとめ

| 項目 | 金額 | 備考 |
|------|------|------|
| 申立手数料（収入印紙） | {stamp:,}円 | 訴状に貼付 |
| 予納郵券（郵便切手） | 6,000円 | 裁判所へ予納 |
| 登記事項証明書（相手が法人の場合） | 500〜600円 | 3ヶ月以内に取得 |
| **合計（概算）** | **{total_cost:,}円〜** | |

## 書類チェックリスト

- [ ] 訴状（ドラフト: `.fukugyo/escalate/{inv_id}_少額訴訟/訴状.txt`）
- [ ] 訴状副本（訴状のコピー）× 1部
- [ ] 業務委託契約書（甲第1号証）
- [ ] 請求書 {inv_id}（甲第2号証）
- [ ] 督促メールのスクリーンショット（甲第3号証）
- [ ] 内容証明郵便の控え（甲第4号証）
- [ ] 収入印紙 {stamp:,}円分（訴状に貼付・消印しないこと）
- [ ] 郵便切手 6,000円分（裁判所ごとに組合せが異なる→要確認）
- [ ] 登記事項証明書（相手が法人の場合）

## 申立先

相手方（{inv['client']}）の所在地を管轄する**簡易裁判所**
管轄検索: {URL_KANKATSU}

## 手続きの流れ

```
訴状を簡易裁判所に提出（持参 or 郵送）
  ↓（1〜2ヶ月後）
審理期日（1回で完結・要出頭）
  ↓
  ├─ 相手が「通常訴訟へ移行」を申立て → 通常訴訟へ
  ├─ 相手が欠席 → 欠席判決（原告勝訴が多い）
  └─ 審理・証拠調べ → 判決
        ↓ それでも払わない場合
        強制執行（銀行口座差押えなど）が可能
```

## 当日の持ち物

- 本人確認書類（運転免許証・マイナンバーカード等）
- 証拠書類の原本（契約書・請求書・メール記録等）
- 印鑑

⚠️ 免責: この訴状は参考用ドラフトです。
📞 無料相談: フリーランス・トラブル110番 0120-532-110
   https://freelance110.mhlw.go.jp/（平日9:30〜16:30・匿名OK）
"""

    ESCALATE_DIR.mkdir(parents=True, exist_ok=True)
    suit_dir = ESCALATE_DIR / f"{inv_id}_少額訴訟"
    suit_dir.mkdir(exist_ok=True)
    (suit_dir / "訴状.txt").write_text(petition, encoding="utf-8")
    (suit_dir / "準備チェックリスト.md").write_text(checklist, encoding="utf-8")

    print(f"\n{'='*60}")
    print("⚖️  少額訴訟 訴状ドラフト")
    print(f"{'='*60}")
    print(petition)
    print(f"{'='*60}")
    print(f"✓ {suit_dir}/ に保存しました\n")
    print(f"💰 費用概算: 収入印紙 {stamp:,}円 + 予納郵券 6,000円 = 合計 {total_cost:,}円〜")
    print(f"   （支払督促との差額: +{total_cost - (calc_stamp_tokusoku(total) + calc_postage_tokusoku()['total'] + 800):,}円）\n")

    ans = input("\n  相手方は法人ですか？登記簿謄本取得サイトを開きますか？ [Y/n]: ").strip().lower()
    if ans != "n":
        run_touki()

    _append_timeline(inv_id, today, "少額訴訟 訴状ドラフト作成")
    inv.setdefault("escalation", {})["shogaku_drafted_at"] = today.isoformat()
    save_invoices(data)


# ---- 登記簿取得 ----------------------------------------------------------

def run_touki() -> None:
    print(f"""
🏢 登記事項証明書（登記簿謄本）のオンライン取得

  取得先: 登記・供託オンライン申請システム
  URL: {URL_TOUKI}

  費用:
    オンライン申請 + 郵送受取:       500円
    オンライン申請 + 法務局窓口受取: 480円
    窓口での申請:                     600円

  取得する書類: 「履歴事項全部証明書」または「代表者事項証明書」
  注意: 申立日から3ヶ月以内に取得したものが必要
""")
    ans = input("  今すぐブラウザで開きますか？ [Y/n]: ").strip().lower()
    if ans != "n":
        webbrowser.open(URL_TOUKI)
        print(f"  ✓ ブラウザで {URL_TOUKI} を開きました")


# ---- ユーティリティ -------------------------------------------------------

def _append_timeline(inv_id: str, dt: date, event: str) -> None:
    path = ESCALATE_DIR / f"{inv_id}_タイムライン.md"
    ESCALATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- {dt.isoformat()}  {event}\n")


# ---- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="fukugyo escalate",
        epilog="免責: 生成文書は参考用ドラフトです。相談: フリーランス・トラブル110番 0120-532-110（無料）/ 法テラス 0570-078374"
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("start",    help="エスカレーション開始（診断・費用比較・手続き選択）")
    p.add_argument("inv_id")

    p = sub.add_parser("letter",   help="内容証明を生成してe内容証明サイトを開く")
    p.add_argument("inv_id")

    p = sub.add_parser("tokusoku", help="支払督促の申立書を生成（金額上限なし・裁判所不要）")
    p.add_argument("inv_id")

    p = sub.add_parser("shogaku",  help="少額訴訟の訴状を生成（60万円以下・1回で判決）")
    p.add_argument("inv_id")

    sub.add_parser("touki",        help="登記簿謄本取得サイトを開く")

    args = parser.parse_args()

    if args.cmd == "start":
        run_start(args.inv_id)
    elif args.cmd == "letter":
        run_letter(args.inv_id)
    elif args.cmd == "tokusoku":
        run_tokusoku(args.inv_id)
    elif args.cmd == "shogaku":
        run_shogaku(args.inv_id)
    elif args.cmd == "touki":
        run_touki()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
