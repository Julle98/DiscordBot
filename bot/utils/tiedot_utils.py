import discord
import os
import json
from io import BytesIO
from datetime import datetime, timedelta
from discord import Interaction
import zipfile
from pathlib import Path
from discord import ui
from dotenv import load_dotenv
from collections import Counter
from bot.utils.bot_setup import bot
from datetime import datetime
import re

load_dotenv()

JSON_DIR = Path(os.getenv("JSON_DIR"))
JSON_DIRS = Path(os.getenv("JSON_DIRS"))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
MODLOG_CHANNEL_ID = (int(os.getenv("MODLOG_CHANNEL_ID", 0)))
SLOWMODE_CHANNEL_ID = (int(os.getenv("SLOWMODE_CHANNEL_ID", 0)))
LOG_CHANNEL_ID = (int(os.getenv("LOG_CHANNEL_ID", 0)))
BACKUP_JSON_PATH = Path(os.getenv("BACKUP_JSON_PATH", "backup"))

TIEDOSTOT = {
    "Tehtävät": JSON_DIR / "tasks.json",
    "Ostokset": JSON_DIRS / "ostot.json",
    "Streakit": JSON_DIR / "streaks.json",
    "Tarjous": JSON_DIRS / "tarjous.json",
    "XP-data": XP_JSON_PATH / "users_xp.json",
    "Puhe-streak": XP_JSON_PATH / "users_streak.json",
}

KATEGORIAT = list(TIEDOSTOT.keys()) + ["Moderointi", "Toiminta", "Komennot",]

def varmuuskopioi_json_tiedostot():
    BACKUP_JSON_PATH.mkdir(parents=True, exist_ok=True)
    for nimi, polku in TIEDOSTOT.items():
        if polku.exists():
            backup_polku = BACKUP_JSON_PATH / f"{nimi}_backup.json"
            try:
                with open(polku, "r", encoding="utf-8") as src, open(backup_polku, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"Varmuuskopiointivirhe tiedostolle {nimi}:", e)

def jäsennä_tehtäväviesti(viesti):
    try:
        sisältö = json.loads(viesti["content"])
        tehtävä = sisältö.get("task", "")
        aikaleima = sisältö.get("timestamp", "")
        return {
            "task": tehtävä,
            "timestamp": aikaleima
        }
    except Exception as e:
        print(f"Viestin jäsennys epäonnistui: {e}")
        return None

def jäsennä_tehtävätekstistä(teksti):
    m = re.search(r"suoritti .* tehtävän (?P<tehtävä>.+?) ja sai \+(\d+) XP", teksti)
    if m:
        tehtävä = m.group("tehtävä")
        xp = int(m.group(2))
        aikaleima = datetime.now().isoformat()  
        return {
            "task": tehtävä,
            "xp": xp,
            "timestamp": aikaleima
        }
    return None

def laske_tehtävä_xp_viesteistä(viestit):
    yhteensä_xp = 0
    tehtävälista = []

    for viesti in viestit:
        tehtävä = jäsennä_tehtävätekstistä(viesti["content"])
        if tehtävä:
            yhteensä_xp += tehtävä["xp"]
            tehtävälista.append(tehtävä)

    return yhteensä_xp, tehtävälista

def hae_kokonais_xp(uid):
    try:
        with open(TIEDOSTOT["XP-data"], encoding="utf-8") as f:
            data = json.load(f)
        return data.get(uid, {}).get("xp", 0)
    except Exception as e:
        print(f"Virhe XP-datan haussa: {e}")
        return 0

async def hae_tehtävien_määrä(user_id: str):
    channel = bot.get_channel(int(os.getenv("TASK_DATA_CHANNEL_ID")))
    if not channel:
        return 0
    count = 0
    async for msg in channel.history(limit=1000):
        try:
            data = json.loads(msg.content)
            if data.get("type") == "user_task" and str(data.get("user_id")) == user_id:
                count += 1
        except:
            continue
    return count

async def hae_tehtäväviestit(user_id: str):
    kanava = bot.get_channel(int(os.getenv("TASK_DATA_CHANNEL_ID")))
    tehtävät = []
    async for msg in kanava.history(limit=500):
        try:
            data = json.loads(msg.content)
            if data.get("type") == "user_task" and str(data.get("user_id")) == user_id:
                tehtävät.append(data)
        except:
            continue
    return tehtävät

