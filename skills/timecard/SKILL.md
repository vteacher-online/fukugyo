---
name: fukugyo-timecard
description: 副業の勤怠を自動記録するスキル。Slack MCP でチェックイン・アウト投稿を取得し、Chrome閲覧履歴で時刻と作業内容を補完する。Slack MCPが未接続の場合はChrome履歴のみで動作する。
---

# timecardスキル

Slack MCPとChrome閲覧履歴を組み合わせて、副業の勤怠を自動記録する。

## データソースの役割分担

- **Slack MCP** → 出退勤時刻の取得（どのクライアントの仕事かはチャンネルで判定）
- **Chrome履歴** → 正確な作業時刻の補完・作業内容の推定

---

## コマンド

```
/timecard today      今日の勤怠を取得・表示・保存
/timecard yesterday  昨日分
/timecard week       今週の集計
/timecard month      今月の集計（請求書作成用）
```

---

## 実行手順

### Step 1: 設定ファイルの確認

`.fukugyo/config.json` を読み込む。`slack` セクションを確認する。

```json
{
  "slack": {
    "my_user_id": "UXXXXXXXX",
    "channels": {
      "CXXXXXXXX": "株式会社A",
      "CYYYYYYYY": "株式会社B"
    }
  },
  "checkin_keywords":  ["おはよう", "おはようございます", "出勤", "始めます"],
  "checkout_keywords": ["おつかれ", "おつかれさまでした", "退勤", "終わります", "上がります"]
}
```

### Step 2: Slack MCP でメッセージを取得する

Slack MCPが利用可能な場合、以下を行う：

1. `config.json` の `slack.channels` に登録されているチャンネルIDを確認する
2. 各チャンネルで当日のメッセージを Slack MCP の `slack_get_channel_history` ツールで取得する
3. `slack.my_user_id` と一致するメッセージだけ絞り込む
4. `checkin_keywords` に一致する最初の投稿 → チェックイン時刻
5. `checkout_keywords` に一致する最後の投稿 → チェックアウト時刻
6. チャンネルIDから `slack.channels` でクライアント名を解決する

結果を以下の JSON 形式にまとめ、`FUKUGYO_SLACK_DATA` 環境変数にセットして `timecard.py` を呼び出す：

```json
{
  "株式会社A": { "checkin": "2026-03-04T09:12:00", "checkout": "2026-03-04T18:30:00" },
  "株式会社B": { "checkin": "2026-03-04T10:00:00", "checkout": null }
}
```

呼び出し例：
```bash
FUKUGYO_SLACK_DATA='{"株式会社A":{"checkin":"2026-03-04T09:12:00","checkout":"2026-03-04T18:30:00"}}' \
  python3 scripts/timecard.py today
```

Slack MCPが利用できる場合であってもエラー（ invalid_authなど）になる場合は、curlで直接Slack APIを叩いて取得する。SLACK_BOT_TOKENは `.mcp.json` などから取得する。SLACK_BOT_TOKENは正しいことを前提とする。
curlの例：
```bash
curl -s "https://slack.com/api/auth.test" -H "Authorization: Bearer <SLACK_BOT_TOKEN>"
```

Slack MCPが利用できない場合は環境変数をセットせずに `python3 scripts/timecard.py today` を実行する。
timecard.py 側で「Slack MCP 未接続」と表示し、Chrome履歴のみで処理を続ける。

### Step 3: timecard.py を実行する

上記の環境変数をセットした状態で実行すると、timecard.py が以下を行う：
- Chrome履歴も取得して Slack データと統合
- 出退勤時刻を決定して表示・保存確認

---

## エラー・例外処理

| 状況 | 対応 |
|------|------|
| Slack MCPが未接続 | 環境変数なしで実行。Chrome履歴のみで処理する |
| チャンネルにBotが招待されていない | Slack MCPがエラーを返す。手動でBotをチャンネルに招待するよう案内する |
| Chromeが起動中 | 「Chromeを閉じてから再実行してください」と表示 |
| 当日のデータが見つからない | 「該当日の記録が見つかりません」と表示 |
