import discord
from discord.ext import commands
from discord import app_commands
import random
import os
from dotenv import load_dotenv
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

load_dotenv()
SANAT_ENV = os.getenv("ARVAA_SANAT")
SANAT = []
VIHJEET = {}

for pair in SANAT_ENV.split(","):
    if ":" in pair:
        word, hint = pair.split(":")
        SANAT.append(word.lower())
        VIHJEET[word.lower()] = hint

class ArvaaSana(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_arvaa_sana", description="Arvaa mikä sana on kyseessä")
    async def peli_arvaa_sana(self, interaction: discord.Interaction, arvaus1: str, arvaus2: str=None, arvaus3: str=None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_arvaa_sana")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_arvaa_sana_komento")
        sana = random.choice(SANAT)
        vihje = VIHJEET.get(sana, "Ei vihjettä")

        guesses = [g.lower() for g in [arvaus1, arvaus2, arvaus3] if g]

        if sana in guesses:
            games_utils.add_win(interaction.user.id, "arvaa_sana")
            await interaction.response.send_message(
                f"✅ Oikein! Sana oli **{sana}**.\nSait +1 voiton ja +10 XP:tä!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Väärin! Sana oli **{sana}**.\n💡 Vihje oli: {vihje}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ArvaaSana(bot))
