from discord.ext import commands
from difflib import get_close_matches
import json
import os
from dotenv import load_dotenv

load_dotenv()
RESPONSES_PATH = os.getenv("RESPONSES_PATH")

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(RESPONSES_PATH, "r", encoding="utf-8") as f:
            self.responses = json.load(f)

    async def get_response(self, text: str):
        keys = list(self.responses.keys())
        match = get_close_matches(text.lower(), keys, n=1, cutoff=0.5)
        if match:
            return self.responses[match[0]]
        return "En ole varma mitä tarkoitit 🤔"
    
async def setup(bot):
    await bot.add_cog(AI(bot))