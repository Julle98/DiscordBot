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
HELP_CHANNEL_ID = (int(os.getenv("HELP_CHANNEL_ID", 0)))
MUTE_CHANNEL_ID = (int(os.getenv("MUTE_CHANNEL_ID", 0)))
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
    "Kuponki": JSON_DIRS / "kuponki.json",
}

KATEGORIAT = list(TIEDOSTOT.keys()) + ["Moderointi", "Toiminta", "Komennot"]

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
    m = re.search(r"suoritti.*tehtävän:? (?P<tehtävä>.+?)\s+XP: \+(\d+)", teksti)
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
        sisältö = viesti.get("content")
        if not sisältö:
            continue

        tehtävä = jäsennä_tehtävätekstistä(sisältö)
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

def hae_tuotteen_hinta(nimi: str) -> int:
    try:
        with open(JSON_DIRS / "tuotteet.json", encoding="utf-8") as f:
            tuotteet = json.load(f)
        for tuote in tuotteet:
            if tuote.get("nimi") == nimi:
                return int(tuote.get("hinta", 0))
    except Exception as e:
        print(f"Hinnan haku epäonnistui: {e}")
    return 0

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

    if user.id != interaction.user.id:
        roolit = getattr(interaction.user, "roles", [])
        is_mestari = any(r.name == "Mestari" for r in roolit)
        if is_mestari:
            embed.description = (
                f"👀 Katselet toisen käyttäjän tietoja: **{user.display_name}**\n\n"
                + embed.description
            )
        else:
            embed.clear_fields()
            embed.title = "🚫 Ei oikeuksia"
            embed.description = "Sinulla ei ole oikeutta tarkastella muiden käyttäjien tietoja."
            embed.color = discord.Color.red()
            return embed

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
        
        elif kategoria == "Kuponki":
            try:
                uid = str(uid)

                try:
                    with open(TIEDOSTOT["Kuponki"], encoding="utf-8") as f:
                        tapahtumat_data = json.load(f)
                    tapahtumat = tapahtumat_data.get(uid, [])
                except Exception as e:
                    tapahtumat = []
                    print(f"Kuponkitapahtumien lataus epäonnistui: {e}")

                try:
                    with open(JSON_DIRS / "kuponki.json", encoding="utf-8") as f:
                        kuponki_data = json.load(f)
                except Exception as e:
                    kuponki_data = {}
                    print(f"Kuponkidatan lataus epäonnistui: {e}")

                try:
                    with open(JSON_DIRS / "tuotteet.json", encoding="utf-8") as f:
                        tuotteet_lista = json.load(f)
                except Exception as e:
                    tuotteet_lista = []
                    print(f"Tuotedatan lataus epäonnistui: {e}")

                try:
                    with open(JSON_DIRS / "ostot.json", encoding="utf-8") as f:
                        ostot_data = json.load(f)
                    ostot = ostot_data.get(uid, [])
                except Exception as e:
                    ostot = []
                    print(f"Ostotiedoston lataus epäonnistui: {e}")

                def hae_tuotteen_hinta(nimi: str) -> int:
                    for tuote in tuotteet_lista:
                        if tuote.get("nimi") == nimi:
                            return int(tuote.get("hinta", 0))
                    return 0

                def hae_tarjousprosentti(nimi: str) -> int:
                    for tuote in tuotteet_lista:
                        if tuote.get("nimi") == nimi:
                            return int(tuote.get("tarjousprosentti", 0))
                    return 0

                laskuri = Counter()
                tuotteet = {}
                säästö_yhteensä = 0

                for tapahtuma in tapahtumat:
                    kuponki = tapahtuma.get("kuponki", "Tuntematon")
                    tuote = tapahtuma.get("tuote", "Tuntematon tuote")
                    aika = tapahtuma.get("aika", "?")
                    laskuri[kuponki] += 1
                    tuotteet.setdefault(kuponki, []).append((tuote, aika))

                    prosentti = kuponki_data.get(kuponki, {}).get("prosentti", 0)
                    hinta = hae_tuotteen_hinta(tuote)
                    tuote_prosentti = hae_tarjousprosentti(tuote)

                    kokonaisprosentti = prosentti + tuote_prosentti
                    if hinta and kokonaisprosentti:
                        säästö = hinta * (kokonaisprosentti / 100)
                        säästö_yhteensä += säästö

                if not tapahtumat:
                    for kuponki_nimi, kuponki_info in kuponki_data.items():
                        kayttajat_dict = kuponki_info.get("kayttajat_dict", {})
                        kayttoja = kayttajat_dict.get(uid, 0)
                        if kayttoja > 0:
                            laskuri[kuponki_nimi] = kayttoja
                            tuotteet[kuponki_nimi] = [("?", "?")] * kayttoja
                            prosentti = kuponki_info.get("prosentti", 0)
                            hinta = 1000  
                            säästö_yhteensä += kayttoja * hinta * (prosentti / 100)

                for ostos in ostot:
                    nimi_raw = ostos.get("nimi", "")
                    nimi = nimi_raw.replace(" (Tarjous!)", "").strip()

                    normihinta = hae_tuotteen_hinta(nimi)
                    ostohinta = None

                    for kuponki_nimi, kuponki_info in kuponki_data.items():
                        if kuponki_nimi in nimi_raw:
                            prosentti = kuponki_info.get("prosentti", 0)
                            ostohinta = int(normihinta * (1 - prosentti / 100))
                            säästö = normihinta - ostohinta
                            if säästö > 0:
                                säästö_yhteensä += säästö
                            break

                    if ostohinta is None and "Tarjous" in nimi_raw:
                        for tuote in tuotteet_lista:
                            if tuote.get("nimi") == nimi:
                                tarjous_prosentti = tuote.get("tarjousprosentti", 0)
                                ostohinta = int(normihinta * (1 - tarjous_prosentti / 100))
                                säästö = normihinta - ostohinta
                                if säästö > 0:
                                    säästö_yhteensä += säästö
                                break

                embed.add_field(name="📊 Käytetyt kupongit", value=f"{sum(laskuri.values())} kertaa", inline=True)

                for kuponki, määrä in laskuri.items():
                    rivit = [f"• {tuote} ({aika[:10]})" for tuote, aika in tuotteet[kuponki][:3]]

                    kuponki_info = kuponki_data.get(kuponki, {})
                    kayttajat_dict = kuponki_info.get("kayttajat_dict", {})
                    kayttoja = kayttajat_dict.get(uid, 0)
                    max_per = kuponki_info.get("maxkayttoja_per_jasen", "∞")

                    embed.add_field(
                        name=f"🎟️ {kuponki} ({määrä}×, käytetty {kayttoja}/{max_per})",
                        value="\n".join(rivit),
                        inline=False
                    )

                if ostot:
                    rivit = [f"• {ostos['nimi']} ({ostos['pvm'][:10]})" for ostos in ostot[:5]]
                    embed.add_field(
                        name="🛒 Ostetut tuotteet",
                        value="\n".join(rivit),
                        inline=False
                    )

                embed.add_field(
                    name="💸 Arvioitu XP-säästö",
                    value=f"{int(säästö_yhteensä)} XP",
                    inline=False
                )

                if not laskuri and not ostot:
                    embed.add_field(
                    name="🎟️ Kuponkiaktiivisuus",
                    value="Ei kuponkien käyttöä tai ostoksia tallennettuna.",
                    inline=False
                )

            except Exception as e:
                embed.add_field(name="⚠️ Virhe", value=f"Kuponkidatan käsittely epäonnistui: {e}", inline=False)

        elif kategoria == "Puhe-streak":
            try:
                with open(TIEDOSTOT["Puhe-streak"], encoding="utf-8") as f:
                    data = json.load(f)

                puhedata = data.get(str(user.id))

                if puhedata:
                    streak = puhedata.get("streak", 0)
                    pisin = puhedata.get("pisin", streak)
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
                            f"🏆 Pisin streak: {pisin} päivää\n"
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
            uid = str(user.id)
            tehtäväviestit = await hae_tehtäväviestit(uid)

            try:
                with open(TIEDOSTOT.get("Streakit"), encoding="utf-8") as f:
                    streaks = json.load(f)

                daily = streaks.get(uid, {}).get("daily", {}).get("streak", 0)
                weekly = streaks.get(uid, {}).get("weekly", {}).get("streak", 0)
                monthly = streaks.get(uid, {}).get("monthly", {}).get("streak", 0)

                if monthly >= 1:
                    xp_per_task = 150
                elif weekly >= 1:
                    xp_per_task = 100
                elif daily >= 1:
                    xp_per_task = 50
                else:
                    xp_per_task = 50

            except Exception as e:
                xp_per_task = 50
                print("Streak XP-arvio epäonnistui:", e)

            määrä = len(tehtäväviestit)
            tehtävä_xp = määrä * xp_per_task

            try:
                with open(TIEDOSTOT["XP-data"], "r", encoding="utf-8") as f:
                    xp_data = json.load(f)
                tallennettu_xp = xp_data.get(uid, {}).get("xp", 0)
            except Exception as e:
                tallennettu_xp = 0
                embed.add_field(name="⚠️ Virhe", value=f"XP-datan lataus epäonnistui: {e}", inline=False)

            arvio_viesti_xp = max(0, tallennettu_xp - tehtävä_xp)
            tehtävä_prosentti = (tehtävä_xp / tallennettu_xp) * 100 if tallennettu_xp > 0 else 0
            viesti_prosentti = (arvio_viesti_xp / tallennettu_xp) * 100 if tallennettu_xp > 0 else 0

            embed = discord.Embed(
                title="🔢 XP-raportti",
                description=f"Käyttäjän {user.display_name} XP-erittely",
                color=discord.Color.blue()
            )

            embed.add_field(name="🧩 XP-erittely", value=(
                f"📘 Tehtävistä arvioitu: {tehtävä_xp} XP\n"
                f"🔍 Arvio viestipohjaisesta XP:stä: {arvio_viesti_xp} XP\n"
                f"✨ Tallennettu yhteensä: {tallennettu_xp} XP"
            ), inline=False)

            embed.add_field(name="📈 XP-jakauma (%)", value=(
                f"📘 Tehtävät: {tehtävä_prosentti:.1f}%\n"
                f"🔎 Viestit: {viesti_prosentti:.1f}%"
            ), inline=False)

            if tehtävä_xp > tallennettu_xp:
                embed.add_field(name="⚠️ Huomautus", value=(
                    "Tehtävistä arvioitu XP on suurempi kuin tallennettu. Voi viitata tallennusvirheeseen."
                ), inline=False)

    if kategoria == "Moderointi":
        varoituskanava = bot.get_channel(int(os.getenv("MODLOG_CHANNEL_ID")))
        mutekanava = bot.get_channel(int(os.getenv("MUTE_CHANNEL_ID")))
        helpkanava = bot.get_channel(int(os.getenv("HELP_CHANNEL_ID")))

        varoitukset = []
        mute_tiedot = []
        helppyynto = []

        async for msg in varoituskanava.history(limit=1000):
            if f"ID: {user.id}" in msg.content:
                try:
                    syy = msg.content.split("Syy: ")[-1].split(" |")[0]
                    antaja = msg.content.split("Antaja: ")[-1].split("\n")[0]
                    aika = msg.created_at.strftime("%d.%m.%Y %H:%M")
                    varoitukset.append({
                        "syy": syy,
                        "antaja": antaja,
                        "aika": aika
                    })
                except Exception:
                    continue

        async for msg in mutekanava.history(limit=1000):
            if "🔇" in msg.content and "Jäähy" in msg.content:
                try:
                    rivit = msg.content.splitlines()
                    käyttäjä_rivi = next((r for r in rivit if r.startswith("👤")), "")

                    if not any(x in käyttäjä_rivi for x in [user.mention, str(user.id), user.name]):
                        continue

                    tyyppi = "Automaattinen" if "(automaattinen)" in rivit[0] else "Manuaalinen"

                    kesto_rivi = next((r for r in rivit if "⏱" in r), "")
                    if "Kesto:" in kesto_rivi:
                        kesto = kesto_rivi.split("Kesto: ", 1)[-1]
                    elif ": " in kesto_rivi:
                        kesto = kesto_rivi.split(": ", 1)[-1]
                    else:
                        kesto = kesto_rivi.replace("⏱", "").strip()

                    syy_rivi = next((r for r in rivit if "📝" in r), "")
                    if "Syy:" in syy_rivi:
                        syy = syy_rivi.split("Syy: ", 1)[-1]
                    elif ": " in syy_rivi:
                        syy = syy_rivi.split(": ", 1)[-1]
                    else:
                        syy = syy_rivi.replace("📝", "").strip()

                    asettaja_rivi = next((r for r in rivit if "👮" in r), "")
                    if "Asetti:" in asettaja_rivi:
                        asettaja = asettaja_rivi.split("Asetti: ", 1)[-1]
                    elif ": " in asettaja_rivi:
                        asettaja = asettaja_rivi.split(": ", 1)[-1]
                    else:
                        asettaja = asettaja_rivi.replace("👮", "").strip()

                    aika = msg.created_at.strftime("%d.%m.%Y %H:%M")

                    mute_tiedot.append({
                        "kesto": kesto,
                        "syy": syy,
                        "asettaja": asettaja,
                        "aika": aika,
                        "tyyppi": tyyppi,
                    })
                except Exception as e:
                    print(f"Virhe mute-viestissä: {e}")
                    continue

        async for msg in helpkanava.history(limit=500):
            if msg.embeds:
                embed_obj = msg.embeds[0]
                footer = embed_obj.footer.text if embed_obj.footer else ""
                if f"({user.id})" in footer:
                    helppyynto.append(msg)

        embed = discord.Embed(title=f"📋 Käyttäjän {user.name} raportti", color=discord.Color.blue())

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
                    value=(
                        f"🕒 {tiedot['aika']}\n"
                        f"🕓 Kesto: {tiedot['kesto']}\n"
                        f"📝 Syy: {tiedot['syy']}\n"
                        f"👮 Asetti: {tiedot['asettaja']}\n"
                        f"⚙️ Tyyppi: {tiedot['tyyppi']}\n"
                    ),
                    inline=False
                )
        else:
            embed.add_field(name="✅ Ei jäähyjä", value="Käyttäjällä ei ole jäähymerkintöjä.", inline=False)

        if helppyynto:
            helppyynto.sort(key=lambda m: m.created_at, reverse=True)
            embed.add_field(name="🆘 Help-pyynnöt", value=f"Pyyntöjä: {len(helppyynto)}", inline=False)
            for viesti in helppyynto[:2]:
                try:
                    embed_obj = viesti.embeds[0]
                    kentat = embed_obj.fields
                    otsikko = kentat[0].value if len(kentat) > 0 else "💁 Help-pyyntö"
                    kuvaus = kentat[1].value if len(kentat) > 1 else "Ei kuvausta"
                    kuvaus = (kuvaus[:300] + "...") if len(kuvaus) > 300 else kuvaus
                    aika = viesti.created_at.strftime("%d.%m.%Y %H:%M")
                    tila = "❌ Suljettu" if "• Suljettu" in embed_obj.footer.text else "✅ Vastattu"
                    linkki = f"https://discord.com/channels/{viesti.guild.id}/{viesti.channel.id}/{viesti.id}"
                    embed.add_field(
                        name="📥 Pyyntö",
                        value=f"**{otsikko}**\n{kuvaus}\n🕒 {aika}\n📌 Tila: {tila}",
                        inline=False
                    )
                except Exception:
                    continue
        else:
            embed.add_field(name="✅ Ei help-pyyntöjä", value="Käyttäjältä ei löytynyt pyyntöjä.", inline=False)

    elif kategoria == "Komennot":
        await interaction.response.defer(ephemeral=True)

        lataus_embed = discord.Embed(
            title="⏳ Ladataan tietoja...",
            description="• Haetaan komentostatistiikkaa\n• Analysoidaan viestilokit\n\n_Tämä voi kestää hetken..._",
            color=discord.Color.orange()
        )
        msg = await interaction.followup.send(embed=lataus_embed, ephemeral=True)

        embed = discord.Embed(title="📊 Komentostatistiikka", color=discord.Color.blue())

        try:
            log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
            log_channel = bot.get_channel(log_channel_id)
            laskuri = Counter()

            if log_channel:
                async for msg_log in log_channel.history(limit=1000):
                    if f"({user.id})" in msg_log.content:
                        match = re.search(r"Komento: `(.+?)`", msg_log.content)
                        if match:
                            komento = match.group(1)
                            laskuri[komento] += 1

                if laskuri:
                    yhteensä = sum(laskuri.values())
                    rivit = [f"- `{komento}` ({määrä}×)" for komento, määrä in laskuri.most_common(5)]
                    embed.add_field(name="💬 Komentoja käytetty", value=f"{yhteensä} kertaa", inline=True)
                    embed.add_field(name="📌 Käytetyimmät komennot", value="\n".join(rivit), inline=False)
                else:
                    embed.add_field(name="📌 Käytetyimmät komennot", value="Et ole käyttänyt vielä komentoja.", inline=False)
            else:
                embed.add_field(name="📌 Käytetyimmät komennot", value="Lokikanavaa ei löytynyt.", inline=False)

        except Exception as e:
            embed.add_field(name="⚠️ Virhe", value=f"Komentodatan lataus epäonnistui: {e}", inline=False)

        embed.set_footer(text="✅ Lataus valmis • Voit sulkea tämän viestin, kun olet valmis.")
        await msg.edit(embed=embed, view=KategoriaView(user, "Komennot", alkuperäinen_käyttäjä=interaction.user))

    elif kategoria == "Toiminta":
        await interaction.response.defer(ephemeral=True)

        lataus_embed = discord.Embed(
            title="⏳ Ladataan analyysiä...",
            description="• Kerätään viestihistoriaa\n• Lasketaan kanavaaktiivisuus\n• Selvitetään aktiivisin kanava\n\n_Tämä voi kestää hetken...._",
            color=discord.Color.orange()
        )
        msg = await interaction.followup.send(embed=lataus_embed, ephemeral=True)

        try:
            analyysi = JäsenToimintaAnalyysi(user)
            guild = interaction.guild
            if not guild:
                embed = discord.Embed(title="📈 Toiminta-analyysi", color=discord.Color.red())
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
                    embed.add_field(name="💬 Aktiivisin kanava", value=f"{aktiivisin.mention} ({määrä} viestiä)", inline=False)
                else:
                    embed.add_field(name="💬 Aktiivisin kanava", value="Ei lähetettyjä viestejä viimeaikaisesti.", inline=False)

                embed.add_field(name="📊 Analysoitu viestimäärä", value=f"{sum(analyysi.kanavamäärät.values())} viestiä", inline=False)

                try:
                    voice_data_path = Path(os.getenv("XP_VOICE_DATA_FILE"))
                    if voice_data_path.exists():
                        with open(voice_data_path, encoding="utf-8") as f:
                            voice_data = json.load(f)

                        user_id_str = str(user.id)
                        sekunnit = int(voice_data.get("total_voice_usage", {}).get(user_id_str, 0))
                        kesto = str(timedelta(seconds=sekunnit))
                        embed.add_field(name="🎙️ Puhuttu yhteensä", value=f"{kesto}", inline=False)

                        voice_channels = voice_data.get("voice_channels", {}).get(user_id_str, {})
                        if voice_channels:
                            suosituin_id = max(voice_channels, key=voice_channels.get)
                            suosituin_kanava = guild.get_channel(int(suosituin_id))
                            aika = str(timedelta(seconds=voice_channels[suosituin_id]))
                            if suosituin_kanava:
                                embed.add_field(name="📢 Eniten käytetty puhekanava", value=f"{suosituin_kanava.mention} ({aika})", inline=False)
                            else:
                                embed.add_field(name="📢 Eniten käytetty puhekanava", value=f"ID {suosituin_id} ({aika})", inline=False)
                        else:
                            embed.add_field(name="📢 Eniten käytetty puhekanava", value="Ei puhekanavatietoja saatavilla.", inline=False)
                    else:
                        embed.add_field(name="🎙️ Puheaktiivisuus", value="Ei puhedataa saatavilla.", inline=False)
                except Exception as e:
                    embed.add_field(name="⚠️ Virhe puheaktiivisuudessa", value=f"Tietojen lataus epäonnistui: {e}", inline=False)

                embed.set_footer(text="✅ Lataus valmis • Voit sulkea tämän viestin, kun olet valmis.")
                await msg.edit(embed=embed, view=KategoriaView(user, "Toiminta", alkuperäinen_käyttäjä=interaction.user))

        except Exception as e:
            virhe_embed = discord.Embed(title="📈 Toiminta-analyysi", color=discord.Color.red())
            virhe_embed.add_field(name="⚠️ Virhe", value=f"Aktiivisuusdatan lataus epäonnistui: {e}", inline=False)
            await msg.edit(embed=virhe_embed, view=KategoriaView(user, "Toiminta", alkuperäinen_käyttäjä=interaction.user))

    try:
        avaimet = AVAIMET_KATEGORIALLE.get(kategoria)
        if not avaimet:
            polku = TIEDOSTOT.get(kategoria)
            if polku and polku.exists():
                with open(polku, encoding="utf-8") as f:
                    tiedot = json.load(f)
                käyttäjädata = tiedot.get(str(user.id), {})
                if isinstance(käyttäjädata, dict):
                    avaimet = list(käyttäjädata.keys())
    except Exception:
        avaimet = []

    avaimet_str = ", ".join(avaimet) if avaimet else "Ei ladattavia avaimia"

    embed.set_footer(
        text=f"📁 Tiedot päivittyvät reaaliaikaisesti • 🔑 Ladattavissa olevat tiedot: {avaimet_str}"
    )
    return embed

