"""検索コマンド"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from src.core.config import settings
from src.core.firestore import firestore_client
from src.core.gemini import gemini_client
from src.core.models import SearchResult
from src.bot.utils.embed import create_search_result_embed

logger = logging.getLogger(__name__)


class SearchCog(commands.Cog):
    """検索コマンド"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ユーザーごとの検索コンテキスト（絞り込み用）
        self.search_context: dict[int, list[str]] = {}

    @app_commands.command(name="search", description="Discordメッセージを自然言語で検索")
    @app_commands.describe(query="検索クエリ（例: 先月の経理の話）")
    async def search(self, interaction: discord.Interaction, query: str):
        """メッセージを検索"""
        await interaction.response.defer(thinking=True)

        try:
            # Gemini File Searchで検索
            results, response_text = await gemini_client.search_with_context(query)

            if not results:
                embed = create_search_result_embed([], query)
                await interaction.followup.send(embed=embed)
                return

            # メッセージIDからFirestoreでメタデータ取得
            message_ids = [r["message_id"] for r in results]
            messages = await firestore_client.get_messages_by_ids(message_ids)

            # SearchResult形式に変換
            search_results = [
                SearchResult(message=msg, snippet=msg.content[:100])
                for msg in messages
            ]

            # 検索コンテキストを保存（絞り込み用）
            self.search_context[interaction.user.id] = message_ids

            # Embed作成・送信
            embed = create_search_result_embed(search_results, query)
            await interaction.followup.send(embed=embed)

            logger.info(f"検索完了: query='{query}', results={len(search_results)}")

        except Exception as e:
            logger.error(f"検索エラー: {e}")
            await interaction.followup.send(
                f"検索中にエラーが発生しました: {str(e)}",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ監視（絞り込み対応）"""
        # Botのメッセージは無視
        if message.author.bot:
            return

        # 検索コンテキストがあるユーザーからのメッセージ
        user_id = message.author.id
        if user_id not in self.search_context:
            return

        # コマンドではない通常のメッセージ
        if message.content.startswith("/"):
            return

        # 絞り込みクエリとして処理
        previous_results = self.search_context[user_id]
        query = message.content

        try:
            async with message.channel.typing():
                results, response_text = await gemini_client.search_with_context(
                    query,
                    previous_results=previous_results,
                )

                if not results:
                    await message.reply("該当するメッセージが見つかりませんでした")
                    return

                # メッセージIDからFirestoreでメタデータ取得
                message_ids = [r["message_id"] for r in results]
                messages = await firestore_client.get_messages_by_ids(message_ids)

                search_results = [
                    SearchResult(message=msg, snippet=msg.content[:100])
                    for msg in messages
                ]

                # コンテキスト更新
                self.search_context[user_id] = message_ids

                embed = create_search_result_embed(search_results, query)
                await message.reply(embed=embed)

        except Exception as e:
            logger.error(f"絞り込みエラー: {e}")
            await message.reply(f"エラーが発生しました: {str(e)}")


async def setup(bot: commands.Bot):
    """Cogをセットアップ"""
    await bot.add_cog(SearchCog(bot))
