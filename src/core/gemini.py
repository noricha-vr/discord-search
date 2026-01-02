"""Gemini File Search クライアント"""

import logging
from google import genai
from google.genai import types

from src.core.config import settings
from src.core.models import ConversationChunk, Message

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini API操作クラス"""

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.store_name: str | None = None
        self._store: types.FileSearchStore | None = None

    async def ensure_store(self) -> str:
        """File Search Storeが存在することを確認し、名前を返す"""
        if self.store_name:
            return self.store_name

        # 既存のストアを検索
        stores = self.client.file_search_stores.list()
        for store in stores:
            if store.display_name == settings.file_search_store_name:
                self._store = store
                self.store_name = store.name
                logger.info(f"既存のFile Search Store を使用: {store.name}")
                return self.store_name

        # 新規作成
        self._store = self.client.file_search_stores.create(
            config={"display_name": settings.file_search_store_name}
        )
        self.store_name = self._store.name
        logger.info(f"File Search Store を作成: {self.store_name}")
        return self.store_name

    async def index_message(self, message: Message) -> str | None:
        """メッセージをFile Search Storeにインデックス"""
        import tempfile
        import os
        import time

        try:
            store_name = await self.ensure_store()
            content = message.to_file_content()

            # 一時ファイルに書き込み
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                encoding="utf-8",
                delete=False,
            ) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            try:
                # ファイルとしてアップロード
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=tmp_path,
                    file_search_store_name=store_name,
                    config={
                        "display_name": f"msg_{message.message_id}",
                    }
                )

                # 完了を待機
                while not operation.done:
                    time.sleep(1)
                    operation = self.client.operations.get(operation)

                logger.debug(f"メッセージをインデックス: {message.message_id}")
                return f"msg_{message.message_id}"
            finally:
                # 一時ファイルを削除
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"インデックス失敗: {message.message_id} - {e}")
            return None

    async def index_conversation_chunk(
        self,
        chunk: ConversationChunk,
        messages: list[Message],
    ) -> str | None:
        """会話チャンクをFile Search Storeにインデックス

        Args:
            chunk: インデックスする会話チャンク
            messages: チャンク内のメッセージ一覧（時間順）
        """
        import tempfile
        import os
        import time

        try:
            store_name = await self.ensure_store()
            content = chunk.to_file_content(messages)

            # 一時ファイルに書き込み
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                encoding="utf-8",
                delete=False,
            ) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            try:
                # ファイルとしてアップロード
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=tmp_path,
                    file_search_store_name=store_name,
                    config={
                        "display_name": f"chunk_{chunk.chunk_id}",
                    }
                )

                # 完了を待機
                while not operation.done:
                    time.sleep(1)
                    operation = self.client.operations.get(operation)

                logger.debug(f"チャンクをインデックス: {chunk.chunk_id}")
                return f"chunk_{chunk.chunk_id}"
            finally:
                # 一時ファイルを削除
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"チャンクインデックス失敗: {chunk.chunk_id} - {e}")
            return None

    async def delete_all_files_in_store(self) -> int:
        """File Search Store内の全ファイルを削除（再インデックス用）

        Returns:
            削除したファイル数
        """
        try:
            store_name = await self.ensure_store()
            deleted_count = 0

            # ストア内のファイル一覧を取得して削除
            files = self.client.file_search_stores.list_files(
                file_search_store_name=store_name
            )

            for file in files:
                try:
                    self.client.file_search_stores.delete_file(
                        file_search_store_name=store_name,
                        file_name=file.name,
                    )
                    deleted_count += 1
                    logger.debug(f"ファイル削除: {file.name}")
                except Exception as e:
                    logger.warning(f"ファイル削除失敗: {file.name} - {e}")

            logger.info(f"File Search Store内の{deleted_count}件のファイルを削除")
            return deleted_count

        except Exception as e:
            logger.error(f"ファイル削除処理失敗: {e}")
            return 0

    async def search(self, query: str) -> list[dict]:
        """自然言語で検索"""
        try:
            store_name = await self.ensure_store()

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ],
                    system_instruction="""
