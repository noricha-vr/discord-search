"""pytest fixtures"""

import pytest
from datetime import datetime

from src.core.models import Message, Attachment


@pytest.fixture
def sample_message() -> Message:
    """サンプルメッセージ"""
    return Message(
        message_id="1234567890123456789",
        channel_id="9876543210987654321",
        channel_name="general",
        author_id="1111111111111111111",
        author_name="test_user",
        content="これはテストメッセージです",
        timestamp=datetime(2024, 12, 15, 10, 30, 0),
        has_attachment=False,
        attachments=[],
        jump_url="https://discord.com/channels/123/456/789",
    )


@pytest.fixture
def sample_message_with_attachment() -> Message:
    """添付ファイル付きメッセージ"""
    return Message(
        message_id="1234567890123456790",
        channel_id="9876543210987654321",
        channel_name="general",
        author_id="1111111111111111111",
        author_name="test_user",
        content="画像を添付しました",
        timestamp=datetime(2024, 12, 15, 11, 0, 0),
        has_attachment=True,
        attachments=[
            Attachment(
                filename="screenshot.png",
                content_type="image/png",
                url="https://cdn.discord.com/attachments/xxx/screenshot.png",
                has_ocr=True,
                ocr_text="請求書\n金額: 100,000円",
            )
        ],
        jump_url="https://discord.com/channels/123/456/790",
    )
