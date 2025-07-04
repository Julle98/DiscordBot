import discord
from discord.ext import commands
from discord import app_commands, Interaction
import asyncio
from bot.utils.ai.llm import generate_reply
from bot.utils.ai.web_search import simple_web_search
from bot.utils.ai.image_gen import generate_image
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
import logging
from duckduckgo_search import DDGS

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tekoäly",
        description="Käytä tekoälyä hakemiseen, vastaamiseen tai kuvan generointiin"
    )
    @app_commands.describe(
        toiminto="Valitse toiminto",
        kysymys="Kysymys tai kuvaus"
    )
    @app_commands.choices(toiminto=[
        app_commands.Choice(name="Hae", value="hae"),
        app_commands.Choice(name="Kysy", value="kysy"),
        app_commands.Choice(name="Generoi", value="generoi")
    ])
    async def tekoaly(self, interaction: Interaction, toiminto: app_commands.Choice[str], kysymys: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/tekoäly")
        await kirjaa_ga_event(self.bot, interaction.user.id, "teköäly_komento")

        await interaction.response.defer(thinking=True)

        try:
            if toiminto.value == "hae":
                tulos = await asyncio.to_thread(simple_web_search, kysymys)
                await interaction.followup.send(f"🔎 **Hakutulokset:**\n{tulos}")

            elif toiminto.value == "kysy":
                vastaus = await asyncio.to_thread(generate_reply, kysymys)
                await interaction.followup.send(f"🧠 **Vastaus:**\n{vastaus}")

            elif toiminto.value == "generoi":
                await asyncio.to_thread(generate_image, kysymys)
                await interaction.followup.send(
                    content="🎨 **Kuva generoitu:**",
                    file=discord.File("output.png")
                )

        except Exception as e:
            await interaction.followup.send(f"🚫 Tapahtui virhe: `{e}`")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot):
    await bot.add_cog(AI(bot))
