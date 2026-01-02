# Discord Search

Discordの会話を自然言語で検索できるBot

## 機能

- 自然言語検索（「先月のミーティングの話」「〇〇さんが送ったファイル」）
- 日付・発言者での絞り込み
- 添付ファイル（画像・PDF）の内容検索（OCR）
- 検索結果からDiscordメッセージにジャンプ
- ユーザーエイリアス対応（ニックネームで検索可能）

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
2. New Application → 名前を設定
3. Bot → Reset Token → トークンをコピー
4. Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent
5. OAuth2 → URL Generator:
   - Scopes: bot, applications.commands
   - Permissions: Read Messages, Send Messages, Read Message History
6. 生成URLでBotをサーバーに招待

### 2. 環境変数設定

```bash
cp .env.example .env.local
# .env.local を編集してトークン等を設定
```

### 3. ユーザーエイリアス設定（オプション）

```bash
cp config/aliases.example.json config/aliases.json
# config/aliases.json を編集してニックネームを設定
```

### 4. 依存関係インストール

```bash
uv sync
```

### 5. 初回同期

```bash
uv run python scripts/initial_sync.py
```

### 6. Bot起動

```bash
uv run python -m src.bot.main
```

## 使い方

```
/search 先月のミーティングの話
/search 〇〇さんが送った見積書
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
# 環境変数設定
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=asia-northeast1

# Artifact Registry設定
gcloud artifacts repositories create discord-search \
    --repository-format=docker \
    --location=$GCP_REGION \
    --project=$GCP_PROJECT_ID

# イメージビルド・プッシュ
docker buildx build --platform linux/amd64 \
    -t $GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/discord-search/bot:latest \
    -f docker/bot.Dockerfile .

# Cloud Runデプロイ
gcloud run deploy discord-search-bot \
    --image $GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/discord-search/bot:latest \
    --region $GCP_REGION \
    --project $GCP_PROJECT_ID
```

## ライセンス

MIT（YomiTokuは CC BY-NC-SA 4.0）
