import discord
from discord.ext import commands, tasks
from collections import deque
import os
from dotenv import load_dotenv
import time
from datetime import datetime

class SlowmodeTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.slowmode_channel_id = int(os.getenv("SLOWMODE_CHANNEL_ID"))
        self.console_log_channel_id = int(os.getenv("CONSOLE_LOG"))
        self.message_log = deque(maxlen=100)
        self.threshold_count = 10     # viestiraja
        self.time_window = 10         # sekuntia
        self.high_slowmode = 5
        self.low_slowmode = 2
        self.last_slowmode = None

        self.pending_state = None
        self.pending_count = 0

        self.last_log_time = 0
        self.log_cooldown = 10

        bot.loop.create_task(self.initialize_slowmode_state())
        self.slowmode_task.start()

    async def initialize_slowmode_state(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.slowmode_channel_id)
        console_channel = self.bot.get_channel(self.console_log_channel_id)

        if not channel:
            return

        current_delay = channel.slowmode_delay
        if current_delay == self.high_slowmode:
            await channel.edit(slowmode_delay=self.low_slowmode)
            await self.send_embed(console_channel or channel, self.low_slowmode, raised=False, count=0)

        self.last_slowmode = channel.slowmode_delay

    def cog_unload(self):
        self.slowmode_task.cancel()

    def log_message(self, message: discord.Message):
        if message.channel.id == self.slowmode_channel_id and not message.author.bot:
            self.message_log.append(time.time())

    @tasks.loop(seconds=5) 
    async def slowmode_task(self):
        now = time.time()
        while self.message_log and now - self.message_log[0] > self.time_window:
            self.message_log.popleft()

        channel = self.bot.get_channel(self.slowmode_channel_id)
        console_channel = self.bot.get_channel(self.console_log_channel_id)
        if not channel:
            return

        count = len(self.message_log)
        desired_state = self.high_slowmode if count >= self.threshold_count else self.low_slowmode

        if desired_state != self.last_slowmode:
            if self.pending_state == desired_state:
                self.pending_count += 1
                if self.pending_count >= 2:
                    await channel.edit(slowmode_delay=desired_state)
                    await self.send_embed(channel, desired_state, raised=(desired_state == self.high_slowmode), count=count)
                    if console_channel:
                        await self.send_embed(console_channel, desired_state, raised=(desired_state == self.high_slowmode), count=count)
                    self.last_slowmode = desired_state
                    self.pending_state = None
                    self.pending_count = 0
            else:
                self.pending_state = desired_state
                self.pending_count = 1

    async def send_embed(self, channel, delay, raised, count):
        now_ts = time.time()
        if now_ts - self.last_log_time < self.log_cooldown:
            return
        self.last_log_time = now_ts

        now = datetime.now().strftime("%H:%M:%S")
        title = "🐌 Etanatila nostettu" if raised else "🐌 Etanatila laskettu"
        color = discord.Color.red() if raised else discord.Color.green()
        direction = "🔺 Nousi" if raised else "🔻 Laski"

        description = (
            f"**{direction}** – uusi viestirajoitus: **{delay} sekuntia**\n"
            f"💬 Viestejä viimeisen {self.time_window}s aikana: **{count}/{self.threshold_count}**\n"
            f"⏰ Aikaleima: `{now}`"
        )

        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Automaattinen säätö viestimäärän perusteella")
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SlowmodeTracker(bot))