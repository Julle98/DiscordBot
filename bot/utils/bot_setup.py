import os
from collections import deque
from dotenv import load_dotenv
import discord
from discord.ext import commands

intents = discord.Intents.all() 

load_dotenv()

APPLICATION_ID = int(os.getenv("APPLICATION_ID"))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_queue = deque()
        self.current_status = "Online"
        self.command_attempts = {}

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.tree.sync()

bot = MyBot(command_prefix="!", intents=intents)

