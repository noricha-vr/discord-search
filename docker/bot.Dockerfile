FROM python:3.12-slim

WORKDIR /app

# 依存関係インストール
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# ソースコード
COPY src/ ./src/

# 環境変数
ENV PYTHONUNBUFFERED=1

# 実行
CMD ["python", "-m", "src.bot.main"]
