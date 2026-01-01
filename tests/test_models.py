"""モデルのテスト"""

import pytest
from datetime import datetime

from src.core.models import Message, Attachment


def test_message_to_file_content(sample_message):
    """to_file_content()のテスト"""
    content = sample_message.to_file_content()

    assert "[メタデータ]" in content
    assert "チャンネル: #general" in content
    assert "発言者: @test_user" in content
    assert "[本文]" in content
    assert "これはテストメッセージです" in content


def test_message_with_attachment_to_file_content(sample_message_with_attachment):
    """添付ファイル付きメッセージのテスト"""
    content = sample_message_with_attachment.to_file_content()

    assert "[添付ファイル]" in content
    assert "ファイル名: screenshot.png" in content
    assert "[添付ファイル内容]" in content
    assert "請求書" in content
    assert "金額: 100,000円" in content


def test_message_serialization(sample_message):
    """シリアライズのテスト"""
    data = sample_message.model_dump(mode="json")

    assert data["message_id"] == "1234567890123456789"
    assert data["channel_name"] == "general"
    assert data["author_name"] == "test_user"


def test_message_deserialization():
    """デシリアライズのテスト"""
    data = {
        "message_id": "123",
        "channel_id": "456",
        "channel_name": "test",
        "author_id": "789",
        "author_name": "user",
        "content": "hello",
        "timestamp": "2024-12-15T10:00:00",
        "has_attachment": False,
        "attachments": [],
        "jump_url": "https://discord.com/xxx",
    }

    message = Message(**data)

    assert message.message_id == "123"
    assert message.channel_name == "test"
    assert isinstance(message.timestamp, datetime)
