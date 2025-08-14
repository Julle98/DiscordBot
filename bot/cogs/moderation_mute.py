import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from dotenv import load_dotenv
import os
from bot.utils.error_handler import CommandErrorHandler

load_dotenv()
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

class Moderation_mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mute", description="Aseta jäähy jäsenelle.")
    @app_commands.describe(
        jäsen="Jäsen, jolle asetetaan jäähy",
        kesto="Jäähyn kesto (esim. 10s, 5m, 1h)",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    async def mute(self, interaction: discord.Interaction, jäsen: discord.Member, kesto: str, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/mute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "mute_komento")
        if jäsen == interaction.user:
            await interaction.response.send_message("Et voi asettaa itseäsi jäähylle.", ephemeral=True)
            return
        try:
            seconds = int(kesto[:-1])
            unit = kesto[-1]
            if unit == "s":
                duration = timedelta(seconds=seconds)
            elif unit == "m":
                duration = timedelta(minutes=seconds)
            elif unit == "h":
                duration = timedelta(hours=seconds)
            else:
                await interaction.response.send_message("Virheellinen aikaformaatti. Käytä esim. 10s, 5m, 1h", ephemeral=True)
                return

            poistetut = []
            if viesti_id:
                ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
                for vid in ids:
                    try:
                        msg = await interaction.channel.fetch_message(int(vid))
                        if msg.author.id == jäsen.id:
                            await msg.delete()
                            poistetut.append(vid)
                    except:
                        continue

            try:
                await jäsen.send(f"Sinut on asetettu jäähylle palvelimella {interaction.guild.name} ajaksi {kesto}.\nSyy: {syy}")
            except discord.Forbidden:
                pass

            await jäsen.timeout(duration, reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} asetettu jäähylle ajaksi {kesto}. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"🔇 **Jäähy asetettu**\n👤 {jäsen.mention}\n⏱ {kesto}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n🗑 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except Exception as e:
            await interaction.response.send_message(f"Virhe asetettaessa jäähyä: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Poista jäähy jäseneltä.")
    @app_commands.describe(
        jäsen="Jäsen, jolta poistetaan jäähy",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    async def unmute(self, interaction: discord.Interaction, jäsen: discord.Member, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/unmute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unmute_komento")
        if jäsen.timed_out_until is None:
            await interaction.response.send_message(f"{jäsen.mention} ei ole jäähyllä.", ephemeral=True)
            return
        try:
            poistetut = []
            if viesti_id:
                ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
                for vid in ids:
                    try:
                        msg = await interaction.channel.fetch_message(int(vid))
                        if msg.author.id == jäsen.id:
                            await msg.delete()
                            poistetut.append(vid)
                    except:
                        continue

            await jäsen.timeout(None, reason=f"{syy} (Poisti: {interaction.user})")

            try:
                await jäsen.send(f"Jäähysi on poistettu palvelimella {interaction.guild.name}.\nSyy: {syy}")
            except discord.Forbidden:
                pass

            await interaction.response.send_message(f"{jäsen.mention} on vapautettu jäähyltä. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"✅ **Jäähy poistettu**\n👤 {jäsen.mention}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n🗑 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except Exception as e:
            await interaction.response.send_message(f"Virhe poistettaessa jäähyä: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_mute(bot)
    await bot.add_cog(cog)