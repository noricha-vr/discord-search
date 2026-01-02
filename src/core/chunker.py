"""会話チャンク生成ユーティリティ

メッセージを会話単位でグループ化し、RAG検索の精度を向上させる。
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from src.core.models import ConversationChunk, Message


def group_messages_into_chunks(
    messages: list[Message],
    time_window_minutes: int = 30,
    max_messages_per_chunk: int = 20,
    min_messages_per_chunk: int = 3,
) -> list[ConversationChunk]:
    """メッセージを会話チャンクにグループ化

    Args:
        messages: グループ化するメッセージ一覧
        time_window_minutes: 同一チャンクとみなす時間ウィンドウ（分）
        max_messages_per_chunk: 1チャンクの最大メッセージ数
        min_messages_per_chunk: 1チャンクの最小メッセージ数（コンテキスト保証）
    """
    if not messages:
        return []

    # チャンネル+スレッドでグループ化
    grouped: dict[tuple[str, str | None], list[Message]] = defaultdict(list)
    for msg in messages:
        key = (msg.channel_id, msg.thread_id)
        grouped[key].append(msg)

    chunks: list[ConversationChunk] = []
    time_window = timedelta(minutes=time_window_minutes)

    for (channel_id, thread_id), channel_messages in grouped.items():
        # 時間順にソート
        channel_messages.sort(key=lambda m: m.timestamp)

        # チャンクを生成
        channel_chunks = _create_chunks_for_channel(
            channel_messages,
            time_window,
            max_messages_per_chunk,
        )

        # 最小コンテキスト保証を適用
        channel_chunks = _ensure_minimum_context(
            channel_chunks,
            channel_messages,
            min_messages_per_chunk,
        )

        chunks.extend(channel_chunks)

    return chunks


def _create_chunks_for_channel(
    messages: list[Message],
    time_window: timedelta,
    max_messages: int,
) -> list[ConversationChunk]:
    """単一チャンネル/スレッドのメッセージをチャンクに分割"""
    if not messages:
        return []

    chunks: list[ConversationChunk] = []
    current_messages: list[Message] = []

    for msg in messages:
        # 新しいチャンクを開始すべきか判定
        should_start_new = False

        if not current_messages:
            should_start_new = False  # 最初のメッセージ
        elif len(current_messages) >= max_messages:
            should_start_new = True  # 最大数到達
        elif msg.timestamp - current_messages[-1].timestamp > time_window:
            should_start_new = True  # 時間ウィンドウ超過

        if should_start_new and current_messages:
            # 現在のチャンクを確定
            chunks.append(_create_chunk_from_messages(current_messages))
            current_messages = []

        current_messages.append(msg)

    # 残りのメッセージでチャンク作成
    if current_messages:
        chunks.append(_create_chunk_from_messages(current_messages))

    return chunks


def _create_chunk_from_messages(messages: list[Message]) -> ConversationChunk:
    """メッセージリストからConversationChunkを生成"""
    first_msg = messages[0]
    last_msg = messages[-1]

    # 参加者名を収集（重複排除、順序保持）
    participants: list[str] = []
    seen: set[str] = set()
    for msg in messages:
        if msg.author_name not in seen:
            participants.append(msg.author_name)
            seen.add(msg.author_name)

    return ConversationChunk(
        chunk_id=str(uuid.uuid4()),
        channel_id=first_msg.channel_id,
        channel_name=first_msg.channel_name,
        thread_id=first_msg.thread_id,
        thread_name=first_msg.thread_name,
        start_time=first_msg.timestamp,
        end_time=last_msg.timestamp,
        message_ids=[msg.message_id for msg in messages],
        participant_names=participants,
    )


def _ensure_minimum_context(
    chunks: list[ConversationChunk],
    all_messages: list[Message],
    min_count: int,
) -> list[ConversationChunk]:
    """各チャンクが最小メッセージ数を満たすよう、直前のメッセージを追加

    Args:
        chunks: 処理対象のチャンク一覧
        all_messages: 同一チャンネル/スレッドの全メッセージ（時間順）
        min_count: 最小メッセージ数
    """
    if not chunks or min_count <= 0:
        return chunks

    # メッセージIDからインデックスへのマップを作成
    msg_index: dict[str, int] = {
        msg.message_id: i for i, msg in enumerate(all_messages)
    }

    result: list[ConversationChunk] = []

    for chunk in chunks:
        if len(chunk.message_ids) >= min_count:
            result.append(chunk)
            continue

        # 不足分を計算
        needed = min_count - len(chunk.message_ids)

        # チャンク内の最初のメッセージのインデックスを取得
        first_msg_id = chunk.message_ids[0]
        first_idx = msg_index.get(first_msg_id, 0)

        # 直前のメッセージを追加
        prepend_ids: list[str] = []
        prepend_messages: list[Message] = []

        for i in range(first_idx - 1, max(first_idx - needed - 1, -1), -1):
            if i < 0:
                break
            prev_msg = all_messages[i]
            prepend_ids.insert(0, prev_msg.message_id)
            prepend_messages.insert(0, prev_msg)

        if prepend_ids:
            # 新しいチャンクを作成（前のメッセージを含む）
            new_message_ids = prepend_ids + chunk.message_ids

            # 参加者名を更新
            new_participants: list[str] = []
            seen: set[str] = set()
            for msg_id in new_message_ids:
                idx = msg_index.get(msg_id)
                if idx is not None:
                    name = all_messages[idx].author_name
                    if name not in seen:
                        new_participants.append(name)
                        seen.add(name)

            # 新しい開始時刻
            new_start_time = prepend_messages[0].timestamp if prepend_messages else chunk.start_time

            updated_chunk = ConversationChunk(
                chunk_id=chunk.chunk_id,
                channel_id=chunk.channel_id,
                channel_name=chunk.channel_name,
                thread_id=chunk.thread_id,
                thread_name=chunk.thread_name,
                start_time=new_start_time,
                end_time=chunk.end_time,
                message_ids=new_message_ids,
                participant_names=new_participants,
                indexed_at=chunk.indexed_at,
                file_search_doc_id=chunk.file_search_doc_id,
            )
            result.append(updated_chunk)
        else:
            # 追加できるメッセージがない場合はそのまま
            result.append(chunk)

    return result


def get_messages_for_chunk(
    chunk: ConversationChunk,
    all_messages: list[Message],
) -> list[Message]:
    """チャンクに含まれるメッセージを取得

    Args:
        chunk: 対象チャンク
        all_messages: 全メッセージ一覧
    """
    msg_map = {msg.message_id: msg for msg in all_messages}
    return [
        msg_map[msg_id]
        for msg_id in chunk.message_ids
        if msg_id in msg_map
    ]
