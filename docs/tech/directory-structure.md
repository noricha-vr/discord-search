# ディレクトリ構造

## 概要

モノレポ構成。Bot と同期ジョブを1リポジトリで管理。

```
discord-search/
├── src/
│   ├── bot/                    # Discord Bot（Cloud Run）
│   │   ├── __init__.py
│   │   ├── main.py             # エントリーポイント
│   │   ├── commands/           # スラッシュコマンド
│   │   │   ├── __init__.py
│   │   │   └── search.py       # /search コマンド
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── embed.py        # Embed生成ヘルパー
│   │
│   ├── jobs/                   # Cloud Run Jobs（同期処理）
│   │   ├── __init__.py
│   │   ├── main.py             # エントリーポイント
│   │   ├── sync.py             # メッセージ同期ロジック
│   │   └── ocr.py              # YomiToku OCR処理
│   │
│   └── core/                   # 共通コード
│       ├── __init__.py
│       ├── config.py           # 環境変数・設定
│       ├── discord_client.py   # Discord API クライアント
│       ├── firestore.py        # Firestore クライアント
│       ├── gemini.py           # Gemini File Search クライアント
│       └── models.py           # Pydantic モデル
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # pytest fixtures
│   ├── test_search.py
│   ├── test_sync.py
│   └── test_ocr.py
│
├── docker/
│   ├── bot.Dockerfile          # Bot用 Dockerfile
│   └── jobs.Dockerfile         # Jobs用 Dockerfile
│
├── scripts/
│   ├── index.md                # スクリプト一覧
│   ├── initial_sync.py         # 初回同期スクリプト
│   └── setup_gcp.sh            # GCP初期設定
│
├── docs/                       # ドキュメント
│   ├── index.md
│   ├── overview.md
│   ├── api/
│   ├── foundation/
│   ├── requirements/
│   └── tech/
│
├── .env.example                # 環境変数テンプレート
├── .gitignore
├── docker-compose.yaml         # ローカル開発用
├── pyproject.toml              # Python依存関係（uv）
├── README.md
└── cloudbuild.yaml             # Cloud Build設定
```

---

## 各ディレクトリの役割

### src/bot/

Discord Bot 本体。Cloud Run にデプロイ。

| ファイル | 役割 |
|----------|------|
| main.py | Bot 起動、イベントループ |
| commands/search.py | /search コマンドのハンドラ |
| utils/embed.py | 検索結果の Embed 生成 |

### src/jobs/

同期処理ジョブ。Cloud Run Jobs で1時間ごとに実行。

| ファイル | 役割 |
|----------|------|
| main.py | ジョブ起動、エラーハンドリング |
| sync.py | Discord メッセージ取得・保存 |
| ocr.py | YomiToku で画像からテキスト抽出 |

### src/core/

Bot と Jobs で共有するコード。

| ファイル | 役割 |
|----------|------|
| config.py | 環境変数を Pydantic Settings で管理 |
| discord_client.py | Discord API のラッパー |
| firestore.py | Firestore の CRUD 操作 |
| gemini.py | Gemini File Search Store 操作 |
| models.py | Message, SyncStatus 等の Pydantic モデル |

### tests/

pytest によるテスト。

| ファイル | 役割 |
|----------|------|
| conftest.py | 共通 fixtures（モック等） |
| test_search.py | 検索機能のテスト |
| test_sync.py | 同期機能のテスト |
| test_ocr.py | OCR 機能のテスト |

### docker/

Dockerfile を格納。Bot と Jobs で別イメージ。

| ファイル | 役割 |
|----------|------|
| bot.Dockerfile | Bot 用（discord.py, google-genai） |
| jobs.Dockerfile | Jobs 用（yomitoku 追加） |

### scripts/

一時スクリプト・運用スクリプト。

| ファイル | 役割 |
|----------|------|
| index.md | スクリプト一覧 |
| initial_sync.py | 初回の全メッセージ同期 |
| setup_gcp.sh | GCP プロジェクト初期設定 |

---

## Docker イメージ

### bot.Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/

CMD ["python", "-m", "src.bot.main"]
```

### jobs.Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# YomiToku の依存関係
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .[ocr]

COPY src/ ./src/

CMD ["python", "-m", "src.jobs.main"]
```

---

## pyproject.toml

```toml
[project]
name = "discord-search"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "discord.py>=2.3.0",
    "google-genai>=0.1.0",
    "google-cloud-firestore>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
ocr = [
    "yomitoku>=0.10.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

---

## デプロイ構成

| コンポーネント | デプロイ先 | トリガー |
|----------------|-----------|----------|
| Bot | Cloud Run | 常時起動 |
| Jobs | Cloud Run Jobs | Cloud Scheduler（1時間ごと） |
