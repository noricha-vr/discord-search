# データモデル設計

## 概要

| ストレージ | 用途 | 構成 |
|------------|------|------|
| Firestore | メタデータ管理 | フラット構造 |
| File Search Store | 検索インデックス | 1メッセージ1ファイル |

---

## Firestore

### messages コレクション

メッセージのメタデータを保存。検索結果から Jumpリンク等を取得するために使用。

```
messages/{message_id}
├── message_id: string        # Discord メッセージID
├── channel_id: string        # チャンネルID
├── channel_name: string      # チャンネル名
├── thread_id: string?        # スレッドID（あれば）
├── thread_name: string?      # スレッド名（あれば）
├── author_id: string         # 発言者ID
├── author_name: string       # 発言者名
├── content: string           # メッセージ本文（プレビュー用）
├── timestamp: timestamp      # 投稿日時
├── has_attachment: boolean   # 添付ファイル有無
├── attachments: array        # 添付ファイル情報
│   └── {
│         filename: string,
│         content_type: string,
│         url: string,
│         has_ocr: boolean
│       }
├── jump_url: string          # Discordへのジャンプリンク
├── indexed_at: timestamp     # File Search Store登録日時
└── file_search_doc_id: string # File Search Store のドキュメントID
```

### sync_status コレクション

同期状態を管理。中断時の再開に使用。

```
sync_status/{sync_id}
├── status: string            # "in_progress" | "completed" | "failed"
├── type: string              # "initial" | "incremental"
├── started_at: timestamp     # 開始日時
├── completed_at: timestamp?  # 完了日時
├── last_channel_id: string?  # 最後に処理したチャンネルID
├── last_message_id: string?  # 最後に処理したメッセージID
├── processed_count: number   # 処理済みメッセージ数
├── error_count: number       # エラー数
└── error_messages: array     # エラー詳細
```

### config コレクション

設定情報を保存。

```
config/sync
├── last_sync_at: timestamp   # 最後の同期完了日時
├── initial_sync_completed: boolean  # 初回同期完了フラグ
└── excluded_channels: array  # 除外チャンネルID（あれば）
```

---

## File Search Store

### 構成: 1メッセージ = 1ファイル

```
fileSearchStore/
├── msg_123456789012345678.txt
├── msg_123456789012345679.txt
├── msg_123456789012345680.txt
└── ...
```

### ファイル命名規則

```
msg_{message_id}.txt
```

### ファイル内容フォーマット

```
[メタデータ]
日時: 2024-12-15 10:30
チャンネル: #general
スレッド: プロジェクトA進捗
発言者: @user1

[本文]
請求書の処理について確認したいんだけど、
来週までに対応できる？

[添付ファイル]
ファイル名: invoice.pdf
種類: PDF

[添付ファイル内容]
株式会社〇〇
請求書
金額: 100,000円
...
```

### メタデータフィルタ用属性

File Search Store のメタデータフィルタ機能を活用。

```python
# アップロード時にメタデータを設定
client.file_search_stores.upload_to_file_search_store(
    file=file_content,
    file_search_store_name=store.name,
    config={
        'display_name': f'msg_{message_id}',
        'metadata': {
            'channel_id': channel_id,
            'author_id': author_id,
            'timestamp': timestamp.isoformat(),
            'has_attachment': 'true' if has_attachment else 'false'
        }
    }
)
```

---

## データフロー

### バッチ同期（1時間ごと）

```
1. Discord API でメッセージ取得
   ↓
2. 添付ファイル処理
   - 画像 → YomiToku で OCR → テキスト抽出
   - PDF/DOCX → そのまま
   ↓
3. File Search Store 用ファイル生成
   - メタデータ + 本文 + OCR結果
   ↓
4. File Search Store にアップロード
   ↓
5. Firestore にメタデータ保存
   - message_id, jump_url, etc.
```

### 検索（/search）

```
1. ユーザーが /search {クエリ} 実行
   ↓
2. Gemini File Search Tool で検索
   - セマンティック検索
   - 引用情報を取得
   ↓
3. 引用元ファイル名から message_id を抽出
   - msg_123456789.txt → 123456789
   ↓
4. Firestore から jump_url 等を取得
   ↓
5. 結果を Embed で返信
```

---

## インデックス

### Firestore インデックス

```yaml
# firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "messages",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "messages",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "channel_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "messages",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "author_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    }
  ]
}
```

---

## レート制限対策（初回同期）

### Discord API 制限

| 制限 | 値 |
|------|-----|
| メッセージ取得 | 50リクエスト/秒/チャンネル |
| 1リクエスト | 最大100件 |

### 取得戦略

```python
async def fetch_messages_slowly():
    for channel in channels:
        async for message in channel.history(limit=None):
            await process_message(message)

            # 100件ごとに1秒待機
            if count % 100 == 0:
                await asyncio.sleep(1)

        # チャンネル間で5秒待機
        await asyncio.sleep(5)

        # 進捗を Firestore に保存（再開用）
        await save_progress(channel.id, message.id)
```

### 中断・再開

```python
# 再開時は最後の位置から
last_channel_id, last_message_id = await get_last_progress()

for channel in channels:
    if channel.id < last_channel_id:
        continue  # スキップ

    async for message in channel.history(after=last_message_id):
        ...
```

---

## 容量見積もり

### 前提

| 項目 | 想定値 |
|------|--------|
| 過去メッセージ数 | 10,000件 |
| 月間新規メッセージ | 1,000件 |
| 1メッセージの Firestore サイズ | 500バイト |
| 1メッセージの File Search ファイルサイズ | 1KB |

### Firestore

```
初期: 10,000件 × 500バイト = 5MB
年間: 12,000件追加 × 500バイト = 6MB
合計: 約 11MB（無料枠 1GB 内）
```

### File Search Store

```
初期: 10,000件 × 1KB = 10MB
年間: 12,000件追加 × 1KB = 12MB
合計: 約 22MB（ストレージ無料）
```

### インデックスコスト

```
初期: 10MB ÷ 4文字/トークン ≈ 2.5Mトークン
コスト: 2.5M × $0.15/1M = $0.375（初回のみ）
```
