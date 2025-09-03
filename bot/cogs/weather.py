import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
import aiohttp

CODES = {
    0: ("☀️", "Selkeä"), 1: ("🌤️", "Enimmäkseen selkeä"), 2: ("⛅", "Puolipilvinen"),
    3: ("☁️", "Pilvinen"), 45: ("🌫️", "Sumu"), 48: ("🌫️", "Kura/sumu"),
    51: ("🌦️", "Kevyt tihku"), 53: ("🌦️", "Tihku"), 55: ("🌧️", "Voimakas tihku"),
    61: ("🌦️", "Kevyt sade"), 63: ("🌧️", "Sade"), 65: ("🌧️", "Rankkasade"),
    71: ("🌨️", "Kevyt lumi"), 73: ("🌨️", "Lumisade"), 75: ("❄️", "Kova lumisade"),
    80: ("🌦️", "Kuuroja"), 81: ("🌧️", "Voimakkaita kuuroja"), 82: ("⛈️", "Rankkoja kuuroja"),
    95: ("⛈️", "Ukkonen"), 96: ("⛈️", "Ukkonen + rakeita"), 99: ("⛈️", "Voimakas ukkonen + rakeita"),
}

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sää", description="Näytä sää tietyltä paikkakunnalta Esim. Vantaa.")
    @app_commands.describe(
        paikka="Kaupunki tai alue",
        tyyppi="Valitse mitä säätietoja näytetään"
    )
    @app_commands.choices(tyyppi=[
        app_commands.Choice(name="Nykyinen sää", value="now"),
        app_commands.Choice(name="Tuntiennuste (12h)", value="hourly"),
        app_commands.Choice(name="7 päivän ennuste", value="daily"),
    ])
    async def saa(self, interaction: discord.Interaction, paikka: str, tyyppi: app_commands.Choice[str]):
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
                "&current_weather=true&hourly=temperature_2m,weathercode"
                "&daily=temperature_2m_max,temperature_2m_min,weathercode"
                "&forecast_days=7&timezone=auto"
            )
            async with session.get(url) as r:
                weather = await r.json()

        embed = discord.Embed(title=f"Sää: {city}", color=0x1E90FF)

        if tyyppi.value == "now":
            cur = weather["current_weather"]
            e, desc = CODES.get(cur["weathercode"], ("❓", "Tuntematon"))
            embed.add_field(name="Nyt", value=f"{e} {desc}\n🌡️ {cur['temperature']}°C")

        elif tyyppi.value == "hourly":
            hours = weather["hourly"]
            txt = [f"{t.split('T')[1]}: {temp}°C {CODES.get(code, ('❓',''))[0]}"
                   for t, temp, code in zip(hours["time"][:12], hours["temperature_2m"][:12], hours["weathercode"][:12])]
            embed.add_field(name="Seuraavat 12h", value="\n".join(txt), inline=False)

        elif tyyppi.value == "daily":
            days = weather["daily"]
            txt = [f"{d}: {CODES.get(code, ('❓',''))[0]} {CODES.get(code, ('','Tuntematon'))[1]} ({tmin}–{tmax}°C)"
                   for d, tmin, tmax, code in zip(days["time"], days["temperature_2m_min"], 
                                                 days["temperature_2m_max"], days["weathercode"])]
            embed.add_field(name="7 päivän ennuste", value="\n".join(txt), inline=False)

        embed.set_footer(text="Lähde: Open-Meteo (https://open-meteo.com/)")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))