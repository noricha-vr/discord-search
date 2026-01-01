FROM python:3.12-slim

WORKDIR /app

# システム依存関係（YomiToku用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 依存関係インストール（OCR含む）
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[ocr]"

# ソースコード
COPY src/ ./src/

# 環境変数
ENV PYTHONUNBUFFERED=1

# 実行（デフォルトは差分同期）
CMD ["python", "-m", "src.jobs.main"]
