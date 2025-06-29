from discord import app_commands, Interaction
from discord.ext import commands
from bot.utils.ai.llm import generate_reply
from bot.utils.ai.web_search import simple_web_search
from bot.utils.ai.image_gen import generate_image
import discord
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.antinuke import cooldown

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @cooldown("tekoäly")
    @app_commands.command(name="tekoäly", description="Käytä tekoälyä hakemiseen, vastaamiseen tai kuvan generointiin")
    @app_commands.describe(toiminto="Valitse toiminto", kysymys="Kysymys tai kuvaus")
    @app_commands.choices(toiminto=[
        app_commands.Choice(name="Hae", value="hae"),
        app_commands.Choice(name="Kysy", value="kysy"),
        app_commands.Choice(name="Generoi", value="generoi")
    ])
    async def tekoaly(self, interaction: Interaction, toiminto: app_commands.Choice[str], kysymys: str):
        await interaction.response.defer()

        if toiminto.value == "hae":
            tulos = simple_web_search(kysymys)
            await interaction.followup.send(f"🔎 **Hakutulokset:**\n{tulos}")

        elif toiminto.value == "kysy":
            vastaus = generate_reply(kysymys)
            await interaction.followup.send(f"🧠 **Vastaus:**\n{vastaus}")

        elif toiminto.value == "generoi":
            generate_image(kysymys)
            await interaction.followup.send(content="🎨 **Kuva generoitu:**", file=discord.File("output.png"))

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot):
    cog = AI(bot)
    await bot.add_cog(cog)

