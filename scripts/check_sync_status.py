#!/usr/bin/env python
"""同期状態確認スクリプト

Discordのチャンネル一覧とFirestoreの同期状態を比較し、
未同期のチャンネルを検出します。
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

from src.core.config import settings
from src.core.firestore import firestore_client

load_dotenv()


async def check_sync_status():
    """同期状態を確認"""
    print("=" * 60)
    print("Discord Search - 同期状態確認")
    print("=" * 60)

    # Firestore から同期済みチャンネル情報を取得
    synced_channels = await firestore_client.get_synced_channels_info()
    synced_ids = {ch["channel_id"] for ch in synced_channels}

    print(f"\n[Firestore] 同期済みチャンネル数: {len(synced_channels)}")

    # チャンネルごとのメッセージ数を取得
    message_counts = await firestore_client.get_message_count_by_channel()
    total_messages = sum(message_counts.values())
    print(f"[Firestore] 総メッセージ数: {total_messages:,}")

    # 同期済みチャンネル一覧
    if synced_channels:
        print("\n--- 同期済みチャンネル ---")
        for ch in sorted(synced_channels, key=lambda x: x.get("channel_name", "")):
            channel_id = ch.get("channel_id")
            channel_name = ch.get("channel_name", "Unknown")
            msg_count = message_counts.get(channel_id, 0)
            last_synced = ch.get("last_synced_at", "N/A")
            if isinstance(last_synced, str) and len(last_synced) > 19:
                last_synced = last_synced[:19]
            print(f"  - {channel_name}: {msg_count:,} messages (last: {last_synced})")

    # Discord からチャンネル一覧を取得して比較
    print("\n--- Discord チャンネルとの比較 ---")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            guild_id = int(settings.discord_guild_id)
            guild = client.get_guild(guild_id)
            if not guild:
                guild = await client.fetch_guild(guild_id)

            discord_channels = []
            not_synced = []

            # テキストチャンネル
            for channel in guild.text_channels:
                discord_channels.append({
                    "id": str(channel.id),
                    "name": channel.name,
                    "type": "text",
                })
                if str(channel.id) not in synced_ids:
                    not_synced.append(channel.name)

            # フォーラムチャンネル
            forum_channels = getattr(guild, "forum_channels", [])
            for forum in forum_channels:
                async for thread in forum.archived_threads():
                    discord_channels.append({
                        "id": str(thread.id),
                        "name": f"{forum.name}/{thread.name}",
                        "type": "forum_thread",
                    })
                    if str(thread.id) not in synced_ids:
                        not_synced.append(f"{forum.name}/{thread.name}")

            print(f"[Discord] テキストチャンネル数: {len(guild.text_channels)}")
            print(f"[Discord] 総チャンネル/スレッド数: {len(discord_channels)}")

            if not_synced:
                print(f"\n[警告] 未同期チャンネル ({len(not_synced)}件):")
                for name in not_synced:
                    print(f"  - {name}")
            else:
                print("\n[OK] すべてのチャンネルが同期済みです")

            # 最終同期時刻
            last_sync = await firestore_client.get_last_sync_time()
            if last_sync:
                print(f"\n最終同期時刻: {last_sync.isoformat()}")
            else:
                print("\n最終同期時刻: なし（初回同期未実行）")

        finally:
            await client.close()

    await client.start(settings.discord_bot_token)


if __name__ == "__main__":
    asyncio.run(check_sync_status())
