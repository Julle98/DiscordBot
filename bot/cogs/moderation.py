import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin, autocomplete_bannatut_käyttäjät
from bot.utils.error_handler import CommandErrorHandler

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_monitors(self):
        from utils.moderation_tasks import (
            tarkista_ostojen_kuukausi,
            tarkista_paivat
        )
        if not tarkista_ostojen_kuukausi.is_running():
            tarkista_ostojen_kuukausi.start()
        if not tarkista_paivat.is_running():
            tarkista_paivat.start()

    # PING
    @app_commands.command(name="ping", description="Näytä botin viive.")
    async def ping(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ping")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ping_komento")
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Botin viive on {latency} ms.")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)