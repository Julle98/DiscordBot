import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import re
from dotenv import load_dotenv
from collections import Counter
from google.oauth2 import service_account
from googleapiclient.discovery import build
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.antinuke import cooldown

from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
analytics = build('analyticsdata', 'v1beta', credentials=credentials)

def hae_komennot():
    request = {
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "dateRanges": [{"startDate": "2025-01-01", "endDate": "today"}]
    }

    response = analytics.properties().runReport(
        property="properties/486994677",
        body=request
    ).execute()

    return response

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Näytä komentojen käyttömäärät, aktiivisimmat käyttäjät tai omat komennot.")
    @app_commands.checks.has_role("24G")
    @cooldown("stats")
    @app_commands.choices(
        tyyppi=[
            app_commands.Choice(name="Komennot", value="komennot"),
            app_commands.Choice(name="Käyttäjät", value="kayttajat"),
            app_commands.Choice(name="Omat komennot", value="omat"),
        ]
    )
    async def stats(self, interaction: discord.Interaction, tyyppi: app_commands.Choice[str]):
        await asyncio.to_thread(kirjaa_komento_lokiin, self.bot, interaction, "/stats")
        await asyncio.to_thread(kirjaa_ga_event, interaction.user.id, "stats_komento")
        await interaction.response.defer(ephemeral=True)

        if tyyppi.value == "komennot":
            data = await asyncio.to_thread(hae_komennot)
            if not data:
                await interaction.followup.send("Ei löytynyt tietoja analysoitavaksi.")
                return

            event_usage = {}
            for event in data.get("rows", []):
                nimi = event["dimensionValues"][0]["value"]
                määrä = int(event["metricValues"][0]["value"])
                event_usage[nimi] = event_usage.get(nimi, 0) + määrä

            top = sorted(event_usage.items(), key=lambda x: x[1], reverse=True)
            teksti = "\n".join([f"{komento}: ``{lkm} kertaa``" for komento, lkm in top])
            await interaction.followup.send("**Kaikkien komentojen käyttömäärät:**\n" + teksti)

        elif tyyppi.value == "kayttajat":
            log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                await interaction.followup.send("Lokikanavaa ei löytynyt.")
                return

            laskuri = Counter()
            async for msg in log_channel.history(limit=1000):
                if (match := re.search(r"\((\d{17,})\)", msg.content)):
                    user_id = int(match.group(1))
                    laskuri[user_id] += 1

            if not laskuri:
                await interaction.followup.send("Ei löytynyt komentoja.")
                return

            viestit = []
            for i, (user_id, count) in enumerate(laskuri.most_common(10), start=1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    viestit.append(f"{i}. {user.name}#{user.discriminator} (<@{user_id}>): ``{count} komentoa``")
                except:
                    viestit.append(f"{i}. <@{user_id}>: ``{count} komentoa``")

            await interaction.followup.send("**Aktiivisimmat käyttäjät:**\n" + "\n".join(viestit))

        elif tyyppi.value == "omat":
            log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                await interaction.followup.send("Lokikanavaa ei löytynyt.")
                return

            user_id = interaction.user.id
            laskuri = Counter()

            async for msg in log_channel.history(limit=1000):
                if f"({user_id})" in msg.content:
                    if (match := re.search(r"Komento: `(.+?)`", msg.content)):
                        komento = match.group(1)
                        laskuri[komento] += 1

            if not laskuri:
                await interaction.followup.send("Et ole käyttänyt vielä yhtään komentoa.")
                return

            rivit = [f"{komento}: ``{määrä} kertaa``" for komento, määrä in laskuri.most_common()]
            await interaction.followup.send(f"**Omat komennot ({interaction.user.display_name}):**\n" + "\n".join(rivit))

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Stats(bot)
    await bot.add_cog(cog)
    
