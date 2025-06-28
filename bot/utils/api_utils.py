import discord
from bot.utils.xp_utils import parse_xp_content
import os

async def hae_kayttajan_xp(bot: discord.Client, user_id: int):
    xp_channel = bot.get_channel(int(os.getenv("XP_CHANNEL_ID")))
    if not xp_channel:
        return {"viestit": 0, "xp": 0, "level": 0}

    async for msg in xp_channel.history(limit=1000):
        if msg.author.bot and msg.content.startswith(f"{user_id}:"):
            xp, level = parse_xp_content(msg.content)
            viestit = (xp // 10)  # Jos 10 XP per viesti
            return {"viestit": viestit, "xp": xp, "level": level}

    return {"viestit": 0, "xp": 0, "level": 0}
