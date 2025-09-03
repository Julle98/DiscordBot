import discord
from discord.ext import commands
from discord import app_commands
import random
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class ArvaaLuku(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_arvaa_luku", description="Arvaa bottin arpoma luku 1-20")
    async def arvaa_luku(self, interaction: discord.Interaction, arvaus: int):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_arvaa_luku")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_arvaa_luku_komento")
        numero = random.randint(1, 20)

        if arvaus == numero:
            games_utils.add_win(interaction.user.id, "arvaa_luku")
            await interaction.response.send_message(
                f"✅ Oikein! Luku oli {numero}. Sait +1 voiton ja +10 XP:tä!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Väärin! Oikea luku oli {numero}.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ArvaaLuku(bot))