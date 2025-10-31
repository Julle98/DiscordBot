from discord.ext import commands
from bot.utils.bot_setup import bot
from difflib import get_close_matches
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()
RESPONSES_PATH = os.getenv("RESPONSES_PATH")
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
logger = logging.getLogger(__name__)

async def send_to_channel(channel_id: int, message: str):
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(RESPONSES_PATH, "r", encoding="utf-8") as f:
            self.responses = json.load(f)

    def get_time_response(self, text: str) -> str:
        now = datetime.now()
        text = text.lower()

        if "aika" in text:
            return f"Nyt on kello {now.strftime('%H:%M')}."
        elif "päivä" in text:
            return f"Tänään on {now.strftime('%A')} ({now.strftime('%d.%m.%Y')})."
        elif "vuosi" in text:
            return f"Nyt on vuosi {now.year}."
        elif "kuukausi" in text:
            return f"Nyt on {now.strftime('%B')}."
        elif "viikkonumero" in text or "viikko" in text:
            return f"Nyt on viikko {now.isocalendar().week}."
        elif "vuorokausi" in text:
            hour = now.hour
            if 5 <= hour < 12:
                return "Nyt on aamu."
            elif 12 <= hour < 18:
                return "Nyt on päivä."
            elif 18 <= hour < 23:
                return "Nyt on ilta."
            else:
                return "Nyt on yö."
        return None

    async def get_response(self, text: str) -> str:
        try:
            time_response = self.get_time_response(text)
            if time_response:
                return time_response

            keys = list(self.responses.keys())
            match = get_close_matches(text.lower(), keys, n=1, cutoff=0.5)
            if match:
                logger.info(f"Match found: {match[0]}")
                return self.responses[match[0]]

            logger.warning(f"No match for: {text}")
            await self.log_unmatched_message(text)
            return "En ole varma mitä tarkoitit 🤔"
        except Exception as e:
            logger.error(f"Virhe get_response-metodissa: {e}")
            return "Tapahtui virhe vastauksen haussa 😕"

    async def log_unmatched_message(self, text: str):
        if MOD_LOG_CHANNEL_ID:
            try:
                await send_to_channel(MOD_LOG_CHANNEL_ID, f"🛑 Ei löytynyt vastausta viestille: `{text}`")
            except Exception as e:
                logger.error(f"Lokitus epäonnistui: {e}")
    
async def setup(bot):
    await bot.add_cog(AI(bot))