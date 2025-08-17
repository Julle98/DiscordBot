import discord, asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict
import random
from io import BytesIO

from bot.utils.bot_setup import bot
from bot.utils.xp_utils import (
    käsittele_viesti_xp,
    tarkkaile_kanavan_aktiivisuutta,
    käsittele_dm_viesti,
)
from bot.utils.tiedot_utils import pending_file_sends
from utils.xp_bonus import käsittele_xp_bonus

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}
viime_viestit = {}    # {user_id: datetime}

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slowmode_watcher.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            await käsittele_dm_viesti(self.bot, message)
            return

        request = pending_file_sends.get(message.author.id)
        if request:
            del pending_file_sends[message.author.id]
            try:
                liite = message.attachments[0]
                tiedosto = await liite.read()
                buffer = BytesIO(tiedosto)

                await request["kohde"].send(
                    content=(
                        f"✅ **{request['otsikko']}**\n"
                        f"Tarkista liitteenä oleva tiedosto.\n"
                        f"Ota yhteyttä ylläpitoon, jos jokin ei täsmää."
                    ),
                    file=discord.File(buffer, filename=liite.filename)
                )

                await message.channel.send(
                    f"✅ Tiedosto toimitettiin yksityisviestillä käyttäjälle {request['kohde'].mention}."
                )
            except discord.Forbidden:
                await message.channel.send("⚠️ Käyttäjälle ei voitu lähettää tiedostoa yksityisviestillä.")
            except Exception as e:
                await message.channel.send(f"⚠️ Tiedoston lähetys epäonnistui: {e}")

        user_id = message.author.id
        komento_nimi = "xp_viesti"
        nyt = datetime.now(timezone.utc)

        komento_ajastukset.setdefault(user_id, {})
        viimeinen = komento_ajastukset[user_id].get(komento_nimi)

        member = message.guild.get_member(user_id)
        nopea_roolit = ["Mestari", "Admin", "Moderaattori"]
        nopea = any(r.name in nopea_roolit for r in member.roles) if member else False
        raja = timedelta(seconds=5 if nopea else 10)

        if not viimeinen or nyt - viimeinen >= raja:
            await käsittele_xp_bonus(message, user_id, nyt)
            komento_ajastukset[user_id][komento_nimi] = nyt

        await käsittele_viesti_xp(self.bot, message)

        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        tiedot = viestit_ja_ajat.pop(message.id, None)
        if tiedot:
            user_id, aika = tiedot
            nyt = datetime.now(timezone.utc)
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