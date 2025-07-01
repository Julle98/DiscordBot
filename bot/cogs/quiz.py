# bot/cogs/quiz.py
import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from bot.utils.bot_setup import bot

class Quiz(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.game_active = False
        self.current_question_data = None
        self.players = {}
        self.questions = []
        self.quiz_channel = None
        self.quiz_message = None

        self.ACTIVITY_APPLICATION_ID = os.getenv("DISCORD_ACTIVITY_APP_ID") 
        if not self.ACTIVITY_APPLICATION_ID:
            print("VAROITUS: DISCORD_ACTIVITY_APP_ID ei ole asetettu .env-tiedostossa. Activity-komento ei toimi.")
        else:
            self.ACTIVITY_APPLICATION_ID = int(self.ACTIVITY_APPLICATION_ID)


        self.questions = self.load_questions() 
        if not self.questions:
            print("Varoitus: Kysymyksiä ei ladattu Quiz-cogia varten! Tietovisa ei toimi ilman niitä.")

    def load_questions(self, filename="questions.json"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'data', filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Virhe: Kysymystiedostoa '{file_path}' ei löytynyt. Varmista, että se on kansiossa 'data'.")
            return []
        except json.JSONDecodeError:
            print(f"Virhe: Tiedoston '{file_path}' JSON-muoto on virheellinen.")
            return []

    @commands.command(name='aloita_tietovisa', help='Käynnistää tietovisan Discord Activity -muodossa äänikanavalla.')
    async def start_activity_quiz(self, ctx: commands.Context):
        if not self.ACTIVITY_APPLICATION_ID:
            await ctx.send("Botin konfiguraatiosta puuttuu Discord Activity Application ID. Pyydä omistajaa asettamaan `DISCORD_ACTIVITY_APP_ID` .env-tiedostoon.")
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Sinun täytyy olla äänikanavalla käynnistääksesi Activityn.")
            return

        try:
            invite_link = await ctx.author.voice.channel.create_activity_invite(
                self.ACTIVITY_APPLICATION_ID 
            )
            await ctx.send(f"Klikkaa tästä käynnistääksesi tietovisa Activityn äänikanavalla **{ctx.author.voice.channel.name}**: {invite_link}")
        except discord.Forbidden:
            await ctx.send("Minulla ei ole lupaa luoda kutsuja tälle äänikanavalle. Tarkista botin oikeudet.")
        except discord.HTTPException as e:
            await ctx.send(f"Virhe Activityn käynnistyksessä: {e} (Varmista, että Application ID on oikein ja Activity on määritelty Developer Portalissa).")

async def setup(bot: commands.Bot):
    await bot.add_cog(Quiz(bot))