async def hae_tarjousviestit(user_id: str):
    kanava = bot.get_channel(int(os.getenv("OSTOSLOKI_KANAVA_ID")))
    viestit = []
    async for msg in kanava.history(limit=500):
        if f"<@{user_id}>" in msg.content and "Tarjous!" in msg.content:
            viestit.append(msg)
    return viestit

async def hae_ostosmäärä(user_id: str):
    channel = bot.get_channel(int(os.getenv("OSTOSLOKI_KANAVA_ID")))
    if not channel:
        return 0
    count = 0
    async for msg in channel.history(limit=500):
        if f"<@{user_id}>" in msg.content:
            count += 1
    return count

async def hae_ostosviestit(user_id: str):
    kanava = bot.get_channel(int(os.getenv("OSTOSLOKI_KANAVA_ID")))
    viestit = []

    if not kanava:
        return []

    async for msg in kanava.history(limit=500):
        if f"<@{user_id}>" in msg.content and "osti tuotteen" in msg.content:
            viestit.append(msg)

    return viestit

async def hae_käyttäjän_komennot(user_id: int):
    log_channel = bot.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
    laskuri = Counter()
    yhteensä = 0

    if not log_channel:
        return 0, {}

    async for msg in log_channel.history(limit=1000):
        if f"({user_id})" in msg.content:
            match = re.search(r"Komento:\s*/?([^\n]+)", msg.content)
            if match:
                komento = match.group(1).lstrip("/")
                laskuri[komento] += 1
                yhteensä += 1

    return yhteensä, laskuri

async def hae_käyttäjän_komennot_lista(user_id: int):
    log_channel = bot.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
    laskuri = Counter()

    if not log_channel:
        return {}

    async for msg in log_channel.history(limit=1000):
        if f"({user_id})" in msg.content:
            match = re.search(r"Komento:\s*/?([^\n]+)", msg.content)
            if match:
                komento = match.group(1).lstrip("/")
                laskuri[komento] += 1
    return laskuri

async def hae_viimeisin_aktiivisuusviesti(user_id: str):
    kanavat = [
        bot.get_channel(int(os.getenv("TASK_DATA_CHANNEL_ID"))),
        bot.get_channel(int(os.getenv("OSTOSLOKI_KANAVA_ID"))),
        bot.get_channel(SLOWMODE_CHANNEL_ID)
    ]
    viimeisin = None

    for kanava in kanavat:
        if not kanava:
            continue
        async for msg in kanava.history(limit=500):
            if f"{user_id}" in msg.content or f"<@{user_id}>" in msg.content:
                if not viimeisin or msg.created_at > viimeisin:
                    viimeisin = msg.created_at

    return viimeisin

class JäsenToimintaAnalyysi:
    def __init__(self, jäsen: discord.Member):
        self.jäsen = jäsen
        self.kanavamäärät = {}

    async def analysoi(self, guild: discord.Guild, limit=1000):
        self.kanavamäärät.clear()
        kanavat = [c for c in guild.text_channels if c.permissions_for(self.jäsen).read_messages]

        for kanava in kanavat:
            try:
                count = 0
                async for msg in kanava.history(limit=limit):
                    if msg.author == self.jäsen:
                        count += 1
                if count > 0:
                    self.kanavamäärät[kanava] = count
            except discord.Forbidden:
                continue

    def aktiivisin(self):
        if not self.kanavamäärät:
            return None, 0
        kanava = max(self.kanavamäärät, key=self.kanavamäärät.get)
        return kanava, self.kanavamäärät[kanava]

