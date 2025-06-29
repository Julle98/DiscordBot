import random
import discord
from discord.ext import tasks, commands

last_status = None  

class StatusUpdater(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.listening = [
            "Ongelmianne | /komennot",
            "Komentojanne | /komennot",
            "Tehtäviänne | /komennot",
            "Ostoksianne | /komennot",
        ]
        self.watching = [
            "Wilma | /komennot",
            "Keskustelujanne | /komennot",
            "Schauplatz | /komennot",
            "Suorituksia | /komennot",
        ]
        self.playing = [
            "Abitti 2 | /komennot",
            "Tiedoillasi | /komennot",
            "Komennoilla | /komennot",
            "Matikkaeditori | /komennot",
        ]
        self.last_status: str | None = None
        self.update_status.start()

    def cog_unload(self):
        self.update_status.cancel()

    @tasks.loop(hours=6)
    async def update_status(self):
        cat = random.choice(("kuuntelee", "katsoo", "pelaa"))
        pool = {
            "kuuntelee": self.listening,
            "katsoo": self.watching,
            "pelaa": self.playing,
        }[cat]
        status = random.choice(pool)
        full = f"{cat} {status}"
        if full == self.last_status:
            return
        activity = (
            discord.Activity(type=discord.ActivityType.listening, name=status)
            if cat == "kuuntelee"
            else discord.Activity(type=discord.ActivityType.watching, name=status)
            if cat == "katsoo"
            else discord.Game(name=status)
        )
        await self.bot.change_presence(activity=activity)
        self.last_status = full
        print("Status vaihdettu:", full)

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusUpdater(bot))
