import random
import asyncio
import discord
from discord.ext import tasks

# Statuslistat
listening_statuses = [
    "Ongelmianne | /komennot",
    "Komentojanne | /komennot",
    "Tehtäviänne | /komennot",
    "Ostoksianne | /komennot"
]

watching_statuses = [
    "Wilma | /komennot",  
    "Keskustelujanne | /komennot",
    "Schauplatz | /komennot",
    "Suorituksia | /komennot"
]

playing_statuses = [
    "Abitti 2 | /komennot",  
    "Tiedoillasi | /komennot",
    "Komennoilla | /komennot",
    "Matikkaeditori | /komennot"
]

last_status = None  

@tasks.loop(hours=6)
async def update_status(self):
        cat = random.choice(["kuuntelee", "katsoo", "pelaa"])
        pool = {"kuuntelee": self.listening,
                "katsoo":    self.watching,
                "pelaa":     self.playing}[cat]

        status = random.choice(pool)
        full   = f"{cat} {status}"
        if full == self.last_status:       
            return

        activity = (discord.Activity(type=discord.ActivityType.listening, name=status)   if cat=="kuuntelee"
                    else discord.Activity(type=discord.ActivityType.watching,  name=status) if cat=="katsoo"
                    else discord.Game(name=status))
        await self.bot.change_presence(activity=activity)
        self.last_status = full
        print("Status vaihdettu:", full)