async def muodosta_kategoria_embed(kategoria: str, user: discord.User, bot, interaction: discord.Interaction) -> discord.Embed:
    uid = str(user.id)
    embed = discord.Embed(
        title=f"📦 Kategoria: {kategoria}",
        description=f"Tiedot käyttäjältä: {user.display_name}",
        color=discord.Color.blurple()
    )

    user_data = None
    historia = []

    if kategoria in TIEDOSTOT:
        path = TIEDOSTOT[kategoria]
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                user_data = data.get(uid)
        except Exception as e:
            embed.add_field(name="⚠️ Virhe", value=f"Tietojen lataus epäonnistui: {e}", inline=False)

        if kategoria == "Tehtävät":
            tehtäväviestit = await hae_tehtäväviestit(uid)
            määrä = len(tehtäväviestit)

            try:
                with open(TIEDOSTOT.get("Streakit"), encoding="utf-8") as f:
                    streaks = json.load(f)

                daily = streaks.get(uid, {}).get("daily", {})
                weekly = streaks.get(uid, {}).get("weekly", {})
                monthly = streaks.get(uid, {}).get("monthly", {})

                daily_streak = daily.get("streak", 0)
                weekly_streak = weekly.get("streak", 0)
                monthly_streak = monthly.get("streak", 0)

                if monthly_streak >= 1:
                    xp_per_task = 150
                elif weekly_streak >= 1:
                    xp_per_task = 100
                elif daily_streak >= 1:
                    xp_per_task = 50
                else:
                    xp_per_task = 50

                total_xp = määrä * xp_per_task

                embed.add_field(name="📊 Tehtävien määrä", value=f"{määrä} kpl", inline=True)
                embed.add_field(name="✨ XP yhteensä", value=f"{total_xp} XP", inline=True)
                embed.add_field(name="🔥 XP / tehtävä", value=f"{xp_per_task} XP", inline=True)

                embed.add_field(
                    name="📅 Päivittäinen streak",
                    value=f"{daily_streak} päivää",
                    inline=False
                )
                embed.add_field(
                    name="📆 Viikoittainen streak",
                    value=f"{weekly_streak} viikkoa",
                    inline=False
                )
                embed.add_field(
                    name="🗓️ Kuukausittainen streak",
                    value=f"{monthly_streak} kuukautta",
                    inline=False
                )
            except Exception as e:
                embed.add_field(name="⚠️ Virhe", value=f"Streak/XP-datan lataus epäonnistui: {e}", inline=False)

            embed.add_field(name="📄 Viimeisimmät tehtävät", value="Alla näkyy 5 viimeisintä suoritettua tehtävää:", inline=False)
            for i, tehtävä in enumerate(tehtäväviestit[:5]):
                kuvaus = tehtävä.get("task", "Tuntematon tehtävä")
                aikaleima = tehtävä.get("timestamp")
                try:
                    aika = datetime.fromisoformat(aikaleima).strftime("%d.%m.%Y %H:%M") if aikaleima else "?"
                except:
                    aika = "?"
                embed.add_field(name=f"📘 Tehtävä {i+1}", value=f"{kuvaus}\n🕒 {aika}", inline=False)

        elif kategoria == "Streakit":
            try:
                with open(TIEDOSTOT["Streakit"], encoding="utf-8") as f:
                    streak_data = json.load(f)
                data = streak_data.get(uid, {})
                embed.add_field(name="📅 Päivittäinen streak", value=f'{data.get("daily", {}).get("streak", 0)} päivää', inline=False)
                embed.add_field(name="📆 Viikoittainen streak", value=f'{data.get("weekly", {}).get("streak", 0)} viikkoa', inline=False)
                embed.add_field(name="🗓️ Kuukausittainen streak", value=f'{data.get("monthly", {}).get("streak", 0)} kuukautta', inline=False)
            except Exception as e:
                embed.add_field(name="⚠️ Virhe", value=f"Streak-datan lataus epäonnistui: {e}", inline=False)

        elif kategoria == "Komennot":
            await interaction.response.defer(ephemeral=True)

            odotus_embed = discord.Embed(
                title="⏳ Ladataan...",
                description="Haetaan tietoja, tämä vain kestää hetken...",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=odotus_embed, ephemeral=True)

            embed = discord.Embed(title="📊 Komentostatistiikka", color=discord.Color.blue())

            try:
                yhteensä, komentolista = await hae_käyttäjän_komennot(user.id)
                embed.add_field(name="💬 Komentoja käytetty", value=f"{yhteensä} kertaa", inline=True)

                if yhteensä > 0:
                    top_komennot = komentolista.most_common(5)
                    rivit = [f"- `{nimi}` ({määrä}×)" for nimi, määrä in top_komennot]
                    embed.add_field(
                        name="📚 Eniten käytetyt komennot (globaalisti)",
                        value="\n".join(rivit),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📚 Eniten käytetyt komennot (globaalisti)",
                        value="Ei komentoja havaittu.",
                        inline=False
                    )

                log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
                log_channel = bot.get_channel(log_channel_id)
                laskuri = Counter()

                if log_channel:
                    async for msg in log_channel.history(limit=1000):
                        if f"({user.id})" in msg.content:
                            if (match := re.search(r"Komento: `(.+?)`", msg.content)):
                                komento = match.group(1)
                                laskuri[komento] += 1

                    if laskuri:
                        rivit = [f"- `{komento}` ({määrä}×)" for komento, määrä in laskuri.most_common(5)]
                        embed.add_field(
                            name="📌 Omat käytetyimmät komennot",
                            value="\n".join(rivit),
                            inline=False
                        )
                        oma_yht = sum(laskuri.values())
                        embed.set_footer(text=f"Olet käyttänyt {oma_yht} komentoa.")
                    else:
                        embed.add_field(
                            name="📌 Omat käytetyimmät komennot",
                            value="Et ole käyttänyt vielä komentoja.",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="📌 Omat käytetyimmät komennot",
                        value="Lokikanavaa ei löytynyt.",
                        inline=False
                    )

            except Exception as e:
                embed.add_field(
                    name="⚠️ Virhe",
                    value=f"Komentodatan lataus epäonnistui: {e}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            valmis_embed = discord.Embed(
                title="✅ Lataus valmis",
                description="Voit sulkea tämän viestin.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=valmis_embed, ephemeral=True)

        elif kategoria == "Ostokset":
            try:
                ostosviestit = await hae_ostosviestit(str(user.id))
                if ostosviestit:
                    embed.add_field(
                        name="🛒 Ostoksia tehty",
                        value=f"{len(ostosviestit)} kpl",
                        inline=True
                    )

                    yhteensä_xp = 0  

                    for viesti in ostosviestit[:5]:
                        pvm = viesti.created_at.strftime("%d.%m.%Y %H:%M")
                        match = re.search(r"osti tuotteen (.+?) \((\d+) XP\)", viesti.content)
                        tuote = match.group(1) if match else "Tuntematon tuote"
                        hinta = int(match.group(2)) if match else 0
                        yhteensä_xp += hinta
                        embed.add_field(
                            name=f"🧾 {tuote}",
                            value=f"💰 {hinta} XP\n🗓️ {pvm}",
                            inline=False
                        )

                    embed.add_field(
                        name="🧮 XP-käyttö yhteensä",
                        value=f"{yhteensä_xp} XP (vain 5 viimeisintä ostosta huomioitu)",
                        inline=False
                    )
                else:
                    embed.add_field(name="🛒 Ostokset", value="Ei ostoksia kirjattuna.", inline=False)
            except Exception as e:
                embed.add_field(name="⚠️ Virhe", value=f"Ostosviestien käsittely epäonnistui: {e}", inline=False)

        elif kategoria == "Tarjous":
            tarjousviestit = await hae_tarjousviestit(uid)
            if tarjousviestit:
                for viesti in tarjousviestit[:5]:
                    aika = viesti.created_at.strftime("%d.%m.%Y %H:%M")    
                    teksti = re.sub(r" ?\([^)]*\)", "", viesti.content).strip()
                    embed.add_field(name="🎁 Tarjous", value=f"{teksti}\n🗓️ {aika}", inline=False)
            else:
                embed.add_field(name="🎁 Tarjous", value="Ei löydettyjä tarjousviestejä.", inline=False)

        elif kategoria == "Puhe-streak":
            try:
                with open(TIEDOSTOT["Puhe-streak"], encoding="utf-8") as f:
                    data = json.load(f)

                puhedata = data.get(str(user.id))

                if puhedata:
                    streak = puhedata.get("streak", 0)
                    pvm_str = puhedata.get("pvm")

                    try:
                        viimeisin_pvm = datetime.strptime(pvm_str, "%Y-%m-%d")
                        alku = viimeisin_pvm - timedelta(days=streak - 1)
                    except Exception:
                        viimeisin_pvm = datetime.today()
                        alku = viimeisin_pvm - timedelta(days=streak - 1)

                    alku_str = alku.strftime("%d.%m.%Y")
                    viimeisin_str = viimeisin_pvm.strftime("%d.%m.%Y")

                    embed.add_field(
                        name="🎤 Puhe-streak",
                        value=(
                            f"🔥 {streak} päivää\n"
                            f"📅 Alkoi: {alku_str}\n"
                            f"📅 Viimeisin päivä: {viimeisin_str}\n"
                            f"🆔 ID: `{user.id}`"
                        ),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🎤 Puhe-streak",
                        value="Ei puheaktiivisuutta tallennettuna.",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name="⚠️ Virhe",
                    value=f"Puhe-streakin lataus epäonnistui: {e}",
                    inline=False
                )

        elif kategoria == "XP-data":
            kokonais_xp = hae_kokonais_xp(uid)

            viestit = await hae_tehtäväviestit(uid)  
            tehtävä_xp, tehtävälista = laske_tehtävä_xp_viesteistä(viestit)

            arvio_viesti_xp = max(0, kokonais_xp - tehtävä_xp)

            tehtävä_prosentti = (tehtävä_xp / kokonais_xp) * 100 if kokonais_xp > 0 else 0
            viesti_prosentti = (arvio_viesti_xp / kokonais_xp) * 100 if kokonais_xp > 0 else 0

            embed = discord.Embed(
                title="🔢 XP-raportti",
                description=f"Käyttäjän {uid} XP-erittely",
                color=discord.Color.blue()
            )

            embed.add_field(name="🧩 XP-erittely", value=(
                f"📘 Tehtävistä: {tehtävä_xp} XP\n"
                f"🔍 Arvio viestipohjaisesta XP:stä: {arvio_viesti_xp} XP\n"
                f"✨ Yhteensä: {kokonais_xp} XP"
            ), inline=False)

            embed.add_field(name="📈 XP-jakauma (%)", value=(
                f"📘 Tehtävät: {tehtävä_prosentti:.1f}%\n"
                f"🔎 Viestit: {viesti_prosentti:.1f}%"
            ), inline=False)

    elif kategoria == "Moderointi":
        varoituskanava = bot.get_channel(MODLOG_CHANNEL_ID)
        mutekanava = bot.get_channel(MODLOG_CHANNEL_ID)
        helpkanava = bot.get_channel(int(os.getenv("HELP_CHANNEL_ID")))
        
        varoitukset = []
        mute_tiedot = []
        helppyynto = []

        async for msg in varoituskanava.history(limit=1000):
            if f"ID: {user.id}" in msg.content:
                sisältö = msg.content
                syy = sisältö.split("Syy: ")[-1].split(" |")[0]
                antaja = sisältö.split("Antaja: ")[-1].split("\n")[0]
                aika = msg.created_at.strftime("%d.%m.%Y %H:%M")

                varoitukset.append({
                    "syy": syy,
                    "antaja": antaja,
                    "aika": aika
                })

        if mutekanava:
            async for msg in mutekanava.history(limit=1000):
                if f"{user.mention}" in msg.content and "🔇 Jäähy asetettu" in msg.content:
                    sisältö = msg.content
                    rivit = sisältö.split("\n")

                    kesto = next((r.split(": ", 1)[-1] for r in rivit if "⏱ Kesto:" in r), "Tuntematon")
                    syy = next((r.split(": ", 1)[-1] for r in rivit if "📝 Syy:" in r), "Tuntematon")
                    asettaja = next((r.split(": ", 1)[-1] for r in rivit if "👮 Asetti:" in r), "Tuntematon")
                    aika = msg.created_at.strftime("%d.%m.%Y %H:%M")

                    mute_tiedot.append({
                        "kesto": kesto,
                        "syy": syy,
                        "asettaja": asettaja,
                        "aika": aika
                    })

        if helpkanava:
            async for msg in helpkanava.history(limit=500):
                if msg.content.startswith("✅ Uusi pyyntö /help-komennolla") and msg.author.id == user.id:
                    helppyynto.append(msg)

        if varoitukset:
            embed.add_field(name="⚠️ Varoitukset", value=f"{len(varoitukset)} kpl", inline=False)
            for i, data in enumerate(varoitukset[:2]):
                embed.add_field(
                    name=f"⚠️ Varoitus {i+1}",
                    value=f"📝 Syy: {data['syy']}\n👮 Antaja: {data['antaja']}\n🕒 {data['aika']}",
                    inline=False
                )
        else:
            embed.add_field(name="✅ Ei varoituksia", value="Käyttäjällä ei ole merkintöjä.", inline=False)

        if mute_tiedot:
            embed.add_field(name="🔇 Jäähyt (mute)", value=f"{len(mute_tiedot)} kertaa", inline=False)
            for i, tiedot in enumerate(mute_tiedot[:2]):
                embed.add_field(
                    name=f"🔒 Jäähy {i+1}",
                    value=f"🕒 {tiedot['aika']}\n🕓 Kesto: {tiedot['kesto']}\n📝 Syy: {tiedot['syy']}\n👮 Asetti: {tiedot['asettaja']}",
                    inline=False
                )
        else:
            embed.add_field(name="✅ Ei jäähyjä", value="Käyttäjällä ei ole jäähymerkintöjä.", inline=False)

        if helppyynto:
            embed.add_field(name="🆘 Help-pyynnöt", value=f"Pyyntöjä: {len(helppyynto)}", inline=False)
            for viesti in helppyynto[:2]:
                otsikko = viesti.content.split("\n")[1] if "\n" in viesti.content else "💁 Help-pyyntö"
                kuvaus = "\n".join(viesti.content.split("\n")[2:])
                aika = viesti.created_at.strftime("%d.%m.%Y %H:%M")
                tila = "✅ Suljettu" if "• Suljettu" in viesti.content else "🕓 Avoin"
                embed.add_field(
                    name="📥 Pyyntö",
                    value=f"**{otsikko}**\n{kuvaus}\n🕒 {aika}\n📌 Tila: {tila}",
                    inline=False
                )
        else:
            embed.add_field(name="✅ Ei help-pyyntöjä", value="Käyttäjältä ei löytynyt pyyntöjä.", inline=False)

    elif kategoria == "Toiminta":
        await interaction.response.defer(ephemeral=True)

        odotus_embed = discord.Embed(
            title="⏳ Ladataan...",
            description="Haetaan tietoja, tämä vain kestää hetken...",
            color=discord.Color.orange()
        )

        await interaction.followup.send(embed=odotus_embed, ephemeral=True)

        try:
            analyysi = JäsenToimintaAnalyysi(user)
            guild = interaction.guild
            if not guild:
                embed.add_field(name="⚠️ Virhe", value="Guild-objektia ei voitu saada.", inline=False)
            else:
                await analyysi.analysoi(guild=guild, limit=1000)

                embed = discord.Embed(
                    title="📈 Toiminta-analyysi",
                    description="Tässä tulokset jäsenen aktiivisuudesta.",
                    color=discord.Color.blue()
                )

                aktiivisin, määrä = analyysi.aktiivisin()
                if aktiivisin:
                    embed.add_field(
                        name="💬 Aktiivisin kanava",
                        value=f"{aktiivisin.mention} ({määrä} viestiä)",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💬 Aktiivisin kanava",
                        value="Ei lähetettyjä viestejä viimeaikaisesti.",
                        inline=False
                    )
                embed.add_field(
                    name="📊 Analysoitu viestimäärä",
                    value=f"{sum(analyysi.kanavamäärät.values())} viestiä",
                    inline=False
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
                
                valmis_embed = discord.Embed(
                    title="Lataus tehty! ✅",
                    description="Voit sulkea tämän viestin.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=valmis_embed, ephemeral=True)
        except Exception as e: embed.add_field(name="⚠️ Virhe", value=f"Aktiivisuusdatan lataus epäonnistui: {e}", inline=False)

    else:
        embed.add_field(name="❓ Tuntematon kategoria", value="Ei sisältöä saatavilla.", inline=False)

    embed.set_footer(text="📁 Tiedot päivittyvät reaaliaikaisesti")
    return embed

class DataValintaView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user
        for nimi in KATEGORIAT:
            self.add_item(KategoriaNappi(nimi, user=self.user))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user.id

async def käsittele_valinta(user: discord.User, valinta: str, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    odotus_embed = discord.Embed(
        title="⏳ Ladataan...",
        description=f"Haetaan tietoja kategoriasta: **{valinta}**...",
        color=discord.Color.orange()
    )

    msg = await interaction.followup.send(embed=odotus_embed, ephemeral=True)

    try:
        embed = await muodosta_kategoria_embed(valinta, user, bot, interaction)

        await msg.edit(
            content=f"📁 Kategoria: {valinta}",
            embed=embed,
            view=KategoriaView(user, valinta)
        )
    except Exception as e:
        print(f"käsittele_valinta virhe: {e}")
        await msg.edit(content="❌ Virhe tiedonhaussa.", embed=None)

class KategoriaNappi(ui.Button):
    def __init__(self, nimi, user):
        super().__init__(label=nimi, style=discord.ButtonStyle.primary)
        self.nimi = nimi
        self.user = user
        self.bot = bot

    async def callback(self, interaction):
        try:
            embed = await muodosta_kategoria_embed(self.nimi, self.user, self.bot, interaction)
            await interaction.response.edit_message(
                content=f"📁 Kategoria: {self.nimi}",
                embed=embed,
                view=KategoriaView(self.user, self.nimi)
            )
        except Exception as e:
            print(f"Embedin luonti epäonnistui: {e}")
            await interaction.response.send_message("❌ Virhe näkymän avaamisessa.", ephemeral=True)

AVAIMET_KATEGORIALLE = {
    "XP-data": ["xp", "level"],
    "XP-streakit": ["streak", "pvm"],
    "Streakit": ["streak"],
    "Puhe-streak": ["streak", "pvm"],  
}

class KategoriaView(ui.View):
    def __init__(self, user, valittu=None):
        super().__init__(timeout=None)
        self.user = user
        self.kategoria = valittu

        if not valittu:
            for nimi in KATEGORIAT:
                self.add_item(KategoriaNappi(nimi, user))
        else:
            self.add_item(PalaaNappi(user))
            self.add_item(LataaNappi(valittu, user, AVAIMET_KATEGORIALLE.get(valittu, [])))
            self.add_item(PoistaNappi(valittu, user, AVAIMET_KATEGORIALLE.get(valittu, [])))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

class KatsoNappi(ui.Button):
    def __init__(self, user):
        super().__init__(label="Katso tiedot", style=discord.ButtonStyle.secondary)
        self.user = user

    async def callback(self, interaction):
        try:
            await interaction.response.edit_message(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None)
            )
        except discord.NotFound:
            print("⚠️ Interaktio vanhentunut — käytetään followup.send")
            await interaction.followup.send(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None),
                ephemeral=True
            )
        except Exception as e:
            print(f"KatsoNappi virhe: {e}")
            await interaction.response.send_message("❌ Virhe näkymän avaamisessa.", ephemeral=True)

class PalaaNappi(ui.Button):
    def __init__(self, user, nimi="Päävalinta"):
        super().__init__(label="🔙 Palaa alkuun", style=discord.ButtonStyle.secondary)
        self.user = user
        self.nimi = nimi

    async def callback(self, interaction):
        try:
            await interaction.response.edit_message(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None)
            )
        except discord.NotFound:
            print("⚠️ Interaktio vanhentunut — käytetään followup.send")
            await interaction.followup.send(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None),
                ephemeral=True
            )
        except Exception as e:
            print(f"PalaaNappi virhe: {e}")
            await interaction.response.send_message("❌ Virhe näkymän avaamisessa.", ephemeral=True)

