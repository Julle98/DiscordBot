import discord, asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict
import random
from io import BytesIO
import os

from bot.utils.bot_setup import bot
from bot.utils.xp_utils import (
    käsittele_viesti_xp,
    käsittele_dm_viesti,
)
from bot.utils.tiedot_utils import pending_file_sends
from utils.xp_bonus import käsittele_xp_bonus
from bot.utils.settings_utils import get_user_settings

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}
viime_viestit = {}    # {user_id: datetime}

varoituslaskurit = {}

JÄÄHY_KESTO = 15 * 60

MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID"))

ROOLI_POIKKEUKSET = ["Moderaattori", "Admin", "Mestari"]

varoitusviestit = [
    "🐌 Hei {mention}, viestit tulevat turhan nopeasti. Hidasta hieman, niin kaikki toimii sulavasti.",
    "📢 {mention}, tämä on toinen huomautus. Etanatila on olemassa syystä – anna muillekin tilaa hengittää.",
    "⚠️ {mention}, viimeinen varoitus! Jos viestittely jatkuu näin, joudun asettamaan sinut jäähylle."
]

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            await käsittele_dm_viesti(self.bot, message)
            return

        if self.bot.user.mentioned_in(message):
            content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            if content:
                response = await self.get_response(content)
                await message.reply(f"{response}")
            else:
                await message.reply("Hei! Kysy minulta jotain tai kerro, mitä haluat tietää 🙂")
            await self.bot.process_commands(message)
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
        if not member:
            return

        if any(r.name in ROOLI_POIKKEUKSET for r in member.roles):
            settings = get_user_settings(user_id)

            if not settings["xp_epaaktiivisuus"]:
                return

            await käsittele_xp_bonus(message, user_id, nyt)
            komento_ajastukset[user_id][komento_nimi] = nyt

            settings = get_user_settings(user_id)

            if not settings["xp_viestit"]:
                return

            await käsittele_viesti_xp(self.bot, message)
            await self.bot.process_commands(message)
            return

        raja = timedelta(seconds=2)
        if viimeinen and nyt - viimeinen < raja:
            await message.delete()

            laskuri = varoituslaskurit.get(user_id, 0)

            if laskuri < len(varoitusviestit):
                msg = await message.channel.send(varoitusviestit[laskuri].format(mention=message.author.mention))
                await asyncio.sleep(5)
                await msg.delete()
                varoituslaskurit[user_id] = laskuri + 1
            else:
                try:
                    syy = "Etanatilan väärinkäyttö"
                    await member.timeout(datetime.utcnow() + timedelta(seconds=JÄÄHY_KESTO), reason=syy)

                    await member.send(
                        f"🔇 Sinut on asetettu jäähylle palvelimella {message.guild.name} ajaksi 15 minuuttia.\nSyy: {syy}"
                    )

                    modlog_channel = message.guild.get_channel(MODLOG_CHANNEL_ID)
                    if modlog_channel:
                        await modlog_channel.send(
                            f"🔇 Jäähy asetettu (automaattinen)\n"
                            f"👤 Käyttäjä: {member.mention}\n"
                            f"⏱ Kesto: 15 minuuttia\n"
                            f"📝 Syy: {syy}\n"
                            f"👮 Asetti: Sannamaija"
                        )
                except Exception as e:
                    print(f"Jäähyn asettaminen epäonnistui: {e}")

                varoituslaskurit[user_id] = 0
            return

        await käsittele_xp_bonus(message, user_id, nyt)
        komento_ajastukset[user_id][komento_nimi] = nyt
        varoituslaskurit[user_id] = 0

        settings = get_user_settings(user_id)

        if not settings["xp_viestit"]:
            return

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

async def setup(bot):
    await bot.add_cog(XPSystem(bot))