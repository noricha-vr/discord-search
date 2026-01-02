#!/usr/bin/env python
"""再インデックススクリプト（会話チャンク方式）

既存のメッセージを会話チャンク単位でグループ化し、
Gemini File Search Storeに再インデックスします。
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from src.core.chunker import get_messages_for_chunk, group_messages_into_chunks
from src.core.firestore import firestore_client
from src.core.gemini import gemini_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def reindex_with_conversation_chunks(
    time_window_minutes: int = 30,
    max_messages_per_chunk: int = 20,
    min_messages_per_chunk: int = 3,
    dry_run: bool = False,
) -> dict:
    """会話チャンク方式で再インデックス

    Args:
        time_window_minutes: 同一チャンクとみなす時間ウィンドウ（分）
        max_messages_per_chunk: 1チャンクの最大メッセージ数
        min_messages_per_chunk: 1チャンクの最小メッセージ数（コンテキスト保証）
        dry_run: Trueの場合、インデックスせずにチャンク情報のみ表示
    """
    logger.info("=" * 50)
    logger.info("会話チャンク方式による再インデックス開始")
    logger.info("=" * 50)
    logger.info(f"設定: time_window={time_window_minutes}分, "
                f"max={max_messages_per_chunk}, min={min_messages_per_chunk}")

    # Step 1: 既存のFile Search Storeファイルを削除
    if not dry_run:
        logger.info("Step 1: 既存のFile Search Storeファイルを削除中...")
        deleted_files = await gemini_client.delete_all_files_in_store()
        logger.info(f"  {deleted_files}件のファイルを削除")

        # Firestoreの既存チャンクも削除
        deleted_chunks = await firestore_client.delete_all_chunks()
        logger.info(f"  {deleted_chunks}件のチャンクを削除")
    else:
        logger.info("Step 1: [DRY RUN] ファイル削除をスキップ")

    # Step 2: Firestoreから全メッセージを取得
    logger.info("Step 2: Firestoreから全メッセージを取得中...")
    all_messages = await firestore_client.get_all_messages()
    logger.info(f"  {len(all_messages)}件のメッセージを取得")

    if not all_messages:
        logger.warning("メッセージがありません。終了します。")
        return {"chunks": 0, "messages": 0, "indexed": 0, "errors": 0}

    # Step 3: メッセージを会話チャンクにグループ化
    logger.info("Step 3: 会話チャンクにグループ化中...")
    chunks = group_messages_into_chunks(
        all_messages,
        time_window_minutes=time_window_minutes,
        max_messages_per_chunk=max_messages_per_chunk,
        min_messages_per_chunk=min_messages_per_chunk,
    )
    logger.info(f"  {len(chunks)}個のチャンクを生成")

    # チャンク統計
    total_messages_in_chunks = sum(len(c.message_ids) for c in chunks)
    avg_messages = total_messages_in_chunks / len(chunks) if chunks else 0
    logger.info(f"  平均メッセージ数/チャンク: {avg_messages:.1f}")

    if dry_run:
        logger.info("\n[DRY RUN] チャンク詳細:")
        for i, chunk in enumerate(chunks[:10], 1):
            logger.info(f"  Chunk {i}: #{chunk.channel_name} "
                       f"({chunk.start_time.strftime('%Y-%m-%d %H:%M')} - "
                       f"{chunk.end_time.strftime('%H:%M')}) "
                       f"messages={len(chunk.message_ids)}")
        if len(chunks) > 10:
            logger.info(f"  ... and {len(chunks) - 10} more chunks")
        return {
            "chunks": len(chunks),
            "messages": total_messages_in_chunks,
            "indexed": 0,
            "errors": 0,
        }

    # メッセージIDからMessageオブジェクトへのマップを作成
    msg_map = {msg.message_id: msg for msg in all_messages}

    # Step 4: 各チャンクをインデックス
    logger.info("Step 4: チャンクをインデックス中...")
    indexed_count = 0
    error_count = 0

    for i, chunk in enumerate(chunks, 1):
        try:
            # チャンク内のメッセージを取得
            chunk_messages = [
                msg_map[msg_id]
                for msg_id in chunk.message_ids
                if msg_id in msg_map
            ]

            if not chunk_messages:
                logger.warning(f"チャンク {chunk.chunk_id}: メッセージが見つかりません")
                error_count += 1
                continue

            # Geminiにインデックス
            doc_id = await gemini_client.index_conversation_chunk(chunk, chunk_messages)

            if doc_id:
                # Firestoreにチャンクを保存
                chunk.file_search_doc_id = doc_id
                chunk.indexed_at = datetime.utcnow()
                await firestore_client.save_chunk(chunk)

                indexed_count += 1

                if indexed_count % 10 == 0:
                    logger.info(f"  進捗: {indexed_count}/{len(chunks)} チャンク完了")
            else:
                error_count += 1
                logger.warning(f"チャンク {chunk.chunk_id}: インデックス失敗")

        except Exception as e:
            logger.error(f"チャンク {chunk.chunk_id}: エラー - {e}")
            error_count += 1

        # レート制限対策
        if i % 5 == 0:
            await asyncio.sleep(1)

    logger.info("=" * 50)
    logger.info("再インデックス完了")
    logger.info(f"  チャンク数: {len(chunks)}")
    logger.info(f"  メッセージ数: {total_messages_in_chunks}")
    logger.info(f"  インデックス成功: {indexed_count}")
    logger.info(f"  エラー: {error_count}")
    logger.info("=" * 50)

    return {
        "chunks": len(chunks),
        "messages": total_messages_in_chunks,
        "indexed": indexed_count,
        "errors": error_count,
    }


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="会話チャンク方式による再インデックス"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="インデックスせずにチャンク情報のみ表示"
    )
    parser.add_argument(
        "--time-window",
        type=int,
        default=30,
        help="時間ウィンドウ（分）デフォルト: 30"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=20,
        help="1チャンクの最大メッセージ数 デフォルト: 20"
    )
    parser.add_argument(
        "--min-messages",
        type=int,
        default=3,
        help="1チャンクの最小メッセージ数 デフォルト: 3"
    )

    args = parser.parse_args()

    print()
    print("=" * 60)
    print("Discord Search - 会話チャンク方式による再インデックス")
    print("=" * 60)
    print()
    print("このスクリプトは以下を実行します:")
    print("  1. 既存のFile Search Storeファイルを全削除")
    print("  2. Firestoreの既存チャンクを全削除")
    print("  3. 全メッセージを会話チャンクにグループ化")
    print("  4. 各チャンクをGeminiにインデックス")
    print()

    if args.dry_run:
        print("[DRY RUN モード] 削除・インデックスは実行されません")
        print()

    if not args.dry_run:
        confirm = input("続行しますか？ (yes/no): ")
        if confirm.lower() != "yes":
            print("キャンセルしました")
            return

    result = await reindex_with_conversation_chunks(
        time_window_minutes=args.time_window,
        max_messages_per_chunk=args.max_messages,
        min_messages_per_chunk=args.min_messages,
        dry_run=args.dry_run,
    )

    print()
    print("=" * 60)
    print("結果サマリー:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
