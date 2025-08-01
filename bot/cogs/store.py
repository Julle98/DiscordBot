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
    osta_command,
    hae_tarjous_vain
)
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from bot.utils.error_handler import CommandErrorHandler
from typing import Optional
from bot.utils.store_utils import tarkista_kuponki

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

    @app_commands.command(name="kauppa", description="Näytä kaupan tuotteet tai osta tuote")
    @app_commands.describe(
        tuote="Tuotteen nimi ostamista varten, jos tarjoustuote: ``(tarjous!)`` mukaan (valinnainen)",
        kuponki="Alennuskoodi (valinnainen)"
    )
    @app_commands.checks.has_role("24G")
    async def kauppa(self, interaction: discord.Interaction, tuote: Optional[str] = None, kuponki: Optional[str] = None):
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/kauppa")
            await kirjaa_ga_event(self.bot, interaction.user.id, "kauppa_komento")

            tarjoukset = await asyncio.to_thread(hae_tarjous_vain)

            if tuote is None:
                embed = nayta_kauppa_embed(interaction, tarjoukset)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                alennus = 0
                if kuponki:
                    user_id = str(interaction.user.id)
                    alennus = tarkista_kuponki(kuponki, tuote, user_id, interaction)
                    if alennus == 0:
                        await interaction.response.send_message("❌ Kuponki ei kelpaa tälle tuotteelle, vanhentunut tai käyttöraja täynnä. Osto peruutettu.", ephemeral=True)
                        return

                await osta_command(self.bot, interaction, tuote, tarjoukset, alennus=alennus)

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