class LataaNappi(ui.Button):
    def __init__(self, nimi, user, avaimet: list[str] = None):
        super().__init__(label="Lataa tiedosto", style=discord.ButtonStyle.success)
        self.nimi = nimi
        self.user = user
        self.avaimet = avaimet or []  

    async def callback(self, interaction):
        varmuuskopioi_json_tiedostot()
        path = TIEDOSTOT.get(self.nimi)
        if not path or not path.exists():
            await interaction.response.send_message("❌ Tiedostoa ei löytynyt.", ephemeral=True)
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            alkuperäinen = data.get(str(self.user.id))
            if not alkuperäinen:
                await interaction.response.send_message("ℹ️ Sinulla ei ole dataa tässä tiedostossa.", ephemeral=True)
                return

            suodatettu = {key: alkuperäinen[key] for key in self.avaimet if key in alkuperäinen}

            if not suodatettu:
                await interaction.response.send_message("ℹ️ Ei ladattavaa dataa valituilla avaimilla.", ephemeral=True)
                return

            buffer = BytesIO()
            json.dump({str(self.user.id): suodatettu}, buffer, ensure_ascii=False, indent=2)
            buffer.seek(0)
            await interaction.response.send_message(
                file=discord.File(buffer, filename=f"{self.nimi}_{self.user.id}.txt"),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("⚠️ Lataus epäonnistui.", ephemeral=True)

class PoistaNappi(ui.Button):
    def __init__(self, nimi, user, avaimet: list[str] = None):
        super().__init__(label="Poista tiedot", style=discord.ButtonStyle.danger)
        self.nimi = nimi
        self.user = user
        self.avaimet = avaimet or []

    async def callback(self, interaction):
        await interaction.response.send_modal(
            PoistovarmistusModal(self.nimi, [TIEDOSTOT[self.nimi]], self.user, self.avaimet)
        )

class IlmoitaVirheNappi(ui.Button):
    def __init__(self, user):
        super().__init__(label="Ilmoita virheestä", style=discord.ButtonStyle.danger)
        self.user = user

    async def callback(self, interaction):
        modlog = bot.get_channel(MOD_LOG_CHANNEL_ID)
        if modlog:
            await modlog.send(
                f"🚨 *Varoitusvirhe-ilmoitus*\nKohde: {self.user.mention} ({self.user.id})\nIlmoittaja: {interaction.user.mention} ({interaction.user.id})\nAika: <t:{int(discord.utils.utcnow().timestamp())}:F>"
            )
        await interaction.response.send_message("✅ Ilmoitus lähetetty moderaattoreille.", ephemeral=True)

class PoistovarmistusModal(ui.Modal, title="Vahvista tietojen poisto"):
    vahvistus = ui.TextInput(label="Kirjoita VAHVISTA poistaaksesi", placeholder="vahvista", required=True)

    def __init__(self, nimi: str, polut: list[Path], user: discord.User, avaimet: list[str] = None):
        super().__init__()
        self.nimi = nimi
        self.polut = polut
        self.user = user
        self.avaimet = avaimet or []

    async def on_submit(self, interaction: discord.Interaction):
        if self.vahvistus.value.lower() != "vahvista":
            await interaction.response.send_message("❌ Vahvistus epäonnistui. Tietoja ei poistettu.", ephemeral=True)
            return

        tiedot_poistettu = False
        koko_poisto = False

        for polku in self.polut:
            try:
                if polku.exists():
                    with open(polku, "r+", encoding="utf-8") as f:
                        data = json.load(f)
                        uid = str(self.user.id)
                        if uid in data:
                            if self.avaimet:
                                for avain in self.avaimet:
                                    if avain in data[uid]:
                                        del data[uid][avain]
                                        tiedot_poistettu = True
                                if not data[uid]:  
                                    del data[uid]
                                    koko_poisto = True
                            else:
                                del data[uid]
                                koko_poisto = True
                                tiedot_poistettu = True

                            f.seek(0)
                            json.dump(data, f, indent=2, ensure_ascii=False)
                            f.truncate()
            except Exception as e:
                print("Poistovirhe:", e)

        if tiedot_poistettu:
            viesti = (
                f"🗑️ Poistettiin {'kaikki' if koko_poisto else 'valitut'} tiedot kohteesta **{self.nimi}**."
            )
        else:
            viesti = f"ℹ️ Ei löytynyt poistettavaa dataa kohteesta **{self.nimi}**."

        await interaction.response.send_message(viesti, ephemeral=True)
        await logita_poisto(interaction.user, self.nimi, self.user)

async def logita_poisto(poistaja: discord.User, kohde: str, käyttäjä: discord.User):
    kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if kanava:
        await kanava.send(
            f"🗑️ **Poisto:** {kohde}\n"
            f"👤 Kohdekäyttäjä: {käyttäjä.mention} ({käyttäjä.id})\n"
            f"👮 Poistaja: {poistaja.mention} ({poistaja.id})\n"
            f"🕒 Aika: <t:{int(discord.utils.utcnow().timestamp())}:F>"
        )