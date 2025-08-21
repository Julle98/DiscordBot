import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

class SlowmodeWatcher(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel_id: int = int(os.getenv("SLOWMODE_CHANNEL_ID"))
        self.log_channel_id: int = int(os.getenv("CONSOLE_LOG"))
        self.channel: discord.TextChannel | None = None
        self.log_channel: discord.TextChannel | None = None

    async def cog_load(self) -> None:
        self.watch_loop.start()

    async def cog_unload(self) -> None:
        self.watch_loop.cancel()

    @tasks.loop(seconds=30)
    async def watch_loop(self):
        if self.channel is None:
            return

        now = datetime.now(timezone.utc)
        active_messages = 0

        try:
            async for msg in self.channel.history(limit=100, after=now - timedelta(seconds=30)):
                if not msg.author.bot:
                    active_messages += 1
        except Exception as exc:
            print(f"[Etanatila] Virhe viestien haussa: {exc}")
            return

        try:
            if active_messages >= 15 and self.channel.slowmode_delay < 5:
                await self.channel.edit(slowmode_delay=5)
                await self._send_log("🚨 Viestejä tulee paljon! Etanatila nostettu 5 sekuntiin.")
            elif active_messages < 3 and self.channel.slowmode_delay != 2:
                await self.channel.edit(slowmode_delay=2)
                await self._send_log("✅ Viestimäärä laskenut. Etanatila palautettu 2 sekuntiin.")
        except Exception as exc:
            print(f"[Etanatila] Virhe hidastustilan muokkauksessa: {exc}")

    @watch_loop.before_loop
    async def before_watch_loop(self):
        await self.bot.wait_until_ready()
        self.channel = self.bot.get_channel(self.channel_id)
        self.log_channel = self.bot.get_channel(self.log_channel_id)

        if self.channel is None:
            print("[Etanatila] Kanavaa ei löytynyt (SLOWMODE_CHANNEL_ID).")
            return

        try:
            if self.channel.slowmode_delay != 2:
                await self.channel.edit(slowmode_delay=2)
                await self._send_log("🔄 Etanatila asetettu oletukseksi 2 sekuntiin.")
        except Exception as exc:
            print(f"[Etanatila] Virhe oletusetanatilan asetuksessa: {exc}")

    async def _send_log(self, message: str) -> None:
        if self.log_channel:
            await self.log_channel.send(message)
        if self.channel:
            await self.channel.send(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(SlowmodeWatcher(bot))
