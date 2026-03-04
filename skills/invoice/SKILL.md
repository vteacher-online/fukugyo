---
name: fukugyo-invoice
description: 副業の請求書を自動発行するスキル。timecardの月次集計データから請求書を生成する。freee MCPが接続されていればfreeeに直接登録する。未接続の場合はMarkdownで出力する。インボイス制度対応（適格請求書）。複数クライアントへの一括発行も可能。
---

# invoiceスキル

`/timecard month` の集計データをもとに請求書を発行する。

**freee MCP（`freee-mcp`）が接続されている場合は freee に直接登録する。**
未接続の場合は Markdown ファイルとして出力する。

## コマンド

```
/invoice create [YYYY-MM]   指定月の請求書を作成（省略すると先月分）
/invoice list               発行済み請求書の一覧
/invoice status             入金状況の確認
```

---

## `/invoice create` の手順

### Step 1: データ取得

`.fukugyo/timecard.json` から指定月のデータを読み込む。
なければ「先に `/timecard month` を実行してください」と促す。

### Step 2: freee MCP の接続確認

`freee_auth_status` ツールを呼び出して freee MCP の接続状態を確認する。

- **接続済み** → Step 3a（freee登録フロー）へ
- **未接続またはMCP未インストール** → Step 3b（Markdownフォールバック）へ

### Step 3a: freee に直接登録（MCP接続時）

#### 事前準備

1. `freee_get_current_company` で事業所IDを取得し、`company_id` を確定する
2. `freee_api_get /api/1/partners` で取引先一覧を取得し、クライアント名から `partner_id` を特定する
   - 見つからない場合は `freee_api_post /api/1/partners` で新規作成する
3. `freee_api_get /api/1/items` で品目一覧を取得し、「業務委託費」に相当する `item_id` を特定する
   - なければ新規作成する

#### 請求書の登録

請求書APIリファレンスを参照する。ここに使用方法やエンドポイントが掲載されている。
https://developer.freee.co.jp/reference/iv/reference 

`freee_api_post /api/1/invoices` を呼び出す：

```json
{
  "company_id": "{company_id}",
  "issue_date": "{today}",
  "due_date": "{due_date}",
  "partner_id": "{partner_id}",
  "invoice_layout": "default_classic",
  "tax_entry_method": "inclusive",
  "invoice_contents": [
    {
      "order": 1,
      "type": "normal",
      "qty": "{total_hours}",
      "unit": "時間",
      "unit_price": "{hourly_rate}",
      "description": "業務委託費（{YYYY}年{MM}月分）",
      "tax_code": 1
    }
  ]
}
```

登録成功後、freeeが発行した `invoice_id` と `invoice_number` を `.fukugyo/invoices.json` に記録する。

#### 入金確認との連携

freee登録済みの請求書は `/payment check` 実行時に `freee_api_get /api/1/invoices/{invoice_id}` で入金状況を確認できる。

### Step 3b: Markdownで出力（MCP未接続時）

`.fukugyo/config.json` の `me` セクションと稼働データをもとに請求書Markdownを生成：

```
請求書番号: INV-{YYYY}-{MM}-{連番3桁}
発行日: 当日
支払期限: config.jsonのデフォルト支払条件から自動計算
```

`config.json` に `invoice_number` が設定されている場合は適格請求書として出力する。

生成後に保存：
```
.fukugyo/invoices/INV-2026-03-001_{クライアント名}.md
```

同時に `.fukugyo/invoices.json` の台帳に追記する。

---

## invoices.json の形式

```json
{
  "invoices": [
    {
      "id": "INV-2026-03-001",
      "client": "株式会社A",
      "amount": 396000,
      "tax": 36000,
      "total": 432000,
      "issued_at": "2026-03-31",
      "due_at": "2026-04-30",
      "status": "未入金",
      "paid_at": null
    }
  ]
}
```

---

## 請求書の出力形式

Markdown形式で生成する。必要であれば `pandoc` でPDF変換する（環境にあれば）。

```markdown
# 請 求 書

請求書番号: INV-2026-03-001
発行日: 2026年3月31日
支払期限: 2026年4月30日

## 請求先
株式会社A
〒100-0001 東京都...

## 請求元
山田太郎
〒150-0001 東京都...
登録番号: T1234567890123

---

| 件名 | 数量 | 単価 | 金額 |
|------|------|------|------|
| システム開発業務（2026年3月分）| 72時間 | 5,000円 | 360,000円 |

小計: 360,000円
消費税（10%）: 36,000円
**合計: 396,000円**

---

お振込先
銀行名: ○○銀行
支店名: ○○支店
口座種別: 普通
口座番号: 1234567
口座名義: ヤマダ タロウ
```
