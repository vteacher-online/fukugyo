# fukugyo — 副業・フリーランスの雑務をAIに任せる

> 「今月何時間働いた？」「請求書どう作る？」「振り込まれてない…」
> そういう面倒ごとを、AIにやってもらうためのスキルです。

## 1ヶ月のスケジュールまとめ

```
新しい案件が来たとき
  └─ /fukugyo-contract 株式会社A契約書.pdf   ← 契約書を読ませる

毎日やること
  └─ /fukugyo-timecard   ← 今日の稼働を記録（Slack MCPと連携可能）

月末
  ├─ /fukugyo-timecard-month   ← 今月の稼働をまとめる
  └─ /fukugyo-invoice   ← 請求書を発行（freee MCPと連携可能）

支払期日を過ぎたら
  └─ /fukugyo-payment    ← 入金確認・督促メール生成

それでも払わないなら
  └─ /fukugyo-escalate [請求書ID]   ← 法的手続きの準備
```

## このツールでできること

副業・フリーランスをしていると、毎月こんな作業が発生します。

| よくある悩み | fukugyo がやること |
|-------------|-------------------|
| 今月の稼働時間がわからない | Slackの挨拶やChromeの履歴から集計 |
| 請求書を毎月手で作っている | コマンド1つで発行（インボイス制度対応） |
| 先方の契約書、単価はどこに書いてある？ | 契約書ファイルを渡せばAIが読んで教えてくれる |
| 振り込まれていない… | 検知して督促メールの文面を生成 |
| 督促しても無視される | 内容証明・支払督促の申立書まで生成 |

## インストール手順

### 1. Claude Code をインストールする（まだの人）

公式サイトの手順に従ってインストールしてください。
https://docs.anthropic.com/en/docs/claude-code/overview

インストール後、ターミナルで `claude` と入力して起動できればOKです。

### 2. Python が入っているか確認する

ターミナルで以下を実行してください：

```bash
python3 --version
```

`Python 3.11.x` のように表示されればOKです。
Mac には最初から入っています。表示されない場合は https://www.python.org からインストールしてください。

### 3. fukugyo をインストールする

ターミナルで以下を実行してください：

```bash
npx skills add vteacher-online/fukugyo -a claude-code
npx skills add vteacher-online/fukugyo/skills/contract -a claude-code
npx skills add vteacher-online/fukugyo/skills/escalate -a claude-code
npx skills add vteacher-online/fukugyo/skills/invoice -a claude-code
npx skills add vteacher-online/fukugyo/skills/payment -a claude-code
npx skills add vteacher-online/fukugyo/skills/timecard -a claude-code
```

> 💡 `npx` が「コマンドが見つかりません」と言われたら、Node.js のインストールが必要です。
> https://nodejs.org からインストールしてください（LTS版を選んでください）。

### 4. 初回セットアップ（最初の1回だけ）

Claude Code を開いて、以下を入力してください：

```
/fukugyo
```

質問が順番に出てくるので、答えていくだけです。

```
あなたの名前を入力してください: 山田太郎
住所を入力してください: 〒150-0001 東京都渋谷区...
メールアドレス: yamada@example.com
振込先の銀行名: ○○銀行
...
```

入力した情報は **あなたのパソコンに保存されます**。

**後から設定を変えたいときは？**

もう一度 `/fukugyo-setup` を実行するか、`.fukugyo/config.json` というファイルを直接テキストエディタで開いて編集してください。

よく変更するもの：

| 変えたいもの | config.json の場所 |
|-------------|-------------------|
| 自分の名前・住所 | `me.name` / `me.address` |
| 振込先口座 | `me.bank` の各項目 |
| インボイス登録番号 | `me.invoice_number` |
| 時間単価 | `clients.クライアント名.hourly_rate` |
| 支払条件 | `clients.クライアント名.payment_terms` |
| Slackの出勤キーワード | `checkin_keywords`（後述） |
| Slackの退勤キーワード | `checkout_keywords`（後述） |
| 入金確認に開くURL | `payment_check_url`（後述） |

## 毎月の使い方

### ＜毎日＞ 今日の稼働を記録する

