---
name: fukugyo-contract
description: 既存の業務委託契約書（txt/md/pdf）を読み込み、報酬・契約形態・リスク条項などを自動抽出するスキル。抽出した内容をconfig.jsonに反映して請求書発行に活用できる。契約書の作成は行わない。
---

# contractスキル

既存の契約書ファイルを読み込み、AIが内容を解析して報酬・契約形態などの情報を抽出・保存する。

## コマンド

```
/contract read   <ファイル>    契約書を読んで解析・保存する
/contract list                 読み込み済み契約書の一覧
/contract show   <クライアント> 特定クライアントの契約情報を表示
/contract sync   <クライアント> 抽出情報をconfig.jsonに反映する
```

---

## `/contract read` の手順

### Step 1: 契約書テキストを表示させる

```bash
python3 scripts/contract.py read 契約書.txt
```

スクリプトが契約書の内容を表示し、抽出すべき項目のリストを表示する。

### Step 2: Claude Code が内容を解析して以下を抽出する

| フィールド | 内容 |
|-----------|------|
| `client` | クライアント名（甲 or 乙の相手方） |
| `contract_type` | `hourly`（時間単価）/ `fixed`（固定）/ `mixed`（複合） |
| `hourly_rate` | 時間単価（円・税別）|
| `min_hours` / `max_hours` | 月間稼働時間の下限・上限 |
| `fixed_amount` | 固定報酬額（円・税別）|
| `payment_terms` | 支払条件（例: 月末締め翌月末払い）|
| `contract_start` / `contract_end` | 契約期間（YYYY-MM-DD）|
| `auto_renewal` | 自動更新あり（true/false）|
| `renewal_notice_days` | 更新停止の通知期間（日）|
| `ip_ownership` | 著作権帰属（`client`/`contractor`/`unclear`）|
| `nda` | 秘密保持義務あり（true/false）|
| `nda_duration_years` | 秘密保持の存続期間（年）|
| `non_compete` | 競業避止義務あり（true/false）|
| `non_compete_scope` | 競業避止の範囲・期間 |
| `subcontract_ok` | 再委託可能（true/false）|
| `liability_cap` | 損害賠償の上限 |
| `side_job_forbidden` | 副業禁止条項あり（true/false）|
| `risks` | リスク項目のリスト（文字列の配列）|
| `notes` | その他の特記事項 |

### Step 3: 抽出したデータを JSON にまとめて保存する

```bash
python3 scripts/contract.py read 契約書.txt --data '{
  "client": "株式会社A",
  "contract_type": "hourly",
  "hourly_rate": 8000,
  "min_hours": 40,
  "max_hours": 140,
  "payment_terms": "月末締め翌月末払い",
  "contract_start": "2026-04-01",
  "contract_end": null,
  "auto_renewal": true,
  "renewal_notice_days": 30,
  "ip_ownership": "client",
  "nda": true,
  "nda_duration_years": 3,
  "non_compete": false,
  "non_compete_scope": null,
  "subcontract_ok": false,
  "liability_cap": "報酬額1ヶ月分",
  "side_job_forbidden": false,
  "risks": ["著作権がクライアントに帰属（譲渡対価の記載なし）", "再委託禁止"],
  "notes": "契約更新時に単価の改定交渉が可能"
}'
```

### Step 4: config.json への反映を案内する

```bash
python3 scripts/contract.py sync 株式会社A
```

以下を config.json の clients セクションに反映できる：
- `hourly_rate`（時間単価）
- `payment_terms`（支払条件）
- `contract_date`（契約開始日）

---

## リスク判定の基準

以下に該当する場合は `risks` リストに追加し、`side_job_forbidden` などのフラグもセットする：

| 条項 | リスクレベル | 判定基準 |
|------|------------|---------|
| 著作権帰属 | 🔴高 | 「甲に帰属する」かつ譲渡対価の記載がない |
| 競業避止 | 🔴高 | 期間1年超、地域・業種の範囲が広い |
| 副業禁止 | 🔴高 | 「他の業務を行ってはならない」等の条項 |
| 損害賠償上限なし | 🟡中 | 賠償額の上限が設定されていない |
| 再委託禁止 | 🟡中 | 外注・下請け不可の制限 |
| 解除通知が短い | 🟡中 | 解除予告が1ヶ月未満 |
| 自動更新の通知期間が短い | 🟡中 | 30日未満 |
| 無償での追加対応 | 🔴高 | 仕様変更・追加作業を無償で行う義務 |

---

## 保存先

```
.fukugyo/contracts/
└── {クライアント名}.json   ← 抽出した契約情報（構造化JSON）
```

元の契約書ファイル自体は移動・コピーしない（`source_file` フィールドにパスを記録するだけ）。
