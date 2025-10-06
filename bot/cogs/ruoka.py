import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, time  
import aiohttp
import json
import os
import calendar
import re
from typing import Optional
from datetime import timedelta
    
from bot.utils.ruokailuvuorot_utils import parse_schedule
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.ruokailuvuorot_utils import lue_tiedosto_turvallisesti

async def logita_äänestys(interaction: discord.Interaction, päivä_id: str, ääni: str):
    logikanava_id = os.getenv("CONSOLE_LOG")
    if not logikanava_id:
        return
    logikanava = interaction.client.get_channel(int(logikanava_id))
    if logikanava:
        await logikanava.send(
            f"🗳️ {interaction.user.name} äänesti {ääni} ruokalistalle ({päivä_id})"
        )

class RuokaÄänestysView(discord.ui.View):
    def __init__(self, päivä_id: str, interaction: discord.Interaction = None):
        super().__init__(timeout=None)
        self.päivä_id = päivä_id
        self.interaction = interaction 
        self.äänet = self.lataa_äänet()
        self.käyttäjä_äänet = self.lataa_käyttäjä_äänet()

    def lataa_äänet(self):
        polku = os.getenv("VOTE_DATA_PATH")
        try:
            with open(polku, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(self.päivä_id, {"👍": 0, "👎": 0})
        except:
            return {"👍": 0, "👎": 0}

    def lataa_käyttäjä_äänet(self):
        polku = os.getenv("VOTE_USER_PATH")
        try:
            with open(polku, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(self.päivä_id, {})
        except:
            return {}

    def tallenna_äänet(self):
        polku = os.getenv("VOTE_DATA_PATH")
        try:
            with open(polku, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
        data[self.päivä_id] = self.äänet
        with open(polku, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def tallenna_käyttäjä_äänet(self):
        polku = os.getenv("VOTE_USER_PATH")
        try:
            with open(polku, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
        data[self.päivä_id] = self.käyttäjä_äänet
        with open(polku, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def käsittele_ääni(self, interaction: discord.Interaction, ääni: str, button: discord.ui.Button):
        käyttäjä_id = str(interaction.user.id)
        if käyttäjä_id in self.käyttäjä_äänet:
            await interaction.response.send_message("⚠️ Voit äänestää vain kerran!", ephemeral=True)
            return

        self.äänet[ääni] += 1
        self.käyttäjä_äänet[käyttäjä_id] = ääni
        button.label = f"{ääni} {self.äänet[ääni]}"
        self.tallenna_äänet()
        self.tallenna_käyttäjä_äänet()
        await interaction.response.edit_message(view=self)
        await logita_äänestys(interaction, self.päivä_id, ääni)

    @discord.ui.button(label="👍 0", style=discord.ButtonStyle.success, custom_id="vote_up")
    async def vote_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.käsittele_ääni(interaction, "👍", button)

    @discord.ui.button(label="👎 0", style=discord.ButtonStyle.danger, custom_id="vote_down")
    async def vote_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.käsittele_ääni(interaction, "👎", button)

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

def hae_merkinnät(nimi):
    osumat = re.findall(r"\(([^)]+)\)", nimi)
    return ", ".join(osumat) if osumat else ""

def vanha_meunu_yliviivaus(menu_date: str, current_time: datetime, delay_hours: int = 12) -> bool:
    try:
        menu_datetime = datetime.strptime(menu_date, "%Y-%m-%d")
        strike_time = menu_datetime + timedelta(hours=delay_hours)
        return current_time >= strike_time
    except Exception as e:
        print(f"[DEBUG] Virhe yliviivauslogiikassa: {e}")
        return False

async def hae_ruoka(interaction: discord.Interaction, valinta="päivän ruoka", kasvisvaihtoehto=False, merkinnät=False, milloin_viimeksi=False, näytä_äänet=False):
    try:
        url_map = {
            "päivän ruoka": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "tämän viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/page-data.json",
            "seuraavan viikon ruokalista": "https://kouluruoka.fi/page-data/menu/vantaa_tikkurilanlukio/2/page-data.json"
        }

        data = await fetch_menu_data(url_map[valinta])
        if not data:
            await interaction.followup.send("📂 Ruokalistaa ei voitu hakea.", ephemeral=True)
            return

        days = data["result"]["pageContext"]["menu"]["Days"]

        if valinta == "päivän ruoka":
            tänään = datetime.now().strftime("%-d.%-m.")
            päivän_ruoat = next((day for day in days if tänään in day["Date"]), None)
            if not päivän_ruoat:
                await interaction.followup.send("📅 Tälle päivälle ei löytynyt ruokalistaa.", ephemeral=True)
                return

            nykyhetki = datetime.now().time()
            if nykyhetki > time(11, 50):
                await interaction.followup.send("⏳ Ruokailu on jo ohi, joten miksi haluat nähdä ruoan?", ephemeral=True)
                return

            days = [päivän_ruoat]

        try:
            with open("ruoka_historia.json", "r", encoding="utf-8", errors="replace") as f:
                ruoka_historia = json.load(f)
        except Exception as e:
            await interaction.followup.send(f"📛 Virhe luettaessa ruoka_historia.json: {e}", ephemeral=True)
            ruoka_historia = {}

        embed = discord.Embed(
            title=f"📆 Tilun ruokalista ({valinta.capitalize()})",
            description=f"📁 Päivitetty: {datetime.now().strftime('%d.%m.%Y')}\n🔗 Lähde: kouluruoka.fi",
            color=discord.Color.orange()
        )

        for day in days:
            päivä = day["Date"]
            viikonpäivä = viikonpäivä_nimi(päivä) if valinta != "päivän ruoka" else ""
            otsikko = f"{viikonpäivä} {päivä}" if viikonpäivä else päivä

            pvm_match = re.search(r"\d{1,2}\.\d{1,2}\.", päivä)
            if not pvm_match:
                continue
            pvm_str = pvm_match.group()
            dt = datetime.strptime(pvm_str, "%d.%m.").replace(year=datetime.now().year)
            tallennettava_pvm = dt.strftime("%Y-%m-%d")

            ateriat = []
            for meal in day["Meals"]:
                tyyppi = meal["MealType"].lower()
                nimi_key = meal["Name"].lower()

                ruoka_historia.setdefault(nimi_key, [])
                if tallennettava_pvm not in ruoka_historia[nimi_key]:
                    ruoka_historia[nimi_key].append(tallennettava_pvm)

                if tyyppi == "lounas" or (kasvisvaihtoehto and "kasvis" in tyyppi):
                    emoji = "🍽️" if tyyppi == "lounas" else "🥦"
                    nimi_raw = meal["Name"]
                    nimi_näytettävä = puhdista_nimi(nimi_raw) if not merkinnät else nimi_raw
                    nimi = f"{emoji} **{meal['MealType']}**: {nimi_näytettävä}"

                    if merkinnät:
                        lisätiedot = hae_merkinnät(nimi_raw) or ", ".join(meal.get("Labels", []))
                        if lisätiedot:
                            nimi += f" _(Merkinnät: {lisätiedot})_"

                    if milloin_viimeksi:
                        try:
                            viimeisin_pvm = sorted(
                                ruoka_historia[nimi_key],
                                key=lambda x: datetime.strptime(x, "%Y-%m-%d")
                            )[-1]
                            viimeisin_dt = datetime.strptime(viimeisin_pvm, "%Y-%m-%d")
                            erotus = (datetime.now().date() - viimeisin_dt.date()).days

                            if vanha_meunu_yliviivaus(viimeisin_pvm, datetime.now()):
                                nimi += f"\n> ~~Viimeksi tarjolla: {viimeisin_dt.strftime('%d.%m.%Y')} – {erotus} päivää sitten~~"
                                print(f"[DEBUG] Yliviivattu tarjoilupäivä: {viimeisin_pvm}")
                            else:
                                nimi += f"\n> _Viimeksi tarjolla: {viimeisin_dt.strftime('%d.%m.%Y')} – {erotus} päivää sitten_"
                                print(f"[DEBUG] Näytetään tarjoilupäivä normaalisti: {viimeisin_pvm}")
                        except Exception as e:
                            nimi += "\n> _(Viimeisin tarjoilupäivä ei saatavilla)_"
                            print(f"[DEBUG] Ei tarjoilupäivää: {e}")

                    ateriat.append(nimi)
    
            if ateriat:
                sisältö = "\n".join(ateriat)
                embed.add_field(name=otsikko, value=sisältö, inline=False)

        with open("ruoka_historia.json", "w", encoding="utf-8") as f:
            json.dump(ruoka_historia, f, ensure_ascii=False, indent=2)

        if not embed.fields:
            await interaction.followup.send("🍽️ Ruokia ei löytynyt listalta.", ephemeral=True)
            return

        päivä_id = f"{valinta}_{datetime.now().strftime('%Y-%m-%d')}"
        view = RuokaÄänestysView(päivä_id, interaction)

        if näytä_äänet:
            try:
                polku = os.getenv("VOTE_DATA_PATH")
                with open(polku, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tilanne = data.get(päivä_id)
                if tilanne:
                    embed.add_field(
                        name="📊 Äänestystilanne",
                        value=f"👍 {tilanne['👍']} ääntä\n👎 {tilanne['👎']} ääntä",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name="📊 Äänestystilanne",
                    value=f"⚠️ Virhe äänien lukemisessa: {e}",
                    inline=False
                )

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"⚠️ Virhe ruokalistan hakemisessa: {e}", ephemeral=True)

milloin_viimeksi: str = None

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Antaa ruokailuvuoro listan tai etsii ruokailuvuoron.")
    @app_commands.describe(
        luokkakoodi="Luokan tunnus (kaikki isolla), esim. ENA05.13 tai S25.12",
        paiva="Viikonpäivä (tyhjä = tämän päivän ruokailuvuoro)"
    )
    @app_commands.choices(paiva=[
        app_commands.Choice(name="Maanantai", value="MAANANTAI"),
        app_commands.Choice(name="Tiistai", value="TIISTAI"),
        app_commands.Choice(name="Keskiviikko", value="KESKIVIIKKO"),
        app_commands.Choice(name="Torstai", value="TORSTAI"),
        app_commands.Choice(name="Perjantai", value="PERJANTAI"),
    ])
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(
        self,
        interaction: discord.Interaction,
        luokkakoodi: str = None,
        paiva: app_commands.Choice[str] = None
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")

        raw_path = os.getenv("RAW_SCHEDULE_PATH")
        drive_link = os.getenv("RUOKAILU_DRIVE_LINK")

        weekdays = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI"]

        if paiva:
            weekday = paiva.value
        else:
            weekday = weekdays[datetime.today().weekday()] if datetime.today().weekday() < 5 else "MAANANTAI"

        if luokkakoodi:
            try:
                text = lue_tiedosto_turvallisesti(raw_path)
                if text.startswith("📛 Virhe"):
                    await interaction.response.send_message(text, ephemeral=True)
                    return

                schedule = parse_schedule(text)
                luokkakoodi = luokkakoodi.upper()

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
                message = f"📛 Virhe ruokailuvuorojen käsittelyssä: {e}"
        else:
            message = drive_link or "🔗 Linkkiä ei löytynyt."

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="ruoka", description="Näyttää Tilun ruokalistan.")
    @app_commands.checks.has_role("24G")
    @app_commands.describe(
        valinta="Valitse ruokalistan tyyppi",
        kasvisvaihtoehto="Näytä valinnainen kasvisvaihtoehto",
        merkinnät="Näytä aterioiden merkinnät (esim. allergiat)",
        milloin_viimeksi="Näytä milloin ruoka on viimeksi ollut tarjolla",
        näytä_äänet="Näytä viimeisin äänestystilanne"
    )
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str,
        kasvisvaihtoehto: bool = False,
        merkinnät: bool = False,
        milloin_viimeksi: bool = False,
        näytä_äänet: bool = False
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruoka")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruoka_komento")
        await interaction.response.defer()

        await hae_ruoka(
            interaction,
            valinta=valinta.lower(),
            kasvisvaihtoehto=kasvisvaihtoehto,
            merkinnät=merkinnät,
            milloin_viimeksi=milloin_viimeksi,
            näytä_äänet=näytä_äänet
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