```
/fukugyo-timecard
```

これだけです。
Slackで「おはようございます」「おつかれさまでした」と投稿していれば、その時刻が出退勤として記録されます。
Slackを使っていなくても、Chromeの閲覧履歴から作業時間を推定します。

> ⚠️ Chromeを使っている方へ：Chromeを開いたまま実行するとエラーになります。
> 実行前に一度Chromeを閉じてください。

**「おはようございます」以外の言葉で出退勤したい場合**

`.fukugyo/config.json` を開いて、以下の部分を自分の言葉に書き換えてください：

```json
"checkin_keywords":  ["おはよう", "おはようございます", "出勤", "始めます"],
"checkout_keywords": ["おつかれ", "おつかれさまでした", "退勤", "終わります", "上がります"]
```

たとえば英語で使いたい場合：

```json
"checkin_keywords":  ["gm", "good morning", "start"],
"checkout_keywords": ["gn", "bye", "done for today"]
```

リストの中のどれかひとつが投稿に含まれていれば、出退勤として認識されます。

### ＜月初めに新しい案件が来たとき＞ 契約書を読ませる

先方から受け取った契約書（PDF）があれば、そのまま渡すだけでAIが読み解いてくれます。

契約書は `contracts/` フォルダに置いてください（`.gitignore` 設定済みで git には含まれません）：

```
📁 contracts/          ← このプロジェクトフォルダ内
├── 株式会社A契約書.pdf
├── 株式会社B業務委託契約書.pdf
└── 株式会社C_NDA.pdf
```

```
/fukugyo-contract contracts/株式会社A契約書.pdf
```

AIが自動で以下を読み取ってくれます：

- 時間単価はいくらか
- 月の稼働時間の上限・下限はあるか
- 支払いはいつ（月末締め翌月末払い、など）
- 著作権は誰のものか
- 副業禁止・競業避止などの危険な条項がないか

読み取った内容は保存されて、請求書の発行にも自動で使われます。

### ＜月末＞ 稼働をまとめて請求書を発行する

**ステップ1：今月の稼働をまとめる**

```
/fukugyo-timecard-month
```

クライアントごとに「今月○○時間」とまとめてくれます。

**ステップ2：請求書を発行する**

```
/fukugyo-invoice
```

先月分の請求書が自動で作られます。インボイス登録番号があれば「適格請求書」として出力されます。
ファイルは `.fukugyo/invoices/` フォルダに保存されます。

特定の月を指定したい場合：

```
/fukugyo-invoice 2026-03
```

### ＜支払期日を過ぎたとき＞ 入金確認・督促

```
/fukugyo-payment
```

実行すると最初に「ブラウザで口座を確認しますか？」と聞いてきます。`y` を押すと、あらかじめ設定したネットバンクやfreeeのログイン画面が自動で開きます。

**ブラウザで開く先を設定するには**

`.fukugyo/config.json` に `payment_check_url` を追記してください：

```json
"payment_check_url": "https://login.rakuten-bank.co.jp/"
```

主要なネットバンクのURLはこちら（使っている銀行のURLをコピーしてください）：

| 銀行 | URL |
|------|-----|
| freee | `https://secure.freee.co.jp/` |
| 三菱UFJ | `https://direct.bk.mufg.jp/` |
| 三井住友 | `https://www.smbc.co.jp/kojin/direct/` |
| みずほ | `https://www.mizuhobank.co.jp/direct/` |
| ゆうちょ | `https://www.jp-bank.japanpost.jp/` |
| 楽天銀行 | `https://www.rakuten-bank.co.jp/` |
| PayPay銀行 | `https://www.paypay-bank.co.jp/` |
| 住信SBI | `https://www.netbk.co.jp/contents/` |
| auじぶん銀行 | `https://www.jibunbank.co.jp/` |

> 💡 上記以外の銀行も、ネットバンキングのログイン画面のURLをそのまま設定すればOKです。

口座を確認して入金されていたら：

```
/fukugyo-payment-paid INV-2026-03-001
```

まだ入金されていなければ、督促メールの文面を生成します。督促は3段階で状況に合わせて文面が変わります：

