"""Firestore クライアント"""

from datetime import datetime
from google.cloud import firestore

from src.core.config import settings
from src.core.models import Message, SyncStatus, Attachment


class FirestoreClient:
    """Firestore操作クラス"""

    def __init__(self):
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.messages_ref = self.db.collection("messages")
        self.sync_status_ref = self.db.collection("sync_status")
        self.config_ref = self.db.collection("config")

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


# シングルトンインスタンス
firestore_client = FirestoreClient()
