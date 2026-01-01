# Discord Search

Discordの会話を自然言語で検索できるBot

## 機能

- 自然言語検索（「先月の経理の話」で検索）
- 日付・発言者での絞り込み
- 添付ファイル（画像・PDF）の内容検索
- 検索結果からDiscordにジャンプ

## 技術スタック

- Python 3.12+
- discord.py
- Gemini API File Search Tool
- YomiToku（日本語OCR）
- Cloud Run / Cloud Run Jobs
- Firestore

## セットアップ

### 1. Discord Bot作成

1. https://discord.com/developers/applications にアクセス
2. New Application → 名前: Discord Search
3. Bot → Reset Token → トークンをコピー
4. Privileged Gateway Intents:
   - Message Content Intent ✓
   - Server Members Intent ✓
5. OAuth2 → URL Generator:
   - Scopes: bot, applications.commands
   - Permissions: Read Messages, Send Messages, Read Message History
6. 生成URLでBotをサーバーに招待

### 2. 環境変数設定

```bash
cp .env.example .env
# .envを編集してトークン等を設定
```

### 3. 依存関係インストール

```bash
uv sync
```

### 4. 初回同期

```bash
uv run python scripts/initial_sync.py
```

### 5. Bot起動

```bash
uv run python -m src.bot.main
```

## 使い方

```
/search 先月の経理の話
/search 妻が送った見積書
/search 添付ファイルがある予算の話
```

## Docker

```bash
# Bot起動
docker compose up bot

# 同期ジョブ実行
docker compose --profile jobs run sync-job

# 初回フル同期
docker compose --profile jobs run sync-job-full
```

## GCPデプロイ

```bash
# Artifact Registry設定
gcloud artifacts repositories create discord-search \
    --repository-format=docker \
    --location=asia-northeast1

# イメージビルド・プッシュ
docker buildx build --platform linux/amd64 \
    -t asia-northeast1-docker.pkg.dev/discord-search-20260101/discord-search/bot:latest \
    -f docker/bot.Dockerfile .

# Cloud Runデプロイ
gcloud run deploy discord-search-bot \
    --image asia-northeast1-docker.pkg.dev/discord-search-20260101/discord-search/bot:latest \
    --region asia-northeast1
```

## ライセンス

MIT（YomiTokuは CC BY-NC-SA 4.0）