- **1回目**（期日直後）：やんわり確認する文面
- **2回目**（1週間後）：はっきり催促する文面
- **3回目**（2週間後）：法的措置を示唆する文面

### ＜督促しても無視されるとき＞ 法的対応

3回督促しても無視される場合は、法的手続きに進めます。

```
/fukugyo-escalate INV-2026-03-001
```

実行すると、状況を診断して2つの選択肢を費用込みで提示してくれます：

**支払督促**（おすすめ・金額の上限なし）
- 裁判所に行かなくていい
- オンラインで申立できる
- 費用の目安：数千円〜

**少額訴訟**（60万円以下の場合）
- 1回の審理で判決が出る
- 裁判所への出頭が1回必要
- 費用の目安：1万円前後〜

どちらを選んでも、必要な書類（内容証明・申立書など）を自動で作成してくれます。

> ⚠️ 生成される書類は参考用ドラフトです。
> 不安な方は下記の無料相談窓口をご利用ください。

## 🔒 安全性について

**個人情報や口座番号の保存場所について**  
入力した口座番号・住所・クライアント情報などは、すべてあなたのパソコン内の `.fukugyo/` というフォルダに保存されます。

**Slack の Bot Token について**  
Slackと連携する場合、「Bot Token」という認証キーが必要になります。
このキーは `.fukugyo/` フォルダではなく、Claude Code 専用の設定ファイルに保存します。これにより、このツールのスクリプトが直接キーを扱わない仕組みになっています。

**Chromeの履歴について**  
Chrome の履歴は、あなたのパソコン内のファイルをローカルで読み取るだけです。どこにも送信しません。

**GitHub に公開するときは**  
このリポジトリを GitHub に公開しても、`.gitignore` の設定により `.fukugyo/` フォルダは自動的に除外されます。口座番号などが誤ってアップロードされることはありません。

## Slack との連携設定（任意）

Slackを使っていない方はこのセクションはスキップできます。

Slackと連携すると、朝「おはようございます」と投稿するだけで自動的に出勤時刻が記録されます。

### 設定の流れ（6ステップ）

**ステップ1：Slack App を作る**

1. https://api.slack.com/apps を開く
2. 右上の「Create New App」をクリック
3. 「From scratch」を選ぶ
4. App Name に `fukugyo-bot` と入力、ワークスペースを選んで「Create App」

**ステップ2：権限を設定する**

左メニューの「OAuth & Permissions」を開き、「Bot Token Scopes」に以下を追加：

| スコープ | 用途 |
|---------|------|
| `channels:history` | パブリックチャンネルの投稿を読む |
| `groups:history` | プライベートチャンネルの投稿を読む |
| `mpim:history` | グループDMの投稿を読む |
| `im:history` | ダイレクトメッセージを読む |
| `channels:read` | チャンネル一覧を取得する |
| `groups:read` | プライベートチャンネル一覧を取得する |

> ⚠️ **スコープを変更した後は必ず再インストールが必要です。**
> スコープを追加しただけでは反映されません。必ずステップ3の「Reinstall to Workspace」を行ってください。

**ステップ3：ワークスペースにインストール（または再インストール）する**

「Install to Workspace」または「Reinstall to Workspace」ボタンをクリック → 権限を許可する。
表示される **Bot User OAuth Token**（`xoxb-` で始まる長い文字列）をコピーしてください。

> 🔒 このトークンは次のステップで書きます。他の人に見せないでください。
>
> ℹ️ スコープを変更するたびに新しいトークンが発行されます。`.mcp.json` のトークンも忘れずに更新してください。

**ステップ4：Botをチャンネルに招待する**

勤怠を記録したいSlackチャンネルを開いて、以下を入力：

```
/invite @fukugyo-bot
```

**ステップ5：MCP の設定ファイルに書く**

