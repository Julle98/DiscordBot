import random
from typing import Optional, List, Tuple

import discord
from discord.ext import tasks, commands

def _cog(bot: commands.Bot) -> Optional[commands.Cog]:
    return bot.get_cog("StatusUpdater")

async def update_status(bot: commands.Bot):
    cog = _cog(bot)
    if cog:
        await cog.update_status()

async def force_status_update(bot: commands.Bot) -> None:
    cog = _cog(bot)
    if cog:
        await cog.update_status_once()

def get_last_status(bot: commands.Bot) -> Optional[str]:
    cog = _cog(bot)
    return cog.last_status if cog else None

class StatusUpdater(commands.Cog):

    LISTENING: List[str] = [
        "Ongelmat | /komennot",
        "Komennot | /komennot",
        "Tehtävät | /komennot",
        "Ostokset | /komennot",
    ]
    WATCHING: List[str] = [
        "Wilma | /komennot",
        "TV | /komennot",
        "YouTube | /komennot",
        "TikTok | /komennot",
    ]
    PLAYING: List[str] = [
        "Abitti | /komennot",
        "Matikka | /komennot",
        "Sanapeli | /komennot",
        "Koodia | /komennot",
        "Facebook | /komennot",
        "Candy Crush | /komennot",
    ]
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_status: Optional[str] = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.update_status.is_running():
            self.update_status.start()

    def _choose_status(self) -> Tuple[discord.BaseActivity, str]:
        cat = random.choice(("kuuntelee", "katsoo", "pelaa"))
        pool = {
            "kuuntelee": self.LISTENING,
            "katsoo": self.WATCHING,
            "pelaa": self.PLAYING,
        }[cat]
        status = random.choice(pool)
        full = f"{cat} {status}"
        activity: discord.BaseActivity = (
            discord.Activity(type=discord.ActivityType.listening, name=status)
            if cat == "kuuntelee"
            else discord.Activity(type=discord.ActivityType.watching, name=status)
            if cat == "katsoo"
            else discord.Game(name=status)
        )
        return activity, full

    @tasks.loop(hours=6)
    async def update_status(self):
        activity, full = self._choose_status()
        if full == self.last_status:
            return
        await self.bot.change_presence(activity=activity)
        self.last_status = full
        print("Status vaihdettu:", full)

    async def update_status_once(self) -> None:
        activity, full = self._choose_status()
        await self.bot.change_presence(activity=activity)
        self.last_status = full
        print("Status päivitetty käsin:", full)

    def cog_unload(self):
        self.update_status.cancel()

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusUpdater(bot))
