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

async def hae_ruoka(interaction: discord.Interaction, valinta="päivän ruoka", kasvisvaihtoehto=False, merkinnät=False, milloin_viimeksi=None):
    try:
        url_map = {
            "päivän ruoka": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "tämän viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "seuraavan viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/2/page-data.json"
        }

        food_data_file = os.getenv("FOOD_DATA_FILE")

        if milloin_viimeksi:
            kaikki_ruoat = []
            for url in url_map.values():
                data = await fetch_menu_data(url)
                if not data:
                    continue
                for day in data["result"]["pageContext"]["menu"]["Days"]:
                    päivä = day["Date"]
                    for meal in day["Meals"]:
                        nimi = puhdista_nimi(meal["Name"]).lower()
                        if milloin_viimeksi.lower() in nimi:
                            kaikki_ruoat.append((nimi, päivä))

            if kaikki_ruoat:
                viimeisin = sorted(kaikki_ruoat, key=lambda x: datetime.strptime(x[1], "%-d.%-m."))[-1]
                viesti = f"🍽️ **{milloin_viimeksi}** on viimeksi ollut tarjolla **{viimeisin[1]}**."
                await interaction.followup.send(viesti)
            else:
                await interaction.followup.send(f"🔍 Ruokaa **{milloin_viimeksi}** ei löytynyt viimeaikaisista listoista.")
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

        try:
            with open(food_data_file, "w", encoding="utf-8") as f:
                json.dump(days, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ruokalistan tallennus epäonnistui: {e}")

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
            löytyi_viimeksi = False

            for meal in day["Meals"]:
                tyyppi = meal["MealType"].lower()
                puhdas_nimi = puhdista_nimi(meal["Name"])
                if tyyppi == "lounas" or (kasvisvaihtoehto and "kasvis" in tyyppi):
                    emoji = "🍽️" if tyyppi == "lounas" else "🥦"
                    nimi = f"{emoji} **{meal['MealType']}**: {puhdas_nimi}"
                    if merkinnät and meal.get("Labels"):
                        lisätiedot = ", ".join(meal["Labels"])
                        nimi += f" _(Merkinnät: {lisätiedot})_"
                    ateriat.append(nimi)

                    if milloin_viimeksi and milloin_viimeksi.lower() in puhdas_nimi.lower():
                        löytyi_viimeksi = True

            if ateriat:
                sisältö = "\n".join(ateriat)
                if milloin_viimeksi and löytyi_viimeksi:
                    sisältö += f"\n📌 **{milloin_viimeksi}** tarjolla viimeksi {päivä}"
                embed.add_field(name=otsikko, value=sisältö, inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"⚠️ Virhe ruokalistan hakemisessa: {e}", ephemeral=True)

milloin_viimeksi: str = None

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Näyttää uusimmat ruokailuvuorot.")
    @app_commands.describe(
        luokkakoodi="(BETA OMINAISUUS) Luokan tunnus, esim. ENA05.13 tai MAB04.13",
        viikonpaiva="(Valinnainen) Viikonpäivä, esim. maanantai, tiistai..."
    )
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(self, interaction: discord.Interaction, luokkakoodi: str = None, viikonpaiva: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")

        raw_path = os.getenv("RAW_SCHEDULE_PATH")
        drive_link = os.getenv("RUOKAILU_DRIVE_LINK")

        def get_weekday_name(name=None):
            weekday_map = {
                "maanantai": "MAANANTAI",
                "tiistai": "TIISTAI",
                "keskiviikko": "KESKIVIIKKO",
                "torstai": "TORSTAI",
                "perjantai": "PERJANTAI"
            }
            if name:
                return weekday_map.get(name.lower())
            today = datetime.today().weekday()
            return list(weekday_map.values())[today] if today < 5 else None

        weekday = get_weekday_name(viikonpaiva)

        if not weekday:
            await interaction.response.send_message("Viikonpäivä ei kelpaa tai ei ole arkipäivä.")
            return

        if luokkakoodi:
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    text = f.read()

                schedule = parse_schedule(text)

                if luokkakoodi in schedule:
                    entry = schedule[luokkakoodi].get(weekday)
                    if entry:
                        message = (
                            f"**{luokkakoodi}** ({weekday})\n"
                            f"{entry['vuoro']}\n"
                            f"Ruokailu: {entry['ruokailu']}\n"
                            f"Oppitunti: {entry['oppitunti']}"
                        )
                    else:
                        message = f"Luokkakoodille **{luokkakoodi}** ei löytynyt tietoja päivälle **{weekday}**."
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
        milloin_viimeksi="Näytä milloin jokin ruoka on viimeksi ollut tarjolla"
    )
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str,
        kasvisvaihtoehto: bool = False,
        merkinnät: bool = False,
        milloin_viimeksi: Optional[str] = None
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