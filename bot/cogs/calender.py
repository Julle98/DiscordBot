import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import datetime
import pytz
import os
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
API_KEY = os.getenv("API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID")
TIMEZONE = "Europe/Helsinki"

class Calendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kalenteri", description="Näytä tapahtumat tilu lukuvuosikalenterista.")
    @app_commands.choices(aikaväli=[
        app_commands.Choice(name="Päivä", value="päivä"),
        app_commands.Choice(name="Viikko", value="viikko"),
        app_commands.Choice(name="Seuraava viikko", value="seuraava_viikko"),
        app_commands.Choice(name="Kuukausi", value="kuukausi"),
    ])
    async def tapahtumat(self, interaction: discord.Interaction, aikaväli: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True)

        tz = pytz.timezone(TIMEZONE)
        now = datetime.datetime.now(tz)

        if aikaväli.value == "päivä":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
        elif aikaväli.value == "viikko":
            start = now - datetime.timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=7)
        elif aikaväli.value == "seuraava_viikko":
            start = now - datetime.timedelta(days=now.weekday()) + datetime.timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=7)
        else:  
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)

        start_str = start.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
        end_str = end.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")

        cal_id_encoded = urllib.parse.quote(CALENDAR_ID, safe="")

        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{cal_id_encoded}/events"
            f"?key={API_KEY}&timeMin={start_str}&timeMax={end_str}&singleEvents=true&orderBy=startTime"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                events = data.get("items", [])

        if not events:
            await interaction.followup.send(f"Ei tapahtumia ({aikaväli.name.lower()})")
            return

        embed = discord.Embed(
            title=f"Kalenteri Tilu ({aikaväli.name})",
            color=discord.Color.blue()
        )

        for event in events[:10]:  
            start_time = event["start"].get("dateTime") or event["start"].get("date")
            if "dateTime" in event["start"]:
                dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                dt_local = dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")
            else:
                dt_local = start_time  

            html_link = event.get("htmlLink", "")

            embed.add_field(
                name=event.get("summary", "Ei otsikkoa"),
                value=f"🗓️ {dt_local}\n🔗 [Avaa kalenterissa]({html_link})",
                inline=False
            )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Calendar(bot))