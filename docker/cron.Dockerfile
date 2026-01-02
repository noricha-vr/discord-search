FROM python:3.12-slim

WORKDIR /app

# cronインストール
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# 依存関係インストール
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# ソースコード
COPY src/ ./src/
COPY scripts/ ./scripts/

# entrypointスクリプト
COPY docker/cron-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ログファイル作成
RUN touch /var/log/sync.log

# 環境変数
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
