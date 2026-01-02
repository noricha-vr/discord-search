#!/bin/bash

# 環境変数をcron用にエクスポート
printenv | grep -E '^(DISCORD_|GEMINI_|GCP_|GOOGLE_)' >> /etc/environment

# cronジョブ設定（毎日午前3時に同期実行）
echo "0 3 * * * root cd /app && /usr/local/bin/python -m src.jobs.main >> /var/log/sync.log 2>&1" > /etc/cron.d/sync-job
chmod 0644 /etc/cron.d/sync-job
crontab /etc/cron.d/sync-job

echo "Cron job scheduled: 毎日 03:00 に同期実行"
echo "ログ: docker compose logs -f cron"

# cron実行（フォアグラウンド）
cron -f
