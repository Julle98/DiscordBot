from discord.ext import commands
from difflib import get_close_matches
import json
import os
from dotenv import load_dotenv
import logging

load_dotenv()
RESPONSES_PATH = os.getenv("RESPONSES_PATH")
logger = logging.getLogger(__name__)

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(RESPONSES_PATH, "r", encoding="utf-8") as f:
            self.responses = json.load(f)

    async def get_response(self, text: str) -> str:
        try:
            keys = list(self.responses.keys())
            match = get_close_matches(text.lower(), keys, n=1, cutoff=0.5)
            if match:
                logger.info(f"Match found: {match[0]}")
                return self.responses[match[0]]
            logger.warning(f"No match for: {text}")
            return "En ole varma mitä tarkoitit 🤔"
        except Exception as e:
            logger.error(f"Virhe get_response-metodissa: {e}")
            return "Tapahtui virhe vastauksen haussa 😕"
    
async def setup(bot):
    await bot.add_cog(AI(bot))