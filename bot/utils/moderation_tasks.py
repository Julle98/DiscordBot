from discord.ext import tasks
import discord
import os
from datetime import datetime
import json
import asyncio
from bot.utils.bot_setup import bot
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from pathlib import Path

def start_moderation_loops():
    asyncio.create_task(tarkista_ostojen_kuukausi())
    asyncio.create_task(tarkista_paivat())

aktiiviset_paivat = dict()

ostot = {}

load_dotenv()
JSON_DIR = Path(os.getenv("JSON_DIR"))
OSTO_TIEDOSTO = JSON_DIR / "ostot.json"

def lue_ostokset():
    try:
        with open(OSTO_TIEDOSTO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def tallenna_ostokset(ostot):
    with open(OSTO_TIEDOSTO, "w", encoding="utf-8") as f:
        json.dump(ostot, f, ensure_ascii=False, indent=2)

async def kysy_kayttajalta(interaction, kysymys):
    await interaction.followup.send(kysymys)
    try:
        vastaus = await bot.wait_for(
            "message",
            timeout=60.0,
            check=lambda m: m.author == interaction.user and m.channel == interaction.channel
        )
        return vastaus.content
    except asyncio.TimeoutError:
        await interaction.followup.send("Aikakatkaisu. Toiminto peruutettu.")
        return None

@tasks.loop(hours=1)
async def tarkista_ostojen_kuukausi():
    try:
        ostot = lue_ostokset()

        # Tarkista ensimmäinen päiväys
        kaikki_paivamaarat = []
        for ostot_lista in ostot.values():
            for ostos in ostot_lista:
                if "pvm" in ostos:
                    try:
                        pvm = datetime.fromisoformat(ostos["pvm"])
                        kaikki_paivamaarat.append(pvm)
                    except:
                        continue

        if not kaikki_paivamaarat:
            return  # Ei mitään tehtävää

        nyt = datetime.now()
        viimeisin = max(kaikki_paivamaarat)

        if viimeisin.month != nyt.month:
            print("Tyhjennetään ostot (uusi kuukausi)")
            tallenna_ostokset({})
    except Exception as e:
        print(f"Ostojen tarkistus epäonnistui: {e}")

@tasks.loop(hours=24)
async def tarkista_paivat():
    nyt = datetime.now(timezone.utc).date()
    for paiva, data in list(aktiiviset_paivat.items()):
        if nyt != paiva + timedelta(days=1):
            continue

        guild = bot.get_guild(data["guild_id"])
        if not guild:
            continue

        kanavat = [c for c in guild.text_channels if c.permissions_for(guild.me).read_messages]
        aloitus = datetime.combine(paiva, datetime.min.time(), tzinfo=timezone.utc)
        lopetus = datetime.combine(paiva + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        for kanava in kanavat:
            try:
                async for msg in kanava.history(after=aloitus, before=lopetus, limit=None):
                    if not msg.author.bot:
                        member = guild.get_member(msg.author.id)
                        if member:
                            data["viestimäärät"][member] += 1
            except discord.Forbidden:
                continue

        if not data["viestimäärät"]:
            aktiiviset_paivat.pop(paiva)
            continue

        top = sorted(data["viestimäärät"].items(), key=lambda x: x[1], reverse=True)[:5]

        load_dotenv()
        kanava = guild.get_channel(int(os.getenv("AKTIIVISIMMAT_KANAVA_ID")))
        rooli = guild.get_role(int(os.getenv("AKTIIVISIMMAT_ROOLI_ID")))
        estetyt_roolit = {"Mestari", "Moderaattori", "Admin", "VIP"}

        if kanava:
            alku = datetime.combine(paiva, datetime.min.time()).strftime("%d.%m.%Y %H:%M")
            loppu = datetime.combine(paiva + timedelta(days=1), datetime.min.time()).strftime("%d.%m.%Y %H:%M")
            viesti = f"**Aktiivisimmat ({alku} – {loppu}):**\n"
            for i, (käyttäjä, määrä) in enumerate(top, start=1):
                viesti += f"{i}. {käyttäjä.mention} – {määrä} viestiä\n"
            await kanava.send(viesti)

            if rooli:
                for käyttäjä, _ in top:
                    if not any(r.name in estetyt_roolit for r in käyttäjä.roles):
                        try:
                            await käyttäjä.add_roles(rooli, reason="Päivän aktiivisin viestittelijä")
                        except discord.Forbidden:
                            await kanava.send("En onnistunut antamaan roolia voittajalle.")
                        break

        aktiiviset_paivat.pop(paiva)