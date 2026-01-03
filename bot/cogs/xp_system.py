import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from io import BytesIO
import os
from typing import Optional
import re

from bot.utils.bot_setup import bot
from bot.utils.xp_utils import (
    käsittele_viesti_xp,
    käsittele_dm_viesti,
)
from bot.utils.tiedot_utils import pending_file_sends
from utils.xp_bonus import käsittele_xp_bonus
from bot.utils.settings_utils import get_user_settings
from bot.cogs.ai import AI
from bot.cogs.slowmode import SlowmodeTracker

ROOLI_POIKKEUKSET = ["Moderaattori", "Admin", "Mestari"]

EMOJI_REGEX = re.compile(
    r'(<a?:\w+:\d+>)|'  
    r'([\U0001F1E6-\U0001F1FF])|'  
    r'([\U0001F300-\U0001F5FF])|'  
    r'([\U0001F600-\U0001F64F])|' 
    r'([\U0001F680-\U0001F6FF])|' 
    r'([\U0001F700-\U0001F77F])|' 
    r'([\U0001F780-\U0001F7FF])|' 
    r'([\U0001F800-\U0001F8FF])|' 
    r'([\U0001F900-\U0001F9FF])|'  
    r'([\U0001FA70-\U0001FAFF])'  
)

IGNORED_EMOJI_ROLES = {
    1339853855315197972,  
    1368228763770294375,  
    1339846508199022613,  
}

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slowmode_channel_id = int(os.getenv("SLOWMODE_CHANNEL_ID"))
        self.ai = AI(bot)
        self.emoji_default_limit = 3  
        self.emoji_channel_limits = {
            1339859287739994112: 1,  
            1395025181310849084: 1,
            1339846062281588777: 2,
            1339856017277714474: 2 
        }

    def _extract_emojis(self, text: str):
        return [m.group(0) for m in EMOJI_REGEX.finditer(text)]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is not None:
            limit = self.emoji_channel_limits.get(
                message.channel.id,
                self.emoji_default_limit
            )

            emojis = self._extract_emojis(message.content)
            if emojis:
                counts = {}
                for e in emojis:
                    counts[e] = counts.get(e, 0) + 1

                violated = [e for e, c in counts.items() if c > limit]
                if violated:
                    if any(r.id in IGNORED_EMOJI_ROLES for r in message.author.roles):
                        return

                    try:
                        emote_list = ", ".join(set(violated))
                        dm_text = (
                            f"Hei {message.author.mention}!\n\n"
                            f"Viestissäsi kanavalla **#{message.channel.name}** "
                            f"oli liian monta samaa emojia.\n"
                            f"Tässä kanavassa sallitaan enintään **{limit}** kpl "
                            f"samaa emojia per viesti.\n\n"
                            f"Näissä emojeissa raja ylittyi: {emote_list}\n\n"
                            f"Viesti jäi kanavaan, mutta koita jatkossa käyttää vähemmän emojeita 🙂"
                        )
                        await message.author.send(dm_text)
                    except discord.Forbidden:
                        pass

        maininta = self.bot.user.mentioned_in(message)
        reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg.author == self.bot.user:
                    reply_to_bot = True
            except discord.NotFound:
                pass

        if maininta or reply_to_bot:
            content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()

            reaction = await self.ai.get_reaction_response(message)
            if reaction:
                await message.reply(reaction, mention_author=False)
                return

            response = await self.ai.get_response(content) if content else "Hei! Kysy minulta jotain tai kerro, mitä haluat tietää 🙂"
            await message.reply(response, mention_author=False)
            return

        if isinstance(message.channel, discord.DMChannel):
            await käsittele_dm_viesti(self.bot, message)
            return

        if message.channel.id == self.slowmode_channel_id:
            slowmode_cog: Optional[SlowmodeTracker] = self.bot.get_cog("SlowmodeTracker")
            if slowmode_cog:
                try:
                    slowmode_cog.log_message(message)
                except Exception as e:
                    print(f"[XPSystem] SlowmodeTracker log_message virhe: {e}")

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

async def setup(bot):
    await bot.add_cog(XPSystem(bot))
    await bot.add_cog(AI(bot))
    await bot.add_cog(SlowmodeTracker(bot))