"""Firestore クライアント"""

from datetime import datetime
from google.cloud import firestore

from src.core.config import settings
from src.core.models import ConversationChunk, Message, SyncStatus, Attachment


class FirestoreClient:
    """Firestore操作クラス"""

    def __init__(self):
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.messages_ref = self.db.collection("messages")
        self.chunks_ref = self.db.collection("conversation_chunks")
        self.sync_status_ref = self.db.collection("sync_status")
        self.config_ref = self.db.collection("config")
        self.channels_ref = self.db.collection("synced_channels")

    # --- Messages ---

    async def save_message(self, message: Message) -> None:
        """メッセージを保存"""
        doc_ref = self.messages_ref.document(message.message_id)
        doc_ref.set(message.model_dump(mode="json"))

    async def get_message(self, message_id: str) -> Message | None:
        """メッセージを取得"""
        doc = self.messages_ref.document(message_id).get()
        if doc.exists:
            return Message(**doc.to_dict())
        return None

    async def get_messages_by_ids(self, message_ids: list[str]) -> list[Message]:
        """複数のメッセージを取得"""
        messages = []
        for message_id in message_ids:
            msg = await self.get_message(message_id)
            if msg:
                messages.append(msg)
        return messages

    async def message_exists(self, message_id: str) -> bool:
        """メッセージが存在するか確認"""
        doc = self.messages_ref.document(message_id).get()
        return doc.exists

    async def get_all_messages(self) -> list[Message]:
        """全メッセージを取得（再インデックス用）"""
        messages = []
        docs = self.messages_ref.stream()
        for doc in docs:
            messages.append(Message(**doc.to_dict()))
        return messages

    # --- Conversation Chunks ---

    async def save_chunk(self, chunk: ConversationChunk) -> None:
        """会話チャンクを保存"""
        doc_ref = self.chunks_ref.document(chunk.chunk_id)
        doc_ref.set(chunk.model_dump(mode="json"))

    async def get_chunk(self, chunk_id: str) -> ConversationChunk | None:
        """会話チャンクを取得"""
        doc = self.chunks_ref.document(chunk_id).get()
        if doc.exists:
            return ConversationChunk(**doc.to_dict())
        return None

    async def get_chunk_by_message_id(self, message_id: str) -> ConversationChunk | None:
        """メッセージIDから所属チャンクを取得"""
        docs = (
            self.chunks_ref
            .where("message_ids", "array_contains", message_id)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return ConversationChunk(**doc.to_dict())
        return None

    async def get_all_chunks(self) -> list[ConversationChunk]:
        """全チャンクを取得"""
        chunks = []
        docs = self.chunks_ref.stream()
        for doc in docs:
            chunks.append(ConversationChunk(**doc.to_dict()))
        return chunks

    async def delete_all_chunks(self) -> int:
        """全チャンクを削除（再インデックス用）

        Returns:
            削除したチャンク数
        """
        deleted_count = 0
        docs = self.chunks_ref.stream()
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        return deleted_count

    # --- Sync Status ---

    async def create_sync_status(self, sync_id: str, sync_type: str = "incremental") -> SyncStatus:
        """同期ステータスを作成"""
        status = SyncStatus(
            sync_id=sync_id,
            status="in_progress",
            sync_type=sync_type,
            started_at=datetime.utcnow(),
        )
        self.sync_status_ref.document(sync_id).set(status.model_dump(mode="json"))
        return status

    async def update_sync_progress(
        self,
        sync_id: str,
        last_channel_id: str | None = None,
        last_message_id: str | None = None,
        processed_count: int | None = None,
    ) -> None:
        """同期進捗を更新"""
        update_data = {}
        if last_channel_id:
            update_data["last_channel_id"] = last_channel_id
        if last_message_id:
            update_data["last_message_id"] = last_message_id
        if processed_count is not None:
            update_data["processed_count"] = processed_count
        if update_data:
            self.sync_status_ref.document(sync_id).update(update_data)

    async def complete_sync(self, sync_id: str, error_count: int = 0) -> None:
        """同期完了"""
        self.sync_status_ref.document(sync_id).update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "error_count": error_count,
        })

    async def fail_sync(self, sync_id: str, error_message: str) -> None:
        """同期失敗"""
        doc = self.sync_status_ref.document(sync_id).get()
        errors = doc.to_dict().get("error_messages", []) if doc.exists else []
        errors.append(error_message)
        self.sync_status_ref.document(sync_id).update({
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error_messages": errors,
        })

    async def get_last_sync_status(self) -> SyncStatus | None:
        """最後の同期ステータスを取得"""
        docs = (
            self.sync_status_ref
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return SyncStatus(**doc.to_dict())
        return None

    # --- Config ---

    async def get_last_sync_time(self) -> datetime | None:
        """最後の同期時刻を取得"""
        doc = self.config_ref.document("sync").get()
        if doc.exists:
            data = doc.to_dict()
            last_sync = data.get("last_sync_at")
            if last_sync:
                if isinstance(last_sync, str):
                    return datetime.fromisoformat(last_sync)
                return last_sync
        return None

    async def update_last_sync_time(self, sync_time: datetime) -> None:
        """最後の同期時刻を更新"""
        self.config_ref.document("sync").set({
            "last_sync_at": sync_time.isoformat(),
            "initial_sync_completed": True,
        }, merge=True)

    # --- Synced Channels ---

    async def get_synced_channel_ids(self) -> set[str]:
        """同期済みチャンネルIDの一覧を取得"""
        channel_ids = set()
        docs = self.channels_ref.stream()
        for doc in docs:
            channel_ids.add(doc.id)
        return channel_ids

    async def mark_channel_synced(
        self,
        channel_id: str,
        channel_name: str,
        first_synced_at: datetime | None = None,
    ) -> None:
        """チャンネルを同期済みとしてマーク"""
        now = datetime.utcnow()
        doc_ref = self.channels_ref.document(channel_id)
        doc = doc_ref.get()

        if doc.exists:
            # 既存: last_synced_atのみ更新
            doc_ref.update({
                "channel_name": channel_name,
                "last_synced_at": now.isoformat(),
            })
        else:
            # 新規: 全フィールド設定
            doc_ref.set({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "first_synced_at": (first_synced_at or now).isoformat(),
                "last_synced_at": now.isoformat(),
            })

    async def get_synced_channels_info(self) -> list[dict]:
        """同期済みチャンネルの詳細情報を取得"""
        channels = []
        docs = self.channels_ref.stream()
        for doc in docs:
            channels.append(doc.to_dict())
        return channels

    async def get_message_count_by_channel(self) -> dict[str, int]:
        """チャンネルごとのメッセージ数を取得"""
        from collections import defaultdict
        counts = defaultdict(int)
        docs = self.messages_ref.stream()
        for doc in docs:
            data = doc.to_dict()
            channel_id = data.get("channel_id")
            if channel_id:
                counts[channel_id] += 1
        return dict(counts)


# シングルトンインスタンス
firestore_client = FirestoreClient()
