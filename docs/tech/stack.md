# 技術選定

## 概要

| カテゴリ | 技術 |
|----------|------|
| 言語 | Python 3.12+ |
| Bot フレームワーク | discord.py |
| 検索エンジン | Gemini API File Search Tool |
| 画像 OCR | YomiToku（軽量モデル、CPU） |
| ホスティング | Cloud Run |
| バッチ処理 | Cloud Scheduler + Cloud Run Jobs |
| データベース | Firestore |
| クラウド | GCP（新規プロジェクト） |

## 選定理由

### discord.py

- Gemini SDK（Python）と言語統一
- シンプルな実装
- 十分な機能とドキュメント

### Gemini API File Search Tool

- 完全管理型 RAG（チャンキング・埋め込み・ベクトルDB 自動）
- 自然言語検索（セマンティック検索）
- 添付ファイル内容検索対応（PDF, DOCX, XLSX 等）
- 低コスト（ストレージ無料、クエリ無料、インデックス $0.15/100万トークン）

### YomiToku

- 日本語特化の AI OCR
- 約 7,000 文字種対応（縦書き含む）
- 軽量モデル（GPU Free OCR）で CPU 推論可能
- Discord の画像添付（スクリーンショット等）をテキスト化

### Cloud Run

- サーバーレス（使った分だけ課金）
- GCP 統一
- コンテナベースでローカル開発しやすい
- YomiToku 軽量モデルは CPU で実用的な速度

### Cloud Scheduler + Cloud Run Jobs

- 1時間ごとのバッチ処理に最適
- GCP 統一で管理が楽
- ジョブ失敗時のリトライ設定可能

### Firestore

- サーバーレス NoSQL
- GCP 統一
- メッセージID ↔ メタデータの管理に十分
- 無料枠で十分（小規模利用）

## アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│                  Discord Server                  │
│  - テキストメッセージ                            │
│  - 画像添付（スクリーンショット等）              │
│  - PDF/ドキュメント添付                          │
└─────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────┐       ┌───────────────────────────────┐
│  Discord Bot      │       │  Cloud Run Jobs（1時間ごと）   │
│  Cloud Run        │       │  - Discord API でメッセージ取得│
│                   │       │  - 画像 → YomiToku で OCR      │
│  - /search 受付   │       │  - PDF → そのまま              │
│  - Gemini 検索    │       │  - File Search Store に追加    │
│  - 結果を返信     │       │  - Firestore にメタデータ保存  │
└───────────────────┘       └───────────────────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────┐       ┌───────────────────────┐
│  Gemini API       │       │  Firestore            │
│  File Search Tool │       │  - メッセージID       │
│                   │       │  - チャンネル名       │
│  - テキスト検索   │       │  - 発言者             │
│  - PDF 内容検索   │       │  - Jumpリンク         │
│  - OCR結果検索    │       │  - 添付ファイル情報   │
└───────────────────┘       └───────────────────────┘
                        ▲
                        │
              ┌─────────┴─────────┐
              │  Cloud Scheduler  │
              │  （1時間ごと起動） │
              └───────────────────┘
```

## 処理フロー

### バッチ同期（1時間ごと）

```
1. Cloud Scheduler が Cloud Run Jobs を起動
2. Discord API で前回同期以降のメッセージを取得
3. 添付ファイルの処理:
   - 画像 (.png, .jpg) → YomiToku でテキスト抽出
   - PDF, DOCX 等 → そのまま File Search Store へ
4. メッセージ本文 + 抽出テキストを File Search Store に保存
5. メタデータ（Jumpリンク等）を Firestore に保存
```

### 検索（/search）

```
1. ユーザーが /search {クエリ} を実行
2. Gemini File Search Tool でセマンティック検索
3. ヒットしたドキュメントの ID から Firestore でメタデータ取得
4. Jumpリンク付きの結果を Embed で返信
5. 「追加で条件を絞りますか？」を表示
```

## GCP 設定

| 項目 | 値 |
|------|-----|
| プロジェクト | 新規作成（未定） |
| リージョン | asia-northeast1 |

## 環境変数

| 変数名 | 用途 |
|--------|------|
| DISCORD_BOT_TOKEN | Discord Bot トークン |
| DISCORD_GUILD_ID | 対象サーバーID |
| GEMINI_API_KEY | Gemini API キー |
| GCP_PROJECT_ID | GCP プロジェクトID |
| FILE_SEARCH_STORE_NAME | File Search Store 名 |

## 依存パッケージ

```
discord.py
google-genai
google-cloud-firestore
yomitoku
```

## コスト見積もり（月額）

| サービス | コスト |
|----------|--------|
| Firestore | $0（無料枠内） |
| Gemini File Search | $0.01〜0.05 |
| Cloud Run（Bot） | $0〜2 |
| Cloud Run Jobs（同期 + OCR） | $0〜2 |
| Cloud Scheduler | $0（無料枠内） |
| **合計** | **$0〜5/月** |

## YomiToku 設定

### 軽量モデルの使用

```bash
yomitoku image.png --lite -d cpu -f md -o results
```

### 制限事項

- 1行あたり最大50文字（軽量モデル）
- Discord のスクリーンショット等には十分

### ライセンス

- CC BY-NC-SA 4.0
- 商用利用は別途確認が必要
