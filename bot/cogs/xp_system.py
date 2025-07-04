# cogs/xp_system.py
import discord, asyncio
from discord.ext import commands, tasks
from bot.utils.xp_utils import käsittele_viesti_xp, tarkkaile_kanavan_aktiivisuutta
from bot.utils.bot_setup import bot

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slowmode_watcher.start()     

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        await käsittele_viesti_xp(self.bot, message)

        await bot.process_commands(message)

    @tasks.loop(seconds=30)
    async def slowmode_watcher(self):
        await tarkkaile_kanavan_aktiivisuutta()

    @slowmode_watcher.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(XPSystem(bot))
