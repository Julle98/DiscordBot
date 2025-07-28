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

    # MUTE
    @app_commands.command(name="mute", description="Aseta jäähy jäsenelle.")
    @app_commands.describe(jäsen="Jäsen, jolle asetetaan jäähy", kesto="Jäähyn kesto", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def mute(self, interaction: discord.Interaction, jäsen: discord.Member, kesto: str, syy: str = "Ei syytä annettu"):
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
            await jäsen.timeout(duration, reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} asetettu jäähylle ajaksi {kesto}. Syy: {syy}")
            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                await modlog_channel.send(
                    f"🔇 **Jäähy asetettu**\n👤 {jäsen.mention}\n⏱ {kesto}\n📝 {syy}\n👮 {interaction.user.mention}"
                )
        except Exception as e:
            await interaction.response.send_message(f"Virhe asetettaessa jäähyä: {e}", ephemeral=True)

    # UNMUTE
    @app_commands.command(name="unmute", description="Poista jäähy jäseneltä.")
    @app_commands.describe(jäsen="Jäsen, jolta poistetaan jäähy", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def unmute(self, interaction: discord.Interaction, jäsen: discord.Member, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/unmute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unmute_komento")
        if jäsen.timed_out_until is None:
            await interaction.response.send_message(f"{jäsen.mention} ei ole jäähyllä.", ephemeral=True)
            return
        try:
            await jäsen.timeout(None, reason=f"{syy} (Poisti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} on vapautettu jäähyltä. Syy: {syy}")
        except Exception as e:
            await interaction.response.send_message(f"Virhe poistettaessa jäähyä: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_mute(bot)
    await bot.add_cog(cog)