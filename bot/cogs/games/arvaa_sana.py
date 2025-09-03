import discord
from discord import app_commands
from discord.ext import commands
import random
import os
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils import games_utils
from dotenv import load_dotenv

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
        self.games = {}  # {user_id: (word, guesses)}

    @app_commands.command(name="peli_arvaa_sana", description="Arvaa sana kirjain kerrallaan")
    async def arvaa_sana(self, interaction: discord.Interaction, kirjain: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_arvaa_sana")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_arvaa_sana_komento")
        user_id = interaction.user.id

        if user_id not in self.games:
            sana = random.choice(SANAT)
            self.games[user_id] = (sana, set())

        sana, guesses = self.games[user_id]
        guesses.add(kirjain.lower())

        näkyvä = "".join(c if c in guesses else "_" for c in sana)

        vihje = VIHJEET.get(sana, "Ei vihjettä saatavilla")

        if "_" not in näkyvä:
            games_utils.add_win(user_id, "arvaa_sana")
            await interaction.response.send_message(
                f"✅ Oikein! Sana oli **{sana}**\n"
                f"Sait +1 voiton ja +10 XP:tä!"
            )
            del self.games[user_id]
        else:
            await interaction.response.send_message(f"Sana: {näkyvä}\n💡 Vihje: {vihje}")

async def setup(bot):
    await bot.add_cog(ArvaaSana(bot))
