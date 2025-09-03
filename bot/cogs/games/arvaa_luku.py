import discord
from discord.ext import commands
from discord import app_commands
import random
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

MAX_TRIES = 3 

class ArvaaLuku(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # {user_id: (number, attempts)}

    @app_commands.command(name="peli_arvaa_luku", description="Arvaa bottin arpoma luku 1-20 (3 yritystä)")
    async def arvaa_luku(self, interaction: discord.Interaction, arvaus: int):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_arvaa_luku")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_arvaa_luku_komento")
        user_id = interaction.user.id

        if user_id not in self.games:
            numero = random.randint(1, 20)
            self.games[user_id] = (numero, 0)

        numero, yritykset = self.games[user_id]
        yritykset += 1

        if arvaus == numero:
            games_utils.add_win(user_id, "arvaa_luku")
            await interaction.response.send_message(
                f"✅ Oikein! Luku oli {numero}. Yrityksiä: {yritykset}\n"
                f"Sait +1 voiton ja +10 XP:tä!"
            )
            del self.games[user_id]

        elif yritykset >= MAX_TRIES:
            await interaction.response.send_message(f"❌ Hävisit! Oikea luku oli {numero}.")
            del self.games[user_id]

        elif arvaus < numero:
            await interaction.response.send_message(f"🔼 Liian pieni! Yritys {yritykset}/{MAX_TRIES}")
            self.games[user_id] = (numero, yritykset)

        else:
            await interaction.response.send_message(f"🔽 Liian suuri! Yritys {yritykset}/{MAX_TRIES}")
            self.games[user_id] = (numero, yritykset)

async def setup(bot):
    await bot.add_cog(ArvaaLuku(bot))
