#!/bin/bash
# GCPプロジェクト初期設定スクリプト

set -e

# 環境変数から取得（必須）
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-asia-northeast1}"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP_PROJECT_ID environment variable is required"
    echo "Usage: GCP_PROJECT_ID=your-project-id ./scripts/setup_gcp.sh"
    exit 1
fi

echo "=== GCP Setup for Discord Search ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo

# Artifact Registry リポジトリ作成
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create discord-search \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID \
    --description="Discord Search Docker images" \
    2>/dev/null || echo "Repository already exists"

# Cloud Scheduler ジョブ作成（同期用）
echo "Creating Cloud Scheduler job..."
gcloud scheduler jobs create http discord-search-sync \
    --location=$REGION \
    --project=$PROJECT_ID \
    --schedule="0 * * * *" \
    --uri="https://discord-search-jobs-xxxxx-an.a.run.app" \
    --http-method=POST \
    --oidc-service-account-email="discord-search-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    2>/dev/null || echo "Scheduler job already exists or needs URL update"

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo "1. Create Discord Bot at https://discord.com/developers/applications"
echo "2. Copy .env.example to .env and fill in values"
echo "3. Run 'docker compose up bot' to start the bot"
echo "4. Run 'python scripts/initial_sync.py' for initial sync"
