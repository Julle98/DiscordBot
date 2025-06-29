import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

class SlowmodeWatcher(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel_id: int = int(os.getenv("SLOWMODE_CHANNEL_ID", "0"))
        self._task: asyncio.Task | None = self.bot.loop.create_task(
            self._watch_channel()
        )

    async def cog_unload(self) -> None:  
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch_channel(self) -> None:
        await self.bot.wait_until_ready()

        channel: discord.TextChannel | None = self.bot.get_channel(self.channel_id)  
        if channel is None:
            print("[SlowmodeWatcher] Kanavaa ei löytynyt (SLOWMODE_CHANNEL_ID).")
            return

        while not self.bot.is_closed():
            now = datetime.now(timezone.utc)
            active_messages = 0

            try:
                async for msg in channel.history(limit=100, after=now - timedelta(seconds=30)):
                    if not msg.author.bot:
                        active_messages += 1
            except Exception as exc:
                print(f"[SlowmodeWatcher] Virhe viestien haussa: {exc}")
                await asyncio.sleep(30)
                continue

            try:
                if active_messages >= 15 and channel.slowmode_delay == 0:
                    await channel.edit(slowmode_delay=5)
                    print("[SlowmodeWatcher] Hidastustila asetettu 5 sekuntiin.")
                elif active_messages < 3 and channel.slowmode_delay > 0:
                    await channel.edit(slowmode_delay=0)
                    print("[SlowmodeWatcher] Hidastustila poistettu.")
            except Exception as exc:
                print(f"[SlowmodeWatcher] Virhe hidastustilan muokkauksessa: {exc}")

            await asyncio.sleep(30)

async def setup(bot: commands.Bot):
    await bot.add_cog(SlowmodeWatcher(bot))
