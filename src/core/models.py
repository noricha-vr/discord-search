"""Pydantic モデル定義"""

from datetime import datetime
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """添付ファイル情報"""

    filename: str
    content_type: str
    url: str
    has_ocr: bool = False
    ocr_text: str | None = None


class Message(BaseModel):
    """Discordメッセージ"""

    message_id: str
    channel_id: str
    channel_name: str
    thread_id: str | None = None
    thread_name: str | None = None
    author_id: str
    author_name: str
    content: str
    timestamp: datetime
    has_attachment: bool = False
    attachments: list[Attachment] = Field(default_factory=list)
    jump_url: str
    indexed_at: datetime | None = None
    file_search_doc_id: str | None = None

    def to_file_content(self) -> str:
        """File Search Store用のテキストコンテンツを生成"""
        lines = [
            "[メタデータ]",
            f"日時: {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"チャンネル: #{self.channel_name}",
        ]

        if self.thread_name:
            lines.append(f"スレッド: {self.thread_name}")

        lines.extend([
            f"発言者: @{self.author_name}",
            "",
            "[本文]",
            self.content,
        ])

        if self.attachments:
            lines.append("")
            lines.append("[添付ファイル]")
            for att in self.attachments:
                lines.append(f"ファイル名: {att.filename}")
                lines.append(f"種類: {att.content_type}")
                if att.ocr_text:
                    lines.append("")
                    lines.append("[添付ファイル内容]")
                    lines.append(att.ocr_text)

        return "\n".join(lines)


class SyncStatus(BaseModel):
    """同期状態"""

    sync_id: str
    status: str = "pending"  # pending, in_progress, completed, failed
    sync_type: str = "incremental"  # initial, incremental
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_channel_id: str | None = None
    last_message_id: str | None = None
    processed_count: int = 0
    error_count: int = 0
    error_messages: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """検索結果"""

    message: Message
    relevance_score: float | None = None
    snippet: str = ""
