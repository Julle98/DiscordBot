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
        self.console_log_channel_id = int(os.getenv("CONSOLE_LOG_CHANNEL_ID"))
        self.message_log = deque(maxlen=20)
        self.threshold_count = 10
        self.time_window = 30
        self.high_slowmode = 5
        self.low_slowmode = 2
        self.check_interval = 10
        self.last_slowmode = None

        bot.loop.create_task(self.initialize_slowmode_state())

        self.slowmode_task.start()

    async def initialize_slowmode_state(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        console_channel = self.bot.get_channel(self.console_log_channel_id)
        if channel:
            current_delay = channel.slowmode_delay
            if current_delay in (self.low_slowmode, self.high_slowmode):
                self.last_slowmode = current_delay
            else:
                if console_channel:
                    await self.send_embed(console_channel, current_delay, raised=None)
                self.last_slowmode = current_delay

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
        if raised is None:
            title = "🐌 Etanatila asetettu"
            color = discord.Color.orange()
        else:
            title = "🐌 Etanatila nostettu" if raised else "🐌 Etanatila laskettu"
            color = discord.Color.red() if raised else discord.Color.green()

        embed = discord.Embed(
            title=title,
            description=f"Uusi viestirajoitus: **{delay} sekuntia**",
            color=color
        )
        embed.set_footer(text="Automaattinen säätö viestimäärän perusteella")
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SlowmodeTracker(bot))