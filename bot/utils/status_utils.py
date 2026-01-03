import discord

from bot.utils.status_message_store import get_status_message_id, set_status_message_id, clear_status_message_id

async def upsert_status_embed(guild: discord.Guild, embed: discord.Embed) -> discord.Message:
    status_channel = discord.utils.get(guild.text_channels, name="🛜bot-status")
    if not status_channel:
        status_channel = await guild.create_text_channel(name="🛜bot-status")

    msg_id = await get_status_message_id(guild.id)
    if msg_id:
        try:
            msg = await status_channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
            return msg
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await clear_status_message_id(guild.id)

    msg = await status_channel.send(embed=embed)
    await set_status_message_id(guild.id, msg.id)
    return msg
