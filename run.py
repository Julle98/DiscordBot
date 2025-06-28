import asyncio
import os
import uvicorn
from dashboard.api import app
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))
import discord
from discord.ext import commands
from bot.main import load_cogs
from collections import deque
intents = discord.Intents.all()  

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_queue = deque()
        self.current_status = "Online"
        self.command_attempts = {}

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.tree.sync()

bot = MyBot(command_prefix="/", intents=intents)

async def main():
    await load_cogs()
    await asyncio.gather(
        bot.start(os.getenv("DISCORD_BOT_TOKEN")),
        uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000)).serve()
    )

if __name__ == "__main__":
    asyncio.run(main())
