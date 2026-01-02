# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

| 項目 | 値 |
|------|-----|
| GCP Project ID | `discord-search-20260101` |
| GCP Region | `asia-northeast1` |
| Python | 3.12+ |
| パッケージ管理 | uv |

## プロジェクト概要

Discordの会話を自然言語で検索できるBot。Gemini File Search Toolによるセマンティック検索、YomiToku OCRによる画像内テキスト検索に対応。

## 開発コマンド

```bash
# 依存関係インストール
uv sync

# Bot起動（ローカル）
uv run python -m src.bot.main

# 同期ジョブ実行（差分）
uv run python -m src.jobs.main

# 同期ジョブ実行（フル）
uv run python -m src.jobs.main --full

# テスト
uv run pytest
uv run pytest tests/test_models.py -v  # 単一ファイル

# Lint
uv run ruff check .
uv run ruff format .
```

## Docker

```bash
# Bot起動
docker compose up bot

# 同期ジョブ（差分）
docker compose --profile jobs run sync-job

# 同期ジョブ（フル）
docker compose --profile jobs run sync-job-full
```

## アーキテクチャ

モノレポ構成。Bot（Cloud Run）と同期ジョブ（Cloud Run Jobs）を1リポジトリで管理。

```
src/
├── bot/        # Discord Bot（Cloud Run）- /search コマンド
├── jobs/       # 同期ジョブ（Cloud Run Jobs）- メッセージ取得・OCR
└── core/       # 共有コード - 設定、モデル、API クライアント
```

### データフロー

1. **同期（1時間ごと）**: Discord API → YomiToku OCR → Gemini File Search Store + Firestore
2. **検索（/search）**: ユーザークエリ → Gemini File Search → Firestore（jump_url取得）→ Embed返信

### 主要コンポーネント

| モジュール | 役割 |
|-----------|------|
| `src/core/gemini.py` | File Search Store操作、セマンティック検索 |
| `src/core/firestore.py` | メッセージメタデータCRUD |
| `src/core/models.py` | Message, ConversationChunk等のPydanticモデル |
| `src/core/chunker.py` | 会話チャンキング（RAG精度向上） |
| `src/jobs/sync.py` | Discordメッセージ取得・インデックス |
| `src/bot/commands/search.py` | /search コマンドハンドラ |

## 環境変数

`.env.example`参照。必須:
- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `GEMINI_API_KEY`

## スクリプト

`scripts/index.md`参照。主要なもの:
- `scripts/reindex.py` - 会話チャンク方式による再インデックス