class DataValintaView(ui.View):
    def __init__(self, user, alkuperäinen_käyttäjä=None):
        super().__init__(timeout=None)
        self.user = user
        self.alkuperäinen_käyttäjä = alkuperäinen_käyttäjä or user
        for nimi in KATEGORIAT:
            self.add_item(KategoriaNappi(nimi, user=self.user, alkuperäinen_käyttäjä=self.alkuperäinen_käyttäjä))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.alkuperäinen_käyttäjä.id

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
    def __init__(self, nimi, user, alkuperäinen_käyttäjä):
        super().__init__(label=nimi, style=discord.ButtonStyle.primary)
        self.nimi = nimi
        self.user = user
        self.alkuperäinen_käyttäjä = alkuperäinen_käyttäjä
        self.bot = bot

    async def callback(self, interaction):
        try:
            embed = await muodosta_kategoria_embed(self.nimi, self.user, self.bot, interaction)
            await interaction.response.edit_message(
                content=f"📁 Kategoria: {self.nimi}",
                embed=embed,
                view=KategoriaView(self.user, self.nimi, alkuperäinen_käyttäjä=self.alkuperäinen_käyttäjä)
            )
        except Exception as e:
            print(f"Embedin luonti epäonnistui: {e}")
            await interaction.response.send_message("❌ Virhe näkymän avaamisessa.", ephemeral=True)

