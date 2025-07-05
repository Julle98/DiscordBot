# cogs/xp_system.py
import discord, asyncio
from discord.ext import commands, tasks
from bot.utils.xp_utils import käsittele_viesti_xp, tarkkaile_kanavan_aktiivisuutta
from bot.utils.bot_setup import bot
from collections import defaultdict
from datetime import datetime, timedelta

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slowmode_watcher.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        user_id = message.author.id
        komento_nimi = "xp_viesti"
        nyt = datetime.now()

        member = message.guild.get_member(user_id)
        nopea_roolit = ["Mestari", "Admin", "Moderaattori"]
        nopea = any(r.name in nopea_roolit for r in member.roles) if member else False
        raja = timedelta(seconds=5 if nopea else 10)

        viimeinen = komento_ajastukset[user_id].get(komento_nimi)
        if viimeinen and nyt - viimeinen < raja:
            return  

        viestit_ja_ajat[message.id] = (user_id, nyt)

        komento_ajastukset[user_id][komento_nimi] = nyt
        await käsittele_viesti_xp(self.bot, message)
        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        tiedot = viestit_ja_ajat.pop(message.id, None)
        if tiedot:
            user_id, aika = tiedot
            nyt = datetime.now()
            if nyt - aika < timedelta(seconds=10):
                komento_ajastukset[user_id].pop("xp_viesti", None)

    @tasks.loop(seconds=30)
    async def slowmode_watcher(self):
        await tarkkaile_kanavan_aktiivisuutta()

    @slowmode_watcher.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(XPSystem(bot))

