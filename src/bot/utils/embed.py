"""Embed生成ユーティリティ"""

import discord
from src.core.models import Message, SearchResult


def create_search_result_embed(
    results: list[SearchResult],
    query: str,
) -> discord.Embed:
    """検索結果のEmbedを生成"""
    if not results:
        embed = discord.Embed(
            title="検索結果",
            description="該当するメッセージが見つかりませんでした",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="検索のヒント",
            value="- 別のキーワードで試してみてください\n- 期間を広げてみてください",
            inline=False,
        )
        return embed

    embed = discord.Embed(
        title=f"検索結果: {len(results)}件",
        description=f"クエリ: `{query}`",
        color=discord.Color.blue(),
    )

    for i, result in enumerate(results, 1):
        msg = result.message

        # 添付ファイル情報
        attachment_info = ""
        if msg.has_attachment:
            attachment_info = f" 📎{len(msg.attachments)}件"

        # 元のメッセージ本文（絵文字マーカー + 太字）
        content_line = ""
        if msg.content:
            # 長すぎる場合は切り詰め（Discord field valueは1024文字制限）
            content = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
            # 改行をスペースに置換してコンパクトに
            content = content.replace("\n", " ")
            content_line = f"\n💬 **{content}**\n\n"

        # 関連理由（Geminiからの説明）
        reason_line = ""
        if result.reason:
            reason_line = f"💡 {result.reason}\n"

        # ハイライト（クエリに関連する部分の引用）
        highlight = result.snippet
        if not highlight:
            highlight = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        if not highlight:
            highlight = "(添付ファイルのみ)"

        field_value = (
            f"**{msg.timestamp.strftime('%Y/%m/%d %H:%M')}** "
            f"#{msg.channel_name}{attachment_info}\n"
            f"{content_line}"
            f"{reason_line}"
            f"「{highlight}」\n"
            f"[ジャンプ]({msg.jump_url})"
        )

        embed.add_field(
            name=f"{i}. @{msg.author_name}",
            value=field_value,
            inline=False,
        )

    # 絞り込みヒント
    embed.set_footer(
        text="追加で条件を絞りますか？\n"
             "例: 「この中で添付ファイルがあるもの」「〇〇さんの発言だけ」"
    )

    return embed


def create_sync_result_embed(
    new_count: int,
    updated_count: int,
    error_count: int,
    elapsed_seconds: float,
) -> discord.Embed:
    """同期結果のEmbedを生成"""
    if error_count > 0:
        color = discord.Color.orange()
        status = "完了（エラーあり）"
    else:
        color = discord.Color.green()
        status = "完了"

    embed = discord.Embed(
        title=f"同期{status}",
        color=color,
    )

    embed.add_field(name="新規メッセージ", value=f"{new_count}件", inline=True)
    embed.add_field(name="更新", value=f"{updated_count}件", inline=True)
    embed.add_field(name="エラー", value=f"{error_count}件", inline=True)
    embed.add_field(name="所要時間", value=f"{elapsed_seconds:.1f}秒", inline=True)

    return embed
