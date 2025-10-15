import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from discord import app_commands, Interaction
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import aiohttp

class CurrencyConverter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="valuutta", description="Muunna valuutta määrästä toiseen valuuttaan tai näytä tuetut valuutat.")
    @app_commands.describe(
        määrä="Muunnettava summa",
        lähtövaluutta="Valuutta, josta muunnetaan (esim. USD)",
        kohdevaluutta="Valuutta, johon muunnetaan (esim. EUR)",
        näytä_tuetut="Näytä lista tuetuista valuutoista (Ei suorita muunnosta)"
    )
    async def valuutta(
        self,
        interaction: discord.Interaction,
        määrä: float,
        lähtövaluutta: str,
        kohdevaluutta: str,
        näytä_tuetut: bool = False
    ):
        await interaction.response.defer(ephemeral=True)

        asyncio.create_task(kirjaa_komento_lokiin(self.bot, interaction, "/valuutta"))
        asyncio.create_task(kirjaa_ga_event(self.bot, interaction.user.id, "valuutta_komento"))

        if näytä_tuetut:
            embed = discord.Embed(
                title="💱 Tuetut valuutat",
                description="Tässä on yleisimmät tuetut valuutat ExchangeRate-API:ssa:",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="Valuuttakoodit",
                value="USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, SEK, NOK",
                inline=False
            )
            embed.set_footer(text="Täydellinen lista: open.er-api.com/v6/currencies")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if määrä <= 0:
            await interaction.followup.send("❌ Määrän täytyy olla suurempi kuin 0.", ephemeral=True)
            return

        url = f"https://open.er-api.com/v6/latest/{lähtövaluutta.upper()}"

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await interaction.followup.send("⚠️ Valuuttatietojen hakeminen epäonnistui.", ephemeral=True)
                    return

                data = await response.json()
                rates = data.get("rates")
                updated_raw = data.get("time_last_update_utc")

                if not rates or kohdevaluutta.upper() not in rates:
                    await interaction.followup.send("❌ Kohdevaluuttaa ei löytynyt. Tarkista valuuttakoodit.", ephemeral=True)
                    return

                kurssi = rates[kohdevaluutta.upper()]
                tulos = määrä * kurssi

                try:
                    utc_time = datetime.strptime(updated_raw, "%a, %d %b %Y %H:%M:%S %z")
                    suomi_time = utc_time.astimezone(ZoneInfo("Europe/Helsinki"))
                    updated = suomi_time.strftime("%d.%m.%Y %H:%M (Suomen aikaa)")
                except Exception:
                    updated = updated_raw or "tuntematon"

                embed = discord.Embed(
                    title="💱 Valuuttamuunnos",
                    description=f"{määrä} {lähtövaluutta.upper()} = {tulos:.2f} {kohdevaluutta.upper()}",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Tiedot: open.er-api.com • Päivitetty: {updated}")
                await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot):
    await bot.add_cog(CurrencyConverter(bot))