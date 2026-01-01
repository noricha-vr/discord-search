"""同期ジョブ エントリーポイント"""

import asyncio
import logging
import sys

import discord

from src.core.config import settings
from src.jobs.sync import MessageSyncer

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SyncClient(discord.Client):
    """同期用Discordクライアント"""

    def __init__(self, full_sync: bool = False):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        super().__init__(intents=intents)

        self.full_sync = full_sync
        self.result = None

    async def on_ready(self):
        """クライアント準備完了時に同期実行"""
        logger.info(f"ログイン: {self.user}")

        try:
            guild_id = int(settings.discord_guild_id)
            syncer = MessageSyncer(self)
            self.result = await syncer.sync_guild(guild_id, self.full_sync)
            logger.info(f"同期結果: {self.result}")
        except Exception as e:
            logger.error(f"同期エラー: {e}")
            self.result = {"error": str(e)}
        finally:
            await self.close()


async def run_sync(full_sync: bool = False) -> dict:
    """同期を実行"""
    if not settings.discord_bot_token:
        logger.error("DISCORD_BOT_TOKEN が設定されていません")
        return {"error": "DISCORD_BOT_TOKEN not set"}

    if not settings.discord_guild_id:
        logger.error("DISCORD_GUILD_ID が設定されていません")
        return {"error": "DISCORD_GUILD_ID not set"}

    client = SyncClient(full_sync=full_sync)

    try:
        await client.start(settings.discord_bot_token)
    except Exception as e:
        logger.error(f"クライアントエラー: {e}")
        return {"error": str(e)}

    return client.result or {"error": "No result"}


def main():
    """メイン関数"""
    # コマンドライン引数で初回同期を指定
    full_sync = "--full" in sys.argv or "--initial" in sys.argv

    if full_sync:
        logger.info("初回フル同期モード")
    else:
        logger.info("差分同期モード")

    result = asyncio.run(run_sync(full_sync))
    logger.info(f"完了: {result}")

    # エラーがあれば終了コード1
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
