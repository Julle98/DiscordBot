import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.error_handler import CommandErrorHandler
from discord import app_commands, Interaction
import aiohttp

class CurrencyConverter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="valuutta", description="Muunna valuutta määrästä toiseen valuuttaan.")
    @app_commands.describe(
        määrä="Muunnettava summa",
        lähtövaluutta="Valuutta, josta muunnetaan (esim. USD)",
        kohdevaluutta="Valuutta, johon muunnetaan (esim. EUR)",
        näytä_tuetut="Näytä lista tuetuista valuutoista"
    )
    async def valuuttamuunnos(
        self,
        interaction: discord.Interaction,
        määrä: float,
        lähtövaluutta: str,
        kohdevaluutta: str,
        näytä_tuetut: bool = False
    ):
        await interaction.response.defer(ephemeral=True)

        if näytä_tuetut:
            embed = discord.Embed(
                title="💱 Tuetut valuutat",
                description="Tässä on yleisimmät tuetut valuutat exchangerate.host API:ssa:",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="Valuuttakoodit",
                value="USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, SEK, NOK",
                inline=False
            )
            embed.set_footer(text="Täydellinen lista: exchangerate.host/currencies")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        url = f"https://api.exchangerate.host/convert?from={lähtövaluutta.upper()}&to={kohdevaluutta.upper()}&amount={määrä}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await interaction.followup.send("⚠️ Valuuttatietojen hakeminen epäonnistui.", ephemeral=True)
                    return

                data = await response.json()
                tulos = data.get("result")

                if tulos is None:
                    await interaction.followup.send("❌ Virhe valuuttamuunnoksessa. Tarkista valuuttakoodit.", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="💱 Valuuttamuunnos",
                    description=f"{määrä} {lähtövaluutta.upper()} = {tulos:.2f} {kohdevaluutta.upper()}",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Tiedot: exchangerate.host")
                await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot):
    await bot.add_cog(CurrencyConverter(bot))