あなたはDiscordメッセージ検索アシスタントです。
ユーザーのクエリに基づいて、関連するメッセージを検索し、結果を返してください。

検索結果は以下の形式で返してください:
1. 見つかったメッセージの要約
2. 各メッセージのメッセージID（msg_xxxxxxxxx形式）

メッセージIDは必ず正確に抽出してください。
""",
                )
            )

            # レスポンスからメッセージIDを抽出
            results = []
            if response.text:
                # msg_で始まるIDを抽出
                import re
                message_ids = re.findall(r"msg_(\d+)", response.text)
                for msg_id in message_ids[:settings.search_result_limit]:
                    results.append({
                        "message_id": msg_id,
                        "response_text": response.text,
                    })

            return results

        except Exception as e:
            logger.error(f"検索失敗: {query} - {e}")
            return []

    async def search_with_context(
        self,
        query: str,
        previous_results: list[str] | None = None,
    ) -> tuple[list[dict], str]:
        """コンテキスト付き検索（絞り込み対応）"""
        try:
            store_name = await self.ensure_store()

            # 絞り込みの場合は前回の結果をコンテキストに含める
            context = ""
            if previous_results:
                context = f"\n\n前回の検索結果のメッセージID: {', '.join(previous_results)}\nこの中から絞り込んでください。"

            full_query = query + context

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ],
                    system_instruction="""
あなたはDiscordメッセージ検索アシスタントです。
ユーザーのクエリに基づいて、関連するメッセージを検索し、結果を返してください。

## ユーザーエイリアス
以下のニックネームは同一人物を指します:
- みーちゃん = @Usagi

## 出力形式
検索結果は必ず以下のJSON形式で返してください。JSONのみを出力し、他のテキストは含めないでください:

```json
{
  "results": [
    {
      "message_id": "msg_xxxxxxxxx",
      "reason": "このメッセージがクエリに関連する理由（1-2文で簡潔に）",
      "highlight": "クエリに関連する部分の引用（元のメッセージから20-50文字程度）"
    }
  ]
}
```

## 重要なルール
1. message_idは必ず "msg_" プレフィックス付きの正確なIDを使用
2. reasonはなぜこのメッセージがクエリにマッチしたか説明
3. highlightはメッセージ本文からクエリに関連する部分を引用（添付ファイルのみの場合は「添付ファイル: ファイル名」）
4. 最大5件まで、関連度の高い順に返す
""",
                )
            )

            # レスポンスからJSONをパース
            results = []
            response_text = response.text or ""

            if response_text:
                import re
                import json

                # JSONブロックを抽出
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # ```なしの場合、全体をJSONとしてパース試行
                    json_str = response_text.strip()

                try:
                    data = json.loads(json_str)
                    for item in data.get("results", [])[:settings.search_result_limit]:
                        msg_id = item.get("message_id", "")
                        # msg_プレフィックスを除去
                        if msg_id.startswith("msg_"):
                            msg_id = msg_id[4:]
                        results.append({
                            "message_id": msg_id,
                            "reason": item.get("reason", ""),
                            "highlight": item.get("highlight", ""),
                        })
                except json.JSONDecodeError:
                    # JSONパース失敗時は従来方式にフォールバック
                    logger.warning(f"JSONパース失敗、従来方式にフォールバック: {response_text[:200]}")
                    message_ids = re.findall(r"msg_(\d+)", response_text)
                    for msg_id in message_ids[:settings.search_result_limit]:
                        results.append({
                            "message_id": msg_id,
                            "reason": "",
                            "highlight": "",
                        })

            return results, response_text

        except Exception as e:
            logger.error(f"検索失敗: {query} - {e}")
            return [], str(e)


# シングルトンインスタンス
gemini_client = GeminiClient()