AVAIMET_KATEGORIALLE = {
    "XP-data": ["xp", "level"],
    "XP-streakit": ["streak", "pvm"],
    "Streakit": ["streak"],
    "Puhe-streak": ["streak", "pvm", "pisin"],  
}

class KategoriaView(ui.View):
    def __init__(self, user, valittu=None, alkuperäinen_käyttäjä=None):
        super().__init__(timeout=None)
        self.user = user
        self.kategoria = valittu
        self.alkuperäinen_käyttäjä = alkuperäinen_käyttäjä or user

        if not valittu:
            for nimi in KATEGORIAT:
                self.add_item(KategoriaNappi(nimi, user, alkuperäinen_käyttäjä=self.alkuperäinen_käyttäjä))
        else:
            self.add_item(PalaaNappi(user))
            self.add_item(LataaNappi(valittu, user, AVAIMET_KATEGORIALLE.get(valittu, [])))

            if valittu != "Moderointi":
                self.add_item(PoistaNappi(valittu, user, AVAIMET_KATEGORIALLE.get(valittu, [])))
            else:
                self.add_item(IlmoitaPoistopyyntöNappi(valittu, user, AVAIMET_KATEGORIALLE.get(valittu, [])))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in {self.user.id, self.alkuperäinen_käyttäjä.id}

