import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from io import BytesIO

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

ROOLI_POIKKEUKSET = ["Moderaattori", "Admin", "Mestari"]

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.id == self.slowmode_channel_id:
            slowmode_cog = self.bot.get_cog("SlowmodeTracker")
            if slowmode_cog:
                try:
                    slowmode_cog.log_message(message)
                except Exception as e:
                    print(f"[XPSystem] SlowmodeTracker log_message virhe: {e}")

        if isinstance(message.channel, discord.DMChannel):
            await käsittele_dm_viesti(self.bot, message)
            return

        maininta = self.bot.user.mentioned_in(message)
        reply_to_bot = message.reference and isinstance(message.reference.resolved, discord.Message) and message.reference.resolved.author == self.bot.user

        if maininta or reply_to_bot:
            content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            if content:
                response = await self.get_response(content)
                await message.reply(response, mention_author=False)
            else:
                await message.reply("Hei! Kysy minulta jotain tai kerro, mitä haluat tietää 🙂", mention_author=False)

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
        komento_ajastukset[user_id][komento_nimi] = nyt

        member = message.guild.get_member(user_id)
        if not member:
            return

        if any(r.name in ROOLI_POIKKEUKSET for r in member.roles):
            settings = get_user_settings(user_id)

            if not settings["xp_epaaktiivisuus"]:
                return

            await käsittele_xp_bonus(message, user_id, nyt)

            settings = get_user_settings(user_id)

            if not settings["xp_viestit"]:
                return

            await käsittele_viesti_xp(self.bot, message)
            await self.bot.process_commands(message)
            return

        await käsittele_xp_bonus(message, user_id, nyt)

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