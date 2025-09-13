import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
import aiohttp
from datetime import datetime
from typing import List

CODES = {
    0: ("☀️", "Selkeä"), 1: ("🌤️", "Enimmäkseen selkeä"), 2: ("⛅", "Puolipilvinen"),
    3: ("☁️", "Pilvinen"), 45: ("🌫️", "Sumu"), 48: ("🌫️", "Kura/sumu"),
    51: ("🌦️", "Kevyt tihku"), 53: ("🌦️", "Tihku"), 55: ("🌧️", "Voimakas tihku"),
    61: ("🌦️", "Kevyt sade"), 63: ("🌧️", "Sade"), 65: ("🌧️", "Rankkasade"),
    71: ("🌨️", "Kevyt lumi"), 73: ("🌨️", "Lumisade"), 75: ("❄️", "Kova lumisade"),
    80: ("🌦️", "Kuuroja"), 81: ("🌧️", "Voimakkaita kuuroja"), 82: ("⛈️", "Rankkoja kuuroja"),
    95: ("⛈️", "Ukkonen"), 96: ("⛈️", "Ukkonen + rakeita"), 99: ("⛈️", "Voimakas ukkonen + rakeita"),
}

def suunta_kompassina(asteet):
    suunnat = [
        "Pohjoinen", "Pohjoiskoillinen", "Koillinen", "Itäkoillinen",
        "Itä", "Itäkaakko", "Kaakko", "Eteläkaakko",
        "Etelä", "Etelälounas", "Lounas", "Länsilounas",
        "Länsi", "Länsiluode", "Luode", "Pohjoisluode"
    ]
    return suunnat[int((asteet + 11.25) % 360 / 22.5)]

