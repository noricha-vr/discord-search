"""起動時のスラッシュコマンド同期の振る舞い

起動処理の失敗で Bot プロセスが落ちると、compose の restart: unless-stopped と
組み合わさって無限再起動になる（実測 2,223 回 / Issue #1）。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest
from discord.ext import commands

from src.bot.main import DiscordSearchBot
from src.core import config

GUILD_ID = "123456789012345678"


def _http_error(cls, status: int, code: int, message: str):
    """discord.py の HTTP 例外を実際のレスポンス形で組み立てる"""
    response = SimpleNamespace(status=status, reason=message)
    return cls(response, {"code": code, "message": message})


def _forbidden() -> discord.Forbidden:
    """403 Missing Access (error code 50001)"""
    return _http_error(discord.Forbidden, 403, 50001, "Missing Access")


def _rate_limited() -> discord.HTTPException:
    """429 Too Many Requests"""
    return _http_error(discord.HTTPException, 429, 0, "You are being rate limited.")


@pytest.fixture
def bot(monkeypatch) -> DiscordSearchBot:
    instance = DiscordSearchBot()
    # Cog は import 時に Firestore / Gemini の認証を要求するため、起動経路の検証では切り離す
    monkeypatch.setattr(instance, "load_extension", AsyncMock())
    return instance


@pytest.mark.parametrize(
    "error",
    [_forbidden(), _rate_limited()],
    ids=["403_missing_access", "429_rate_limited"],
)
async def test_ギルド同期が失敗しても例外を伝播させずグローバルへ広げない(bot, monkeypatch, error):
    monkeypatch.setattr(config.settings, "discord_guild_id", GUILD_ID)
    sync = AsyncMock(side_effect=error)
    monkeypatch.setattr(bot.tree, "sync", sync)

    await bot.setup_hook()

    # グローバル同期は /search を他サーバー・DM へ公開するため、フォールバックしない
    assert sync.await_count == 1
    assert sync.await_args is not None
    assert sync.await_args.kwargs["guild"].id == int(GUILD_ID)
    assert bot.commands_ready is False


async def test_ギルド同期に成功したら準備完了になる(bot, monkeypatch):
    monkeypatch.setattr(config.settings, "discord_guild_id", GUILD_ID)
    sync = AsyncMock()
    monkeypatch.setattr(bot.tree, "sync", sync)

    await bot.setup_hook()

    assert sync.await_count == 1
    assert bot.commands_ready is True


async def test_GUILD_IDが数値でなければ同期せず起動を継続する(bot, monkeypatch):
    monkeypatch.setattr(config.settings, "discord_guild_id", "your-guild-id")
    sync = AsyncMock()
    monkeypatch.setattr(bot.tree, "sync", sync)

    await bot.setup_hook()

    sync.assert_not_awaited()
    assert bot.commands_ready is False


async def test_ギルド未設定ならグローバル同期を行う(bot, monkeypatch):
    monkeypatch.setattr(config.settings, "discord_guild_id", "")
    sync = AsyncMock()
    monkeypatch.setattr(bot.tree, "sync", sync)

    await bot.setup_hook()

    assert sync.await_count == 1
    assert sync.await_args is not None
    assert "guild" not in sync.await_args.kwargs
    assert bot.commands_ready is True


async def test_グローバル同期が失敗しても例外を伝播させない(bot, monkeypatch):
    monkeypatch.setattr(config.settings, "discord_guild_id", "")
    monkeypatch.setattr(bot.tree, "sync", AsyncMock(side_effect=_rate_limited()))

    await bot.setup_hook()

    assert bot.commands_ready is False


async def test_Cogのロードに失敗しても例外を伝播させない(bot, monkeypatch):
    # 認証情報が切れると search Cog の import が ExtensionFailed になる
    monkeypatch.setattr(config.settings, "discord_guild_id", GUILD_ID)
    monkeypatch.setattr(
        bot,
        "load_extension",
        AsyncMock(
            side_effect=commands.ExtensionFailed(
                "src.bot.commands.search", Exception("DefaultCredentialsError")
            )
        ),
    )
    sync = AsyncMock()
    monkeypatch.setattr(bot.tree, "sync", sync)

    await bot.setup_hook()

    sync.assert_not_awaited()
    assert bot.commands_ready is False
