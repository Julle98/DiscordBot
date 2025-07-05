import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))

import asyncio
import uvicorn
from dashboard.api import app
import discord
from discord.ext import commands
from bot.main import load_cogs
from bot.utils.bot_setup import bot 

async def main():
    await load_cogs()
    await asyncio.gather(
        bot.start(os.getenv("DISCORD_BOT_TOKEN")),
    )

if __name__ == "__main__":
    asyncio.run(main())

