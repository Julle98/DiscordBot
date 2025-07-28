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

class Moderation_warning(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Anna varoitus käyttäjälle.")
    @app_commands.describe(member="Käyttäjä", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu"):
            await kirjaa_komento_lokiin(self.bot, interaction, "/warn")
            await kirjaa_ga_event(self.bot, interaction.user.id, "warn_komento")
            try:
                await member.send(f"Olet saanut varoituksen: {syy}")
            except discord.Forbidden:
                await interaction.followup.send("YV epäonnistui.", ephemeral=True)
            await interaction.response.send_message(f"{member.mention} sai varoituksen.")
            modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog:
                await modlog.send(f"[VAROITUS] {member.mention} | ID: {member.id} | Syy: {syy} | Antaja: {interaction.user.mention}")

    # UNWARN
    @app_commands.command(name="unwarn", description="Poista käyttäjän varoitus.")
    @app_commands.describe(member="Käyttäjä", kaikki="Poista kaikki varoitukset.")
    @app_commands.checks.has_role("Mestari")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, kaikki: bool = False):
            await kirjaa_komento_lokiin(self.bot, interaction, "/unwarn")
            await kirjaa_ga_event(self.bot, interaction.user.id, "unwarn_komento")
            modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if not modlog:
                await interaction.response.send_message("Moderaatiokanavaa ei löytynyt.", ephemeral=True)
                return
            poistettu = 0
            async for msg in modlog.history(limit=1000):
                if msg.author == self.bot.user and f"ID: {member.id}" in msg.content:
                    await msg.delete()
                    poistettu += 1
                    if not kaikki:
                        break
            await interaction.response.send_message(
                f"{member.mention} varoituksista poistettiin {poistettu} {'kaikki' if kaikki else 'yksi'}."
            )

    # VAROITUKSET
    @app_commands.command(name="varoitukset", description="Näytä käyttäjän varoitukset.")
    @app_commands.describe(member="Käyttäjä")
    @app_commands.checks.has_role("Mestari")
    async def varoitukset(self, interaction: discord.Interaction, member: discord.Member):
            await kirjaa_komento_lokiin(self.bot, interaction, "/varoitukset")
            await kirjaa_ga_event(self.bot, interaction.user.id, "varoitukset_komento")
            modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if not modlog:
                await interaction.response.send_message("Moderaatiokanavaa ei löytynyt.", ephemeral=True)
                return
            lista = []
            async for msg in modlog.history(limit=1000):
                if f"ID: {member.id}" in msg.content:
                    lista.append(msg.content)
            if not lista:
                await interaction.response.send_message("Ei varoituksia.", ephemeral=True)
                return
            vastaus = "\n".join([f"{i+1}. {v.split(' | Syy: ')[-1].split(' |')[0]}" for i, v in enumerate(lista)])
            await interaction.response.send_message(f"{member.mention} on saanut {len(lista)} varoitusta:\n{vastaus}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_warning(bot)
    await bot.add_cog(cog)