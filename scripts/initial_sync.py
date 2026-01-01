#!/usr/bin/env python
"""初回同期スクリプト

全メッセージを取得してインデックスを作成します。
レート制限を考慮してゆっくり実行します。
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.jobs.main import run_sync


async def main():
    print("=" * 50)
    print("Discord Search - 初回同期")
    print("=" * 50)
    print()
    print("全メッセージを取得してインデックスを作成します。")
    print("メッセージ数によっては時間がかかります。")
    print()

    confirm = input("続行しますか？ (y/N): ")
    if confirm.lower() != "y":
        print("キャンセルしました")
        return

    print()
    print("同期を開始します...")
    print()

    result = await run_sync(full_sync=True)

    print()
    print("=" * 50)
    print("結果:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
