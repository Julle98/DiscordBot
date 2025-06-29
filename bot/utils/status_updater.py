import random, discord
from discord.ext import commands, tasks

class StatusUpdater(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_status.start()         

    def cog_unload(self):
        self.update_status.cancel()

    listening = ["Ongelmianne | /komennot", "Komentojanne | /komennot",
                 "Tehtäviänne | /komennot", "Ostoksianne | /komennot"]
    watching  = ["Wilma | /komennot", "Keskustelujanne | /komennot",
                 "Schauplatz | /komennot", "Suorituksia | /komennot"]
    playing   = ["Abitti 2 | /komennot", "Tiedoillasi | /komennot",
                 "Komennoilla | /komennot", "Matikkaeditori | /komennot"]

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

    @update_status.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(StatusUpdater(bot))
