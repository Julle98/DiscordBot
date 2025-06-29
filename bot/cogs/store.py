import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.store_utils import (
    hae_tai_paivita_tarjous,
    nayta_kauppa_embed,
    osta_command
)
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from bot.utils.error_handler import CommandErrorHandler
from bot.utils import store_utils as su

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}

def cooldown(komento_nimi: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            nyt = datetime.now()
            user_id = interaction.user.id
            viimeinen = komento_ajastukset[user_id].get(komento_nimi)

            nopea_roolit = ["Mestari", "Admin", "Moderaattori"]
            nopea = any(r.name in nopea_roolit for r in interaction.user.roles)
            raja = timedelta(seconds=5 if nopea else 10)

            if viimeinen and nyt - viimeinen < raja:
                erotus = int((raja - (nyt - viimeinen)).total_seconds())
                await interaction.response.send_message(
                    f"Odota {erotus} sekuntia ennen kuin käytät komentoa uudelleen.",
                    ephemeral=True
                )
                return

            komento_ajastukset[user_id][komento_nimi] = nyt
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

load_dotenv()

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cooldown("kauppa")
    @app_commands.command(name="kauppa", description="Näytä kaupan tuotteet tai osta tuote")
    @app_commands.describe(tuote="Tuotteen nimi ostamista varten (valinnainen)")
    @app_commands.checks.has_role("24G")
    @cooldown("kauppa")
    async def kauppa(self, interaction: discord.Interaction, tuote: str = None):
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/kauppa")
            kirjaa_ga_event(interaction.user.id, "kauppa_komento")

            tarjoukset = hae_tai_paivita_tarjous()

            if tuote is None:
                embed = nayta_kauppa_embed(interaction, tarjoukset)
                await interaction.response.send_message(embed=embed)
            else:
                await osta_command(self.bot, interaction, tuote, tarjoukset)

        except Exception as e:
            try:
                await interaction.response.send_message(f"Tapahtui virhe: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"Tapahtui virhe: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Store(bot)
    await bot.add_cog(cog)
