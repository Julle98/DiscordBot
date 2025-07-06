from discord.ext import commands
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

async def handle_message_edit(bot, before, after):
    print("✏️ Muokkaustapahtuma havaittu")

    if after.author.bot:
        print("⏭️ Ohitetaan botin viesti")
        return

    now = datetime.now(timezone.utc)
    message_age = now - before.created_at

    print(f"🕒 Viestin ikä: {message_age.total_seconds() / 3600:.2f} tuntia")

    if message_age > timedelta(hours=24):
        try:
            await after.delete()
            print("🗑️ Viesti poistettu")

            try:
                await after.author.send(
                    f"⚠️ Et voi muokata yli 24 tuntia vanhaa viestiä turvallisuussyistä. "
                    f"Viestisi poistettiin kanavalta #{after.channel.name}."
                )
                print("📩 Ilmoitus lähetetty käyttäjälle")
            except Exception as dm_error:
                print(f"⚠️ Ei voitu lähettää yksityisviestiä: {dm_error}")

            log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    f"🛡️ {after.author.mention} yritti muokata yli 24h vanhaa viestiä kanavassa {after.channel.mention}. Viesti poistettiin.\n"
                    f"**Alkuperäinen viesti:** {before.content}"
                )
                print("📜 Lokitus lähetetty")
            else:
                print("⚠️ Lokituskanavaa ei löytynyt")

        except Exception as e:
            print(f"❌ Virhe viestin poistossa tai ilmoituksessa: {e}")
    else:
        print("✅ Viesti oli alle 24h vanha – ei tehdä mitään")

class DeletionEdit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        print(f"✏️ Muokkaus: {before.content} → {after.content}")
        await handle_message_edit(self.bot, before, after)

async def setup(bot):
    await bot.add_cog(DeletionEdit(bot))