def ryhmittele_voimakkuudet(tunnit, arvot, raja):
    ryhmat = []
    alku = None
    min_arvo = max_arvo = None

    for i, arvo in enumerate(arvot):
        if arvo >= raja:
            if alku is None:
                alku = tunnit[i]
                min_arvo = max_arvo = arvo
            else:
                max_arvo = max(max_arvo, arvo)
                min_arvo = min(min_arvo, arvo)
        else:
            if alku:
                ryhmat.append(f"{alku}–{tunnit[i-1]} ({min_arvo:.1f}–{max_arvo:.1f})")
                alku = None

    if alku:
        ryhmat.append(f"{alku}–{tunnit[-1]} ({min_arvo:.1f}–{max_arvo:.1f})")

    return ryhmat

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sää", description="Näytä sää tietyltä paikkakunnalta")
    @app_commands.describe(
        paikka="Kaupunki tai alue",
        tiedot="Valitse säätietotyyppi",
        näytä_sade="Näytä jokaisen tunnin kohdalla sade",
        näytä_tuuli="Näytä jokaisen tunnin kohdalla tuuli"
    )
    @app_commands.choices(tiedot=[
        app_commands.Choice(name="Nykyinen sää", value="now"),
        app_commands.Choice(name="12h ennuste", value="hourly"),
        app_commands.Choice(name="7 päivän ennuste", value="daily"),
    ])
    async def saa(
        self,
        interaction: discord.Interaction,
        paikka: str,
        tiedot: app_commands.Choice[str],
        näytä_sade: bool = False,
        näytä_tuuli: bool = False
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/sää")
        await kirjaa_ga_event(self.bot, interaction.user.id, "sää_komento")
        await interaction.response.defer(thinking=True)

        async with aiohttp.ClientSession() as session:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={paikka}&count=1&language=fi"
            async with session.get(geo_url) as r:
                data = await r.json()
                if "results" not in data:
                    return await interaction.followup.send("❌ Paikkaa ei löytynyt.")
                res = data["results"][0]
                lat, lon = res["latitude"], res["longitude"]
                city = res["name"]

            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                "&current_weather=true"
                "&hourly=temperature_2m,weathercode,precipitation_probability,precipitation,windspeed_10m,winddirection_10m"
                "&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,windspeed_10m_max"
                "&forecast_days=7&timezone=auto"
            )
            async with session.get(url) as r:
                weather = await r.json()

        embed = discord.Embed(title=f"Sää: {city}", color=0x1E90FF)
        now = datetime.now().isoformat(timespec='hours')
        start_index = next((i for i, t in enumerate(weather["hourly"]["time"]) if t.startswith(now[:13])), 0)

        if tiedot.value == "now":
            cur = weather["current_weather"]
            idx = start_index

            temp = cur["temperature"]
            code = cur["weathercode"]
            icon, desc = CODES.get(code, ("❓", "Tuntematon"))

            rain_mm = weather["hourly"]["precipitation"][idx]
            rain_prob = weather["hourly"]["precipitation_probability"][idx]
            wind_speed = cur["windspeed"]
            wind_dir = weather["hourly"]["winddirection_10m"][idx]

            embed.add_field(
                name="Nyt",
                value=(
                    f"{icon} {desc}\n"
                    f"🌡️ {temp}°C\n"
                    f"🌧️ {rain_mm:.1f} mm ({rain_prob}%)\n"
                    f"💨 {wind_speed:.1f} m/s ({suunta_kompassina(wind_dir)})"
                ),
                inline=False
            )

            if rain_mm >= 5:
                embed.add_field(name="⚠️ Rankkasade nyt!", value=f"{rain_mm:.1f} mm", inline=False)
            if wind_speed >= 10:
                embed.add_field(name="🍃 Voimakas tuuli nyt!", value=f"{wind_speed:.1f} m/s", inline=False)
            if temp < 0:
                embed.add_field(name="🧊 Pakkasta!", value=f"Lämpötila: {temp}°C", inline=False)

        elif tiedot.value == "hourly":
            txt = []
            tunnit = []
            sade_arvot = []
            tuuli_arvot = []
            pakkaset = []

            for i in range(start_index, start_index + 12):
                if i >= len(weather["hourly"]["time"]):
                    break
                time_str = weather["hourly"]["time"][i].split("T")[1]
                temp = weather["hourly"]["temperature_2m"][i]
                rain_mm = weather["hourly"]["precipitation"][i]
                rain_prob = weather["hourly"]["precipitation_probability"][i]
                wind_speed = weather["hourly"]["windspeed_10m"][i]
                wind_dir = weather["hourly"]["winddirection_10m"][i]
                icon = CODES.get(weather["hourly"]["weathercode"][i], ("❓", ""))[0]

                row = f"{time_str}: {icon} 🌡️ {temp}°C"
                if näytä_sade:
                    row += f" | 🌧️ {rain_mm:.1f} mm ({rain_prob}%)"
                if näytä_tuuli:
                    row += f" | 💨 {wind_speed:.1f} m/s ({suunta_kompassina(wind_dir)})"
                txt.append(row)

                tunnit.append(time_str)
                sade_arvot.append(rain_mm)
                tuuli_arvot.append(wind_speed)
                if temp < 0:
                    pakkaset.append(f"{time_str} ({temp}°C)")

            embed.add_field(name="⏳ Seuraavat 12h", value="\n".join(txt), inline=False)

            sade_varoitukset = ryhmittele_voimakkuudet(tunnit, sade_arvot, raja=5)
            tuuli_varoitukset = ryhmittele_voimakkuudet(tunnit, tuuli_arvot, raja=10)

            if sade_varoitukset:
                embed.add_field(name="⚠️ Rankkasateita", value="\n".join(sade_varoitukset), inline=False)
            if tuuli_varoitukset:
                embed.add_field(name="🍃 Voimakkaita tuulia", value="\n".join(tuuli_varoitukset), inline=False)
            if pakkaset:
                embed.add_field(name="🧊 Pakkasta", value="\n".join(pakkaset), inline=False)

        elif tiedot.value == "daily":
            txt = []
            päivät = []
            sade_arvot = []
            tuuli_arvot = []
            pakkasmin = []

            for i in range(7):
                date = weather["daily"]["time"][i]
                t_min = weather["daily"]["temperature_2m_min"][i]
                t_max = weather["daily"]["temperature_2m_max"][i]
                rain_mm = weather["daily"]["precipitation_sum"][i]
                wind_max = weather["daily"]["windspeed_10m_max"][i]
                icon = CODES.get(weather["daily"]["weathercode"][i], ("❓", ""))[0]

                row = f"{date}: {icon} 🌡️ {t_min}–{t_max}°C"
                txt.append(row)

                päivät.append(date)
                sade_arvot.append(rain_mm)
                tuuli_arvot.append(wind_max)
                if t_min < 0:
                    pakkasmin.append(t_min)

            embed.add_field(name="📅 7 päivän ennuste", value="\n".join(txt), inline=False)

            sade_varoitukset = ryhmittele_voimakkuudet(päivät, sade_arvot, raja=10)
            tuuli_varoitukset = ryhmittele_voimakkuudet(päivät, tuuli_arvot, raja=12)
            pakkasvaroitukset = ryhmittele_voimakkuudet(päivät, pakkasmin, raja=0)

            if sade_varoitukset:
                embed.add_field(name="⚠️ Rankkasateita", value="\n".join(sade_varoitukset), inline=False)
            if tuuli_varoitukset:
                embed.add_field(name="🍃 Voimakkaita tuulia", value="\n".join(tuuli_varoitukset), inline=False)
            if pakkasvaroitukset:
                embed.add_field(name="🧊 Pakkasta", value="\n".join(pakkasvaroitukset), inline=False)

        embed.set_footer(text=f"Lähde: Open-Meteo • Päivitetty: {datetime.now().strftime('%d.%m.%Y klo %H:%M')}")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))