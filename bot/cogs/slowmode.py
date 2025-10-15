import discord
from discord.ext import commands, tasks
from collections import deque
import os
from dotenv import load_dotenv
import asyncio

class SlowmodeTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.channel_id = int(os.getenv("SLOWMODE_CHANNEL_ID"))
        self.message_log = deque(maxlen=20)
        self.threshold_count = 10
        self.time_window = 30
        self.high_slowmode = 5
        self.low_slowmode = 2
        self.check_interval = 10
        self.last_slowmode = None 
        self.slowmode_task.start()

    def cog_unload(self):
        self.slowmode_task.cancel()

    def log_message(self, message: discord.Message):
        if message.channel.id == self.channel_id and not message.author.bot:
            self.message_log.append(message.created_at.timestamp())

    @tasks.loop(seconds=10)
    async def slowmode_task(self):
        now = asyncio.get_event_loop().time()
        recent = [t for t in self.message_log if now - t < self.time_window]
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        try:
            if not recent:
                return

            new_delay = self.high_slowmode if len(recent) >= self.threshold_count else self.low_slowmode

            if new_delay != channel.slowmode_delay:
                await channel.edit(slowmode_delay=new_delay)

            if new_delay != self.last_slowmode:
                await self.send_embed(channel, new_delay, new_delay == self.high_slowmode)
                self.last_slowmode = new_delay

        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    async def send_embed(self, channel, delay, raised):
        color = discord.Color.red() if raised else discord.Color.green()
        title = "🐌 Etanatila nostettu" if raised else "🐌 Etanatila laskettu"
        embed = discord.Embed(
            title=title,
            description=f"Uusi viestirajoitus: **{delay} sekuntia**",
            color=color
        )
        embed.set_footer(text="Automaattinen säätö viestimäärän perusteella")
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SlowmodeTracker(bot))