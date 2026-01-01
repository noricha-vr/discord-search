"""Gemini File Search クライアント"""

import logging
from google import genai
from google.genai import types

from src.core.config import settings
from src.core.models import Message

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
        try:
            store_name = await self.ensure_store()
            content = message.to_file_content()

            # ファイルとしてアップロード
            operation = self.client.file_search_stores.upload_to_file_search_store(
                file=content.encode("utf-8"),
                file_search_store_name=store_name,
                config={
                    "display_name": f"msg_{message.message_id}",
                }
            )

            # 完了を待機
            while not operation.done:
                import time
                time.sleep(1)
                operation = self.client.operations.get(operation)

            logger.debug(f"メッセージをインデックス: {message.message_id}")
            return f"msg_{message.message_id}"

        except Exception as e:
            logger.error(f"インデックス失敗: {message.message_id} - {e}")
            return None

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

検索結果には必ず以下を含めてください:
1. 各メッセージのメッセージID（msg_xxxxxxxxx形式）
2. メッセージの簡潔な要約

メッセージIDは正確に抽出し、msg_プレフィックスを付けてください。
""",
                )
            )

            # レスポンスからメッセージIDを抽出
            results = []
            response_text = response.text or ""
            if response_text:
                import re
                message_ids = re.findall(r"msg_(\d+)", response_text)
                for msg_id in message_ids[:settings.search_result_limit]:
                    results.append({
                        "message_id": msg_id,
                        "response_text": response_text,
                    })

            return results, response_text

        except Exception as e:
            logger.error(f"検索失敗: {query} - {e}")
            return [], str(e)


# シングルトンインスタンス
gemini_client = GeminiClient()
