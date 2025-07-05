import discord
from discord.ext import commands
from discord import app_commands, Interaction
import asyncio

from bot.utils.ai.tekoalykieli import tulkitse_tekoalykieli
from bot.utils.ai.tekoaly_hae import suorita_haku
from bot.utils.ai.tekoaly_kysy import suorita_kysymys
from bot.utils.ai.tekoaly_generoi import suorita_kuvagenerointi
from bot.utils.ai.tekoaly_tiivista import suorita_tiivistys
from bot.utils.ai.tekoaly_kaanna import suorita_kaannos

from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tekoäly",
        description="Anna komento TeKo-kielellä (HAE, KYSY, GENEROI, TIIVISTÄ, KÄÄNNÄ)"
    )
    @app_commands.describe(
        kysymys="Kirjoita komento ja kysymys, esim. 'KYSY mikä on tekoäly?'"
    )
    async def tekoaly(self, interaction: Interaction, kysymys: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/tekoäly")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tekoäly_komento")

        await interaction.response.defer(thinking=True)

        try:
            komento, argumentti = tulkitse_tekoalykieli(kysymys)

            if komento == "HAE":
                tulos = await suorita_haku(argumentti)
                await interaction.followup.send(tulos)

            elif komento == "KYSY":
                vastaus = await suorita_kysymys(argumentti)
                await interaction.followup.send(f"🧠 **Vastaus:**\n{vastaus}")

            elif komento == "GENEROI":
                kuva = await suorita_kuvagenerointi(argumentti)
                await interaction.followup.send(content="🎨 **Kuva generoitu:**", file=kuva)

            elif komento == "TIIVISTÄ":
                tiivistelma = await suorita_tiivistys(argumentti)
                await interaction.followup.send(f"✂️ **Tiivistelmä:**\n{tiivistelma}")

            elif komento == "KÄÄNNÄ":
                kaannos = await suorita_kaannos(argumentti)
                await interaction.followup.send(f"🌍 **Käännös:**\n{kaannos}")

            else:
                await interaction.followup.send("🤖 Komentoa ei tunnistettu.")

        except Exception as e:
            await interaction.followup.send(f"🚫 Tapahtui virhe: `{e}`")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot):
    await bot.add_cog(AI(bot))