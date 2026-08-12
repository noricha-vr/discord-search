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

        # コマンド登録に失敗したまま「正常起動」に見えないよう、on_ready の presence に出す。
        self.commands_ready = False

    async def setup_hook(self):
        """Bot起動時の初期化

        起動処理の失敗でプロセスを終了させない。setup_hook から例外を投げると
        Bot が起動できず、compose の restart: unless-stopped と組み合わさって
        無限再起動になり、Discord API へ失敗リクエストを叩き続けるため
        （実測 2,223 回 / Issue #1）。失敗は ERROR ログと presence で可視化する。
        """
        try:
            await self.load_extension("src.bot.commands.search")
        except commands.ExtensionError as exc:
            logger.error(
                f"Cog のロードに失敗しました: {exc}。コマンド無しで起動を継続します。"
                "認証エラーの場合は ~/.config/gcloud のマウントと ADC を確認してください"
            )
            return

        await self._sync_commands()

    async def _sync_commands(self):
        """スラッシュコマンドを同期する

        ギルド同期に失敗してもグローバル同期へはフォールバックしない。
        /search は実行者・サーバーを検証せず単一の検索ストアを引くため、
        グローバル登録は他サーバーと DM へ検索窓を開くことになる。
        403 が出るのはまさに招待スコープが壊れている状況なので、
        フォールバックすると最も危険なタイミングで公開範囲が最大化する。
        """
        if settings.discord_guild_id:
            try:
                guild = discord.Object(id=int(settings.discord_guild_id))
            except ValueError:
                logger.error(
                    f"DISCORD_GUILD_ID が数値ではありません: {settings.discord_guild_id!r}。"
                    "コマンドを登録せず起動を継続します"
                )
                return

            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
            except discord.Forbidden as exc:
                logger.error(
                    f"ギルドコマンドの同期に失敗しました (403): {exc}。"
                    "Bot が applications.commands スコープ付きでギルドに招待されているか、"
                    f"DISCORD_GUILD_ID={settings.discord_guild_id} が正しいかを確認してください。"
                    "コマンド未登録のまま起動を継続します"
                )
                return
            except discord.HTTPException as exc:
                # 429・5xx・コマンド定義不正。ここで落とすと再起動ループに戻る。
                logger.error(
                    f"ギルドコマンドの同期に失敗しました: {exc}。"
                    "コマンド未登録のまま起動を継続します"
                )
                return

            self.commands_ready = True
            logger.info(f"コマンドを同期: guild={settings.discord_guild_id}")
            return

        try:
            await self.tree.sync()
        except discord.HTTPException as exc:
            logger.error(
                f"グローバルコマンドの同期に失敗しました: {exc}。"
                "コマンド未登録のまま起動を継続します"
            )
            return

        self.commands_ready = True
        # グローバル登録は全ギルドへの反映に最大1時間かかる。
        logger.info("グローバルコマンドを同期（反映まで最大1時間かかります）")

    async def on_ready(self):
        """Bot準備完了時"""
        logger.info(f"ログイン: {self.user} (ID: {self.user.id})")
        logger.info(f"接続サーバー数: {len(self.guilds)}")

        # ステータス設定。同期に失敗した時は「正常起動」に見せない（ログを見ずに気づけるように）
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/search で検索" if self.commands_ready else "コマンド同期失敗（ログ参照）",
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
