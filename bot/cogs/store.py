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

load_dotenv()

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kauppa", description="Näytä kaupan tuotteet tai osta tuote")
    @app_commands.describe(
        tuote="Tuotteen nimi ostamista varten, jos tarjoustuote: ``(tarjous!)`` mukaan (valinnainen)",
        kuponki="Alennuskoodi (valinnainen)",
        ohje="Näytä kaupan ohjeet, näyttää vain ohjeet ei kaupanvalikoimaa (valinnainen)"
    )
    @app_commands.checks.has_role("24G")
    async def kauppa(self, interaction: discord.Interaction, tuote: Optional[str] = None, kuponki: Optional[str] = None, ohje: Optional[bool] = False):
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/kauppa")
            await kirjaa_ga_event(self.bot, interaction.user.id, "kauppa_komento")

            if ohje:
                embed = discord.Embed(
                    title="📘 Sannamaija Shopin ohjeet",
                    description="Näin kaupan ostaminen toimii ja mitä kannattaa huomioida:",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Ostaminen",
                    value="Käytä `/kauppa [tuotteen nimi]` ostaaksesi tuotteen. Tuotteen nimi identtinen kuten listassa näkyy elikkä sulkeet mukaan tarjous tuotteissa.",
                    inline=False
                )
                embed.add_field(
                    name="Kuponkien käyttö",
                    value="Voit lisätä alennuskoodin komennon loppuun: `/kauppa [tuotteen nimi] [kuponki]`. Erilaisia kupongeista kerrotaan info viesteissä tai erikseen jaetuissa.",
                    inline=False
                )
                embed.add_field(
                    name="Lisähuomiot",
                    value="• XP ei vähene ostoksia tekemällä.\n• Voit ostaa saman tuotteen kerran kuukaudessa, ja seuraavana kuukautena uudelleen.\n• Tarjoustuotteet voivat vaihtua erikoisjaksojen mukaan.",
                    inline=False
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

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