fukugyo のプロジェクトフォルダにある `.mcp.json` を開いて（なければ作成して）、以下を記述します：

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "ここにさっきコピーしたxoxb-...のトークンを貼る",
        "SLACK_TEAM_ID":   "TXXXXXXXXのようなID"
      }
    }
  }
}
```

> 💡 `.mcp.json` はプロジェクト単位の設定ファイルです。このプロジェクトフォルダで Claude Code を起動すると自動で読み込まれます。
> 全プロジェクト共通にしたい場合は `~/.claude/settings.json` に同じ内容を書いてもOKです。

`SLACK_TEAM_ID` の調べ方：Slackでワークスペース名をクリック →「設定と管理」→「ワークスペースの設定」→ URLに含まれる `T` から始まるIDです。

**ステップ6：fukugyo の設定ファイルにチャンネル情報を書く**

`.fukugyo/config.json` を開いて `slack` セクションに以下を追加：

```json
"slack": {
  "my_user_id": "UXXXXXXXXのようなID",
  "channels": {
    "CXXXXXXXXのようなID": "株式会社A",
    "CYYYYYYYYのようなID": "株式会社B"
  }
}
```

`my_user_id` の調べ方：Slackで自分のアイコンをクリック →「プロフィール」→「…（その他）」→「メンバーIDをコピー」

チャンネルIDの調べ方：チャンネル名を右クリック →「チャンネル詳細を表示」→ 一番下に表示

## Slack 連携のトラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `invalid_auth` | トークンが無効または期限切れ | Slack API で Bot Token を再確認・再生成 |
| `missing_scope` | 必要な権限がない | ステップ2のスコープを追加 → **Reinstall to Workspace** → `.mcp.json` のトークンを更新 |
| `channel_not_found` | Bot がチャンネルに未参加 | チャンネルで `/invite @fukugyo-bot` を実行 |
| データが取得できない | Slack MCP は接続済みだがメッセージなし | `checkin_keywords` / `checkout_keywords` の設定を確認 |

> ⚠️ **よくある落とし穴：スコープ追加後の再インストール忘れ**
> OAuth & Permissions でスコープを追加しても、「Reinstall to Workspace」を押さないと新しいスコープは有効になりません。
> 再インストール後は新しいトークンが発行されるので、`.mcp.json` のトークンも必ず更新してください。

## freee との連携設定（任意）

freeeを使って請求書を管理している方は連携できます。連携すると、請求書発行と同時に freee にも自動登録されます。

```bash
npx freee-mcp configure
```

表示される手順に従って設定してください。
freeeを使っていなくても、Markdownファイルとして請求書が出力されるので問題ありません。

## よくある質問

**Q. インストールしたらどこに何が保存されますか？**

A. 作業フォルダ内に `.fukugyo/` というフォルダが作られ、その中に設定・勤怠記録・請求書がすべて保存されます。

**Q. Slackを使っていなくても使えますか？**

A. 使えます。その場合はChromeの閲覧履歴から作業時間を推定します。

**Q. freeeを使っていなくても使えますか？**

A. 使えます。請求書はMarkdownファイルとして `.fukugyo/invoices/` に保存されます。

**Q. クライアントが増えたときはどうすればいいですか？**

A. `/fukugyo-setup` をもう一度実行するか、`.fukugyo/config.json` を直接開いて追記してください。

**Q. 請求書の単価を変えたいときは？**

A. `.fukugyo/config.json` の中の `hourly_rate` という数字を変更してください。または `/fukugyo-contract-sync クライアント名` で契約書から再取得することもできます。

## 法的な相談窓口

報酬の未払いや契約トラブルで困ったときは、無料で弁護士に相談できる窓口があります。

### フリーランス・トラブル110番（無料・匿名OK）

厚生労働省が委託している、フリーランス専門の相談窓口です。弁護士が対応してくれます。

- 電話：**0120-532-110**（平日 9:30〜16:30）
- メール相談もあり（2〜3営業日で返信）
- 和解のあっせんまで無料でやってくれます
- https://freelance110.mhlw.go.jp/

### 法テラス

- 電話：0570-078374（月〜金 9:00〜21:00、土 9:00〜17:00）
- https://www.houterasu.or.jp/

## 注意事項

- 内容証明・支払督促申立書・少額訴訟の訴状は**参考用のドラフト**です。実際に提出する前に弁護士に確認してください。
- 契約書から抽出した情報もAIによる解析のため、重要な判断は必ず原文を確認してください。

## ライセンス

MIT
