from discord.ext import commands
import discord
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
MESSAGES_LOG_CHANNEL_ID = int(os.getenv("MESSAGES_LOG", 0))

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}

async def handle_message_edit(bot, before: discord.Message, after: discord.Message):
    now = datetime.now(timezone.utc)

    if after.author.bot:
        return

    if before.content == after.content:
        return

    log_channel = bot.get_channel(MESSAGES_LOG_CHANNEL_ID)

    if log_channel:
        await log_channel.send(
            f"✏️ **Viestin muokkaus**\n"
            f"**Käyttäjä:** {after.author.mention}\n"
            f"**Kanava:** {after.channel.mention}\n"
            f"**Alkuperäinen:** {before.content or '*ei sisältöä*'}\n"
            f"**Uusi:** {after.content or '*ei sisältöä*'}"
        )

    message_age = now - before.created_at

    if message_age > timedelta(hours=24):
        try:
            await after.delete()

            try:
                await after.author.send(
                    f"⚠️ Et voi muokata yli 24 tuntia vanhaa viestiä turvallisuussyistä. "
                    f"Viestisi poistettiin kanavalta #{after.channel.name}."
                )
            except Exception as dm_error:
                print(f"⚠️ Ei voitu lähettää yksityisviestiä: {dm_error}")

            if log_channel:
                await log_channel.send(
                    f"🛡️ **Yli 24h vanhan viestin muokkaus – viesti poistettu**\n"
                    f"**Käyttäjä:** {after.author.mention}\n"
                    f"**Kanava:** {after.channel.mention}\n"
                    f"**Alkuperäinen viesti:** {before.content or '*ei sisältöä*'}"
                )
            else:
                print("⚠️ Lokituskanavaa ei löytynyt")

        except Exception as e:
            print(f"❌ Virhe viestin poistossa tai ilmoituksessa: {type(e).__name__}: {e}")


class DeletionEdit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        tiedot = viestit_ja_ajat.pop(message.id, None)
        if tiedot:
            user_id, aika = tiedot
            nyt = datetime.now(timezone.utc)
            if nyt - aika < timedelta(seconds=10):
                komento_ajastukset[user_id].pop("xp_viesti", None)

        if message.author.bot:
            return

        log_channel = self.bot.get_channel(MESSAGES_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"🗑️ **Viestin poisto**\n"
                f"**Käyttäjä:** {message.author.mention}\n"
                f"**Kanava:** {message.channel.mention}\n"
                f"**Sisältö:** {message.content or '*ei sisältöä*'}"
            )
        else:
            print("⚠️ Lokituskanavaa ei löytynyt")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await handle_message_edit(self.bot, before, after)

async def setup(bot):
    await bot.add_cog(DeletionEdit(bot))