class KatsoNappi(ui.Button):
    def __init__(self, user):
        super().__init__(label="Katso tiedot", style=discord.ButtonStyle.secondary)
        self.user = user

    async def callback(self, interaction):
        try:
            await interaction.response.edit_message(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None, alkuperäinen_käyttäjä=interaction.user)
            )
        except discord.NotFound:
            print("⚠️ Interaktio vanhentunut — käytetään followup.send")
            await interaction.followup.send(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None, alkuperäinen_käyttäjä=interaction.user),
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
                view=KategoriaView(self.user, None, alkuperäinen_käyttäjä=interaction.user)
            )
        except discord.NotFound:
            print("⚠️ Interaktio vanhentunut — käytetään followup.send")
            await interaction.followup.send(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(self.user, None, alkuperäinen_käyttäjä=interaction.user),
                ephemeral=True
            )
        except Exception as e:
            print(f"PalaaNappi virhe: {e}")
            await interaction.response.send_message("❌ Virhe näkymän avaamisessa.", ephemeral=True)

class LataaNappi(ui.Button):
    def __init__(self, nimi, user, avaimet=None):
        super().__init__(label="Lataa tiedot", style=discord.ButtonStyle.success)
        self.nimi = nimi
        self.user = user
        self.avaimet = avaimet or []

    async def callback(self, interaction: discord.Interaction):
        path = TIEDOSTOT.get(self.nimi)
        if not path or not path.exists():
            await interaction.response.send_message("❌ Tiedostoa ei löytynyt.", ephemeral=True)
            return

        try:
            with open(path, encoding="utf-8") as f:
                raw_data = f.read()

            tiedostonimi = f"{self.nimi}_{self.user.id}.txt"
            kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
            if not kanava:
                await interaction.response.send_message("⚠️ Ilmoituskanavaa ei löytynyt.", ephemeral=True)
                return

            await lähetä_lataus_lokiviesti(
                kanava=kanava,
                pyytäjä=interaction.user,
                käyttäjä=self.user,
                nimi=self.nimi,
                avaimet=self.avaimet,
                tekstitiedosto=raw_data,
                tiedostonimi=tiedostonimi
            )

            await interaction.response.send_message("✅ Latauspyyntö lähetetty moderaattoreille vahvistusta varten.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ Lataus epäonnistui: {e}", ephemeral=True)

