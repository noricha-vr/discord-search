"""メッセージ同期処理"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import discord

from src.core.config import settings
from src.core.firestore import firestore_client
from src.core.gemini import gemini_client
from src.core.models import Message, Attachment
from src.jobs.ocr import ocr_processor

logger = logging.getLogger(__name__)


class MessageSyncer:
    """Discordメッセージ同期クラス"""

    def __init__(self, client: discord.Client):
        self.client = client
        self.processed_count = 0
        self.error_count = 0
        self.new_count = 0

    async def sync_guild(self, guild_id: int, full_sync: bool = False) -> dict:
        """ギルド全体を同期"""
        sync_id = str(uuid4())
        sync_type = "initial" if full_sync else "incremental"

        logger.info(f"同期開始: guild={guild_id}, type={sync_type}, sync_id={sync_id}")

        # 同期ステータス作成
        await firestore_client.create_sync_status(sync_id, sync_type)

        try:
            guild = self.client.get_guild(guild_id)
            if not guild:
                guild = await self.client.fetch_guild(guild_id)

            # 最後の同期時刻を取得
            last_sync = None
            if not full_sync:
                last_sync = await firestore_client.get_last_sync_time()

            # 全テキストチャンネルを同期
            for channel in guild.text_channels:
                try:
                    await self._sync_channel(channel, last_sync, sync_id)
                except discord.errors.Forbidden:
                    logger.warning(f"チャンネルアクセス拒否: {channel.name}")
                except Exception as e:
                    logger.error(f"チャンネル同期エラー: {channel.name} - {e}")
                    self.error_count += 1

                # チャンネル間で待機（レート制限対策）
                await asyncio.sleep(settings.sync_delay_seconds * 5)

            # フォーラムチャンネルのスレッドも同期（存在する場合）
            forum_channels = getattr(guild, "forum_channels", [])
            for channel in forum_channels:
                try:
                    async for thread in channel.archived_threads():
                        await self._sync_channel(thread, last_sync, sync_id)
                        await asyncio.sleep(settings.sync_delay_seconds * 2)
                except discord.errors.Forbidden:
                    logger.warning(f"フォーラムアクセス拒否: {channel.name}")
                except Exception as e:
                    logger.error(f"フォーラム同期エラー: {channel.name} - {e}")

            # 同期完了
            await firestore_client.complete_sync(sync_id, self.error_count)
            await firestore_client.update_last_sync_time(datetime.utcnow())

            logger.info(
                f"同期完了: processed={self.processed_count}, "
                f"new={self.new_count}, errors={self.error_count}"
            )

            return {
                "sync_id": sync_id,
                "processed_count": self.processed_count,
                "new_count": self.new_count,
                "error_count": self.error_count,
            }

        except Exception as e:
            logger.error(f"同期失敗: {e}")
            await firestore_client.fail_sync(sync_id, str(e))
            raise

    async def _sync_channel(
        self,
        channel: discord.TextChannel | discord.Thread,
        after: datetime | None,
        sync_id: str,
    ) -> None:
        """チャンネルを同期"""
        logger.info(f"チャンネル同期: {channel.name}")

        # メッセージ履歴を取得
        kwargs = {"limit": None}
        if after:
            kwargs["after"] = after

        count = 0
        async for discord_msg in channel.history(**kwargs):
            try:
                await self._process_message(discord_msg, channel)
                count += 1

                # バッチごとに待機（レート制限対策）
                if count % settings.sync_batch_size == 0:
                    await asyncio.sleep(settings.sync_delay_seconds)
                    await firestore_client.update_sync_progress(
                        sync_id,
                        last_channel_id=str(channel.id),
                        last_message_id=str(discord_msg.id),
                        processed_count=self.processed_count,
                    )

            except Exception as e:
                logger.error(f"メッセージ処理エラー: {discord_msg.id} - {e}")
                self.error_count += 1

        logger.info(f"チャンネル完了: {channel.name}, messages={count}")

    async def _process_message(
        self,
        discord_msg: discord.Message,
        channel: discord.TextChannel | discord.Thread,
    ) -> None:
        """メッセージを処理"""
        message_id = str(discord_msg.id)

        # 既存チェック
        if await firestore_client.message_exists(message_id):
            self.processed_count += 1
            return

        # 添付ファイル処理
        attachments = []
        for att in discord_msg.attachments:
            attachment = Attachment(
                filename=att.filename,
                content_type=att.content_type or "application/octet-stream",
                url=att.url,
                has_ocr=False,
            )

            # 画像の場合はOCR
            if ocr_processor.is_available() and ocr_processor.is_image(attachment.content_type):
                ocr_text = await ocr_processor.process_attachment(
                    att.url,
                    att.filename,
                    attachment.content_type,
                )
                if ocr_text:
                    attachment.has_ocr = True
                    attachment.ocr_text = ocr_text

            attachments.append(attachment)

        # スレッド情報
        thread_id = None
        thread_name = None
        if isinstance(channel, discord.Thread):
            thread_id = str(channel.id)
            thread_name = channel.name
            channel_name = channel.parent.name if channel.parent else channel.name
        else:
            channel_name = channel.name

        # Messageモデル作成
        message = Message(
            message_id=message_id,
            channel_id=str(channel.id),
            channel_name=channel_name,
            thread_id=thread_id,
            thread_name=thread_name,
            author_id=str(discord_msg.author.id),
            author_name=discord_msg.author.display_name,
            content=discord_msg.content,
            timestamp=discord_msg.created_at,
            has_attachment=len(attachments) > 0,
            attachments=attachments,
            jump_url=discord_msg.jump_url,
        )

        # File Search Storeにインデックス
        doc_id = await gemini_client.index_message(message)
        if doc_id:
            message.file_search_doc_id = doc_id
            message.indexed_at = datetime.utcnow()

        # Firestoreに保存
        await firestore_client.save_message(message)

        self.processed_count += 1
        self.new_count += 1

        logger.debug(f"メッセージ保存: {message_id}")
