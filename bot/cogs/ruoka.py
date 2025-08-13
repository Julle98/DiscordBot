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
from typing import Optional

from bot.utils.ruokailuvuorot_utils import parse_schedule
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

async def hae_ruoka(interaction: discord.Interaction, valinta="päivän ruoka", kasvisvaihtoehto=False, merkinnät=False, milloin_viimeksi=False):
    try:
        url_map = {
            "päivän ruoka": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "tämän viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "seuraavan viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/2/page-data.json"
        }

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

        try:
            with open("ruoka_historia.json", "r", encoding="utf-8") as f:
                ruoka_historia = json.load(f)
        except:
            ruoka_historia = {}

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
                puhdas_nimi = puhdista_nimi(meal["Name"])
                nimi_key = puhdas_nimi.lower()

                if nimi_key not in ruoka_historia:
                    ruoka_historia[nimi_key] = []
                if päivä not in ruoka_historia[nimi_key]:
                    ruoka_historia[nimi_key].append(päivä)

                if tyyppi == "lounas" or (kasvisvaihtoehto and "kasvis" in tyyppi):
                    emoji = "🍽️" if tyyppi == "lounas" else "🥦"
                    nimi = f"{emoji} **{meal['MealType']}**: {puhdas_nimi}"
                    if merkinnät and meal.get("Labels"):
                        lisätiedot = ", ".join(meal["Labels"])
                        nimi += f" _(Merkinnät: {lisätiedot})_"

                    if milloin_viimeksi:
                        try:
                            viimeisin_pvm = sorted(
                                ruoka_historia[nimi_key],
                                key=lambda x: datetime.strptime(x, "%-d.%-m.")
                            )[-1]
                            viimeisin_dt = datetime.strptime(viimeisin_pvm, "%-d.%-m.")
                            erotus = (datetime.now() - viimeisin_dt).days
                            nimi += f"\n> _Viimeksi tarjolla: {viimeisin_pvm} – {erotus} päivää sitten_"
                        except:
                            nimi += "\n> _(Viimeisin tarjoilupäivä ei saatavilla)_"

                    ateriat.append(nimi)

            if ateriat:
                sisältö = "\n".join(ateriat)
                embed.add_field(name=otsikko, value=sisältö, inline=False)

        with open("ruoka_historia.json", "w", encoding="utf-8") as f:
            json.dump(ruoka_historia, f, ensure_ascii=False, indent=2)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"⚠️ Virhe ruokalistan hakemisessa: {e}", ephemeral=True)

milloin_viimeksi: str = None

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Näyttää uusimmat ruokailuvuorot.")
    @app_commands.describe(
        luokkakoodi="(BETA OMINAISUUS) Luokan tunnus, esim. ENA05.13 tai MAB04.13"
    )
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(self, interaction: discord.Interaction, luokkakoodi: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")

        raw_path = os.getenv("RAW_SCHEDULE_PATH")
        drive_link = os.getenv("RUOKAILU_DRIVE_LINK")

        def get_weekday_name():
            weekday_map = {
                0: "MAANANTAI",
                1: "TIISTAI",
                2: "KESKIVIIKKO",
                3: "TORSTAI",
                4: "PERJANTAI"
            }
            today = datetime.today().weekday()
            return weekday_map.get(today)

        weekday = get_weekday_name()
        if not weekday:
            await interaction.response.send_message("Tänään ei ole arkipäivä, joten ruokailuvuoroja ei näytetä.")
            return

        if luokkakoodi:
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    text = f.read()

                schedule = parse_schedule(text)

                if luokkakoodi in schedule:
                    entry = schedule[luokkakoodi].get(weekday)
                    if not entry:
                        any_entry = next(iter(schedule[luokkakoodi].values()), None)
                        entry = any_entry

                    if entry:
                        message = (
                            f"**{luokkakoodi}** ({weekday})\n"
                            f"{entry['vuoro']}\n"
                            f"Ruokailu: {entry['ruokailu']}\n"
                            f"Oppitunti: {entry['oppitunti']}"
                        )
                    else:
                        message = f"Luokkakoodille **{luokkakoodi}** ei löytynyt tietoja."
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
        merkinnät="Näytä aterioiden merkinnät (esim. allergiat)",
        milloin_viimeksi="Näytä milloin ruoka on viimeksi ollut tarjolla"
    )
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str,
        kasvisvaihtoehto: bool = False,
        merkinnät: bool = False,
        milloin_viimeksi: bool = False
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruoka")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruoka_komento")
        await interaction.response.defer()
        await hae_ruoka(
            interaction,
            valinta=valinta.lower(),
            kasvisvaihtoehto=kasvisvaihtoehto,
            merkinnät=merkinnät,
            milloin_viimeksi=milloin_viimeksi
        )

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