class PoistaNappi(ui.Button):
    def __init__(self, nimi, user, avaimet: list[str] = None):
        super().__init__(label="Poista tiedot", style=discord.ButtonStyle.danger)
        self.nimi = nimi
        self.user = user

        if not avaimet:
            polku = TIEDOSTOT.get(nimi)
            if polku and polku.exists():
                try:
                    with open(polku, encoding="utf-8") as f:
                        data = json.load(f)
                    käyttäjädata = data.get(str(user.id), {})
                    if isinstance(käyttäjädata, dict):
                        self.avaimet = list(käyttäjädata.keys())
                    else:
                        self.avaimet = []
                except Exception:
                    self.avaimet = []
            else:
                self.avaimet = []
        else:
            self.avaimet = avaimet

    async def callback(self, interaction: discord.Interaction):
        kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
        if not kanava:
            await interaction.response.send_message("⚠️ Ilmoituskanavaa ei löytynyt.", ephemeral=True)
            return

        await lähetä_poisto_lokiviesti(
            kanava=kanava,
            poistaja=interaction.user,
            käyttäjä=self.user,
            nimi=self.nimi,
            avaimet=self.avaimet
        )
        await interaction.response.send_message("✅ Poistopyyntö lähetetty moderaattoreille vahvistusta varten.", ephemeral=True)

