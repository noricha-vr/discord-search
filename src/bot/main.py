"""Discord Bot エントリーポイント"""

import asyncio
import logging
import discord
from discord.ext import commands

from src.core.config import settings

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DiscordSearchBot(commands.Bot):
    """Discord Search Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        """Bot起動時の初期化"""
        # Cogsをロード
        await self.load_extension("src.bot.commands.search")

        # スラッシュコマンドを同期
        if settings.discord_guild_id:
            guild = discord.Object(id=int(settings.discord_guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"コマンドを同期: guild={settings.discord_guild_id}")
        else:
            await self.tree.sync()
            logger.info("グローバルコマンドを同期")

    async def on_ready(self):
        """Bot準備完了時"""
        logger.info(f"ログイン: {self.user} (ID: {self.user.id})")
        logger.info(f"接続サーバー数: {len(self.guilds)}")

        # ステータス設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/search で検索",
            )
        )


async def main():
    """メイン関数"""
    if not settings.discord_bot_token:
        logger.error("DISCORD_BOT_TOKEN が設定されていません")
        return

    bot = DiscordSearchBot()

    try:
        await bot.start(settings.discord_bot_token)
    except KeyboardInterrupt:
        logger.info("Botを停止中...")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
