import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from datetime import datetime
import aiohttp
import json
import os
import calendar
import re

from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler

async def fetch_menu_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

def viikonpäivä_nimi(pvm_str):
    try:
        päivä, kuukausi = map(int, pvm_str.strip(".").split("."))
        vuosi = datetime.now().year
        pvm = datetime(vuosi, kuukausi, päivä)
        return calendar.day_name[pvm.weekday()].capitalize()
    except:
        return ""

def puhdista_nimi(nimi):
    return re.sub(r"\s*\([^)]*\)", "", nimi).strip()

async def hae_ruoka(interaction: discord.Interaction, valinta="päivän ruoka", kasvisvaihtoehto=False, merkinnät=False):
    try:
        url_map = {
            "päivän ruoka": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "tämän viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "seuraavan viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/2/page-data.json"
        }

        if valinta not in url_map:
            await interaction.followup.send(f"📅 Valinta '{valinta}' ei ole tuettu.")
            return

        data = await fetch_menu_data(url_map[valinta])
        if not data:
            await interaction.followup.send("📂 Ruokalistaa ei voitu hakea.")
            return

        days = data["result"]["pageContext"]["menu"]["Days"]
        if valinta == "päivän ruoka":
            tänään = datetime.now().strftime("%-d.%-m.")
            päivän_ruoat = next((day for day in days if tänään in day["Date"]), None)
            if not päivän_ruoat:
                await interaction.followup.send("📅 Tälle päivälle ei löytynyt ruokalistaa.")
                return
            days = [päivän_ruoat]

        embed = discord.Embed(
            title=f"📆 Tilun ruokalista ({valinta.capitalize()})",
            description=f"📁 Päivitetty: {datetime.now().strftime('%d.%m.%Y')}\n🔗 Lähde: KOULURUOKA.fi",
            color=discord.Color.orange()
        )

        for day in days:
            päivä = day["Date"]
            viikonpäivä = viikonpäivä_nimi(päivä) if valinta != "päivän ruoka" else ""
            otsikko = f"{viikonpäivä} {päivä}" if viikonpäivä else päivä

            ateriat = []
            for meal in day["Meals"]:
                tyyppi = meal["MealType"].lower()
                if tyyppi == "lounas" or (kasvisvaihtoehto and "kasvis" in tyyppi):
                    emoji = "🍽️" if tyyppi == "lounas" else "🥦"
                    puhdas_nimi = puhdista_nimi(meal["Name"])
                    nimi = f"{emoji} **{meal['MealType']}**: {puhdas_nimi}"
                    if merkinnät and meal.get("Labels"):
                        lisätiedot = ", ".join(meal["Labels"])
                        nimi += f" _(Merkinnät: {lisätiedot})_"
                    ateriat.append(nimi)

            if ateriat:
                embed.add_field(name=otsikko, value="\n".join(ateriat), inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"⚠️ Virhe ruokalistan hakemisessa: {e}", ephemeral=True)

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Näyttää uusimmat ruokailuvuorot.")
    @app_commands.describe(luokkakoodi="Luokan tunnus, esim. ENA05.13 tai MAB04.13")
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(self, interaction: discord.Interaction, luokkakoodi: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")

        json_path = os.getenv("SCHEDULE_JSON_PATH", "./data/ruokailuvuorot.json")
        drive_link = os.getenv("RUOKAILU_DRIVE_LINK")

        if luokkakoodi:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if luokkakoodi in data:
                    entry = data[luokkakoodi]
                    message = f"{entry['vuoro']}\n{entry['ruokailu']}\n{entry['oppitunti']}"
                else:
                    message = f"Tuntikoodia **{luokkakoodi}** ei löytynyt."
            except Exception as e:
                message = f"Virhe luettaessa tiedostoa: {e}"
        else:
            message = drive_link or "Linkkiä ei löytynyt."

        await interaction.response.send_message(message)

    @app_commands.command(name="ruoka", description="Näyttää Tilun ruokalistan.")
    @app_commands.checks.has_role("24G")
    @app_commands.describe(
        valinta="Valitse ruokalistan tyyppi",
        kasvisvaihtoehto="Näytä valinnainen kasvisvaihtoehto",
        merkinnät="Näytä aterioiden merkinnät (esim. allergiat)"
    )
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str,
        kasvisvaihtoehto: bool = False,
        merkinnät: bool = False
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruoka")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruoka_komento")
        await interaction.response.defer()
        await hae_ruoka(interaction, valinta=valinta.lower(), kasvisvaihtoehto=kasvisvaihtoehto, merkinnät=merkinnät)

    @ruoka.autocomplete("valinta")
    async def ruoka_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        vaihtoehdot = [
            "päivän ruoka",
            "tämän viikon ruokalista",
            "seuraavan viikon ruokalista",
        ]
        return [
            app_commands.Choice(name=v, value=v)
            for v in vaihtoehdot if current.lower() in v.lower()
        ]

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = ruoka(bot)
    await bot.add_cog(cog)