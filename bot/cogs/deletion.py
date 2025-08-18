from discord.ext import commands
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

async def handle_message_edit(bot, before, after):
    now = datetime.now(timezone.utc)

    if after.author.bot:
        return

    if before.content == after.content:
        return

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

            log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    f"🛡️ {after.author.mention} yritti muokata yli 24h vanhaa viestiä kanavassa {after.channel.mention}. Viesti poistettiin.\n"
                    f"**Alkuperäinen viesti:** {before.content}"
                )
            else:
                print("⚠️ Lokituskanavaa ei löytynyt")

        except Exception as e:
            print(f"❌ Virhe viestin poistossa tai ilmoituksessa: {type(e).__name__}: {e}")

class DeletionEdit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await handle_message_edit(self.bot, before, after)
        
async def setup(bot):
    await bot.add_cog(DeletionEdit(bot))