class IlmoitaPoistopyyntöNappi(ui.Button):
    def __init__(self, nimi, user, avaimet: list[str] = None):
        super().__init__(label="Ilmoita virhe / poisto", style=discord.ButtonStyle.danger)
        self.nimi = nimi
        self.user = user
        self.avaimet = avaimet or []

    async def callback(self, interaction: discord.Interaction):
        kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
        if kanava:
            await kanava.send(
                f"🗑️ **Poistopyyntö / Virheilmoitus**\n"
                f"📁 Kategoria: {self.nimi}\n"
                f"👤 Käyttäjä: {self.user.mention} ({self.user.id})\n"
                f"🗂️ Avaimet: {', '.join(self.avaimet) if self.avaimet else 'Kaikki'}\n"
                f"👮 Ilmoittaja: {interaction.user.mention} ({interaction.user.id})\n"
                f"🕒 Aika: <t:{int(discord.utils.utcnow().timestamp())}:F>"
            )
            await interaction.response.send_message(
                "✅ Ilmoitus moderaattoreille lähetetty. He tarkistavat ja käsittelevät asian.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("⚠️ Ilmoituskanavaa ei löytynyt.", ephemeral=True)

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

async def logita_poisto(poistaja: discord.User, kohde: str, käyttäjä: discord.User, avaimet: list[str]):
    kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if kanava:
        await kanava.send(
            f"🗑️ **Poistopyyntö:** `{kohde}`\n"
            f"👤 Kohdekäyttäjä: {käyttäjä.mention} ({käyttäjä.id})\n"
            f"🔑 Avaimet: {', '.join(avaimet) if avaimet else 'Kaikki tiedot'}\n"
            f"👮 Pyyntö tehty: {poistaja.mention} ({poistaja.id})\n"
            f"🕒 Aika: <t:{int(discord.utils.utcnow().timestamp())}:F>\n"
            f"⚠️ Poisto on suoritettava manuaalisesti tarkistuksen jälkeen."
        )

async def logita_lataus(pyytäjä: discord.User, kohde: str, käyttäjä: discord.User, avaimet: list[str]):
    kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if kanava:
        await kanava.send(
            f"📥 **Latauspyyntö:** `{kohde}`\n"
            f"👤 Kohdekäyttäjä: {käyttäjä.mention} ({käyttäjä.id})\n"
            f"🔑 Avaimet: {', '.join(avaimet) if avaimet else 'Kaikki tiedot'}\n"
            f"📨 Pyytäjä: {pyytäjä.mention} ({pyytäjä.id})\n"
            f"🕒 Aika: <t:{int(discord.utils.utcnow().timestamp())}:F>\n"
            f"📎 Tiedosto toimitetaan yksityisviestillä."
        )

async def lähetä_vahvistus_dm(käyttäjä: discord.User, tiedostonimi: str, tekstitiedosto: str, otsikko: str):
    try:
        buffer = BytesIO(tekstitiedosto.encode("utf-8"))
        await käyttäjä.send(
            content=(
                f"✅ **{otsikko}**\n"
                f"Tarkista liitteenä oleva tiedosto.\n"
                f"Ota yhteyttä ylläpitoon, jos jokin ei täsmää."
            ),
            file=discord.File(buffer, filename=tiedostonimi)
        )
    except discord.Forbidden:
        print(f"Käyttäjälle {käyttäjä.id} ei voitu lähettää DM:ää.")

pending_file_sends: dict[int, dict] = {}

class VahvistaLähetysNappi(ui.Button):
    def __init__(self, käyttäjä: discord.User, tekstitiedosto: str, tiedostonimi: str, otsikko: str):
        super().__init__(label="📎 Liitä tiedosto lähetettäväksi", style=discord.ButtonStyle.primary)
        self.käyttäjä = käyttäjä
        self.tekstitiedosto = tekstitiedosto
        self.tiedostonimi = tiedostonimi
        self.otsikko = otsikko

    async def callback(self, interaction: discord.Interaction):
        if not any(role.name == "Mestari" for role in interaction.user.roles):
            await interaction.response.send_message("❌ Sinulla ei ole oikeuksia käyttää tätä toimintoa.", ephemeral=True)
            return

        pending_file_sends[interaction.user.id] = {
            "kohde": self.käyttäjä,
            "otsikko": self.otsikko,
            "timestamp": datetime.utcnow()
        }

        await interaction.response.send_message(
            "📎 Liitä nyt haluamasi tiedosto tähän ketjuun vastauksena tai erillisenä viestinä.",
            ephemeral=True
        )

        self.disabled = True
        self.label = "✅ Tiedosto pyyntö lähetetty"
        self.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message("✅ Tiedosto pyyntö lähetetty ja ilmoitettu käyttäjälle.", ephemeral=True)

class VahvistaPoistoNappi(ui.Button):
    def __init__(self, käyttäjä: discord.User, tiedostonimi: str):
        super().__init__(label="🗑️ Vahvista poisto", style=discord.ButtonStyle.danger)
        self.käyttäjä = käyttäjä
        self.tiedostonimi = tiedostonimi

    async def callback(self, interaction: discord.Interaction):
        if not any(role.name == "Mestari" for role in interaction.user.roles):
            await interaction.response.send_message("❌ Sinulla ei ole oikeuksia käyttää tätä toimintoa.", ephemeral=True)
            return

        try:
            await self.käyttäjä.send(
                f"🗑️ Tietosi tiedostosta `{self.tiedostonimi}` on nyt poistettu pysyvästi.\n"
                f"Jos sinulla on kysyttävää, ole yhteydessä ylläpitoon."
            )
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Käyttäjälle ei voitu lähettää DM:ää.", ephemeral=True)

        self.disabled = True
        self.label = "✅ Poisto suoritettu"
        self.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message("✅ Poisto vahvistettu ja ilmoitettu käyttäjälle.", ephemeral=True)

class HylkääPyyntöNappi(ui.Button):
    def __init__(self, käyttäjä: discord.User, syy: str = "Ei syytä annettu"):
        super().__init__(label="❌ Hylkää pyyntö", style=discord.ButtonStyle.danger)
        self.käyttäjä = käyttäjä
        self.syy = syy

    async def callback(self, interaction: discord.Interaction):
        if not any(role.name == "Mestari" for role in interaction.user.roles):
            await interaction.response.send_message("❌ Sinulla ei ole oikeuksia käyttää tätä toimintoa.", ephemeral=True)
            return

        try:
            await self.käyttäjä.send(
                f"❌ Pyyntösi on hylätty.\nSyy: {self.syy}\nJos koet tämän virheelliseksi, ota yhteyttä ylläpitoon."
            )
        except discord.Forbidden:
            print(f"DM epäonnistui käyttäjälle {self.käyttäjä.id}")

        self.disabled = True
        self.label = "❌ Hylätty"
        self.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message("✅ Pyyntö hylätty ja ilmoitettu käyttäjälle.", ephemeral=True)

async def lähetä_lataus_lokiviesti(kanava, pyytäjä, käyttäjä, nimi, avaimet, tekstitiedosto, tiedostonimi):
    view = ui.View()
    view.add_item(VahvistaLähetysNappi(käyttäjä, tekstitiedosto, tiedostonimi, f"Latauspyyntö tiedostolle `{nimi}`"))
    view.add_item(HylkääPyyntöNappi(käyttäjä, syy="Moderaattorin harkinnan mukaan"))

    await kanava.send(
        content=(
            f"📥 **Latauspyyntö** `{nimi}`\n"
            f"👤 Kohdekäyttäjä: {käyttäjä.mention}\n"
            f"📨 Pyytäjä: {pyytäjä.mention}\n"
            f"🔑 Avaimet: {', '.join(avaimet)}\n"
            f"⚠️ Vahvista ennen kuin tiedosto lähetetään jäsenelle."
        ),
        view=view
    )

async def lähetä_poisto_lokiviesti(kanava, poistaja, käyttäjä, nimi, avaimet):
    view = ui.View()
    view.add_item(VahvistaPoistoNappi(käyttäjä, nimi))
    view.add_item(HylkääPyyntöNappi(käyttäjä, syy="Moderaattorin harkinnan mukaan"))

    await kanava.send(
        content=(
            f"🗑️ **Poistopyyntö** `{nimi}`\n"
            f"👤 Kohdekäyttäjä: {käyttäjä.mention}\n"
            f"👮 Poistaja: {poistaja.mention}\n"
            f"🔑 Avaimet: {', '.join(avaimet)}\n"
            f"⚠️ Vahvista ennen kuin poistoilmoitus lähetetään jäsenelle."
        ),
        view=view
    )