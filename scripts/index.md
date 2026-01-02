# スクリプト一覧

## setup_gcp.sh

GCPプロジェクトの初期設定スクリプト。

```bash
./scripts/setup_gcp.sh
```

## initial_sync.py

初回の全メッセージ同期を実行。

```bash
uv run python scripts/initial_sync.py
```

## reindex.py

会話チャンク方式による再インデックス。
既存メッセージを時間ベースでグループ化し、RAG検索精度を向上。

```bash
# dry-run（削除・インデックスせずに確認のみ）
uv run python scripts/reindex.py --dry-run

# 本番実行
uv run python scripts/reindex.py

# オプション
#   --time-window 30    時間ウィンドウ（分）
#   --max-messages 20   1チャンクの最大メッセージ数
#   --min-messages 3    1チャンクの最小メッセージ数
```
