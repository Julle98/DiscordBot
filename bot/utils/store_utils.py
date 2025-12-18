import discord
import asyncio
import os
import json
import random
from datetime import datetime, timedelta, timezone
from discord.ui import Modal, Select
from discord.ui import Modal, TextInput
from dotenv import load_dotenv
from discord.ui import Button, View
from discord.ext import tasks, commands
from bot.utils.bot_setup import bot
from bot.utils.xp_utils import load_xp_data
from pathlib import Path
from datetime import datetime
import os
import json
from pathlib import Path
from typing import Optional
import discord

def start_store_loops():
    if not tarkista_ostojen_kuukausi.is_running():
        tarkista_ostojen_kuukausi.start()
    if not paivita_tarjous_automatisoitu.is_running():
        paivita_tarjous_automatisoitu.start()
    if not tarkista_vanhentuneet_oikeudet.is_running():
        tarkista_vanhentuneet_oikeudet.start()
    if not paivita_valikoima.is_running():
        paivita_valikoima.start()

load_dotenv()
OSTOSLOKI_KANAVA_ID = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))
JSON_DIRS = Path(os.getenv("JSON_DIRS"))
SHOP_CAMPAIGN_PATH = os.getenv("SHOP_CAMPAIGN_PATH")
tuotteet_polku = JSON_DIRS / "tuotteet.json"
VALIKOIMA_POLKU = JSON_DIRS / "valikoima.json"

auto_react_users = {}  # user_id -> emoji

kauppa_tuotteet = [
    {"nimi": "Erikoisemoji", "kuvaus": "Käytä erikoisemojeita 3 päiväksi", "hinta": 1000, "kertakäyttöinen": True, "emoji": "😎"},
    {"nimi": "Double XP -päivä", "kuvaus": "Saat tuplat XP:t 24h ajan", "hinta": 2000, "kertakäyttöinen": True, "emoji": "⚡", "tarjousprosentti": 50},
    {"nimi": "Custom rooli", "kuvaus": "Saat oman roolin", "hinta": 5000, "kertakäyttöinen": True, "emoji": "🎨", "tarjousprosentti": 20},
    {"nimi": "VIP-chat", "kuvaus": "Pääsy VIP-kanavalle viikoksi", "hinta": 3000, "kertakäyttöinen": False, "emoji": "💎", "tarjousprosentti": 10},
    {"nimi": "VIP-rooli", "kuvaus": "Saat VIP-roolin viikoksi", "hinta": 2500, "kertakäyttöinen": True, "emoji": "👑", "tarjousprosentti": 10},
    {"nimi": "Oma komento", "kuvaus": "Saat tehdä oman idean /komennon", "hinta": 6000, "kertakäyttöinen": True, "emoji": "🛠️", "tarjousprosentti": 25},
    {"nimi": "Oma kanava", "kuvaus": "Saat oman tekstikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "📢", "tarjousprosentti": 25},
    {"nimi": "Oma puhekanava", "kuvaus": "Saat oman äänikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "🎙️", "tarjousprosentti": 25},
    {"nimi": "Valitse värisi", "kuvaus": "Saat värillisen roolin (esim. sininen) 7 päiväksi", "hinta": 1500, "kertakäyttöinen": False, "emoji": "🧬", "tarjousprosentti": 30},
    {"nimi": "Valitse emoji", "kuvaus": "Bot reagoi viesteihisi valitsemallasi emojilla 7 päivän ajan", "hinta": 3500, "kertakäyttöinen": True, "emoji": "🤖", "tarjousprosentti": 30},
    {"nimi": "Soundboard-oikeus", "kuvaus": "Käyttöoikeus puhekanavan soundboardiin 3 päiväksi", "hinta": 4000, "kertakäyttöinen": True, "emoji": "🔊", "tarjousprosentti": 10},
    {"nimi": "Streak palautus", "kuvaus": "Palauttaa valitsemasi streakin aiempaan pisin-arvoon.", "hinta": 3000, "kertakäyttöinen": True, "emoji": "♻️", "tarjousprosentti": 20},
    {"nimi": "Tehtävien armonantamisen nollaus", "kuvaus": "Poistaa armolliset jatkoviestit tehtävälogista", "hinta": 2500, "kertakäyttöinen": True, "emoji": "🧼", "tarjousprosentti": 20}
]

def puhdista_tuotteen_nimi(nimi: str) -> str:
    return nimi.replace(" (Tarjous!)", "").strip().lower()

TUOTELOGIIKKA = {
    puhdista_tuotteen_nimi("Erikoisemoji"): {"rooli": "Erikoisemoji", "kesto": timedelta(days=3)},
    puhdista_tuotteen_nimi("Double XP -päivä"): {"rooli": "Double XP", "kesto": timedelta(days=1)},
    puhdista_tuotteen_nimi("Custom rooli"): {"rooli": None, "kesto": None},
    puhdista_tuotteen_nimi("VIP-chat"): {"rooli": "VIP", "kesto": timedelta(days=7)},
    puhdista_tuotteen_nimi("VIP-rooli"): {"rooli": "VIPRooli", "kesto": timedelta(days=7)},
    puhdista_tuotteen_nimi("Oma komento"): {"rooli": None, "kesto": None},
    puhdista_tuotteen_nimi("Oma kanava"): {"rooli": None, "kesto": None},
    puhdista_tuotteen_nimi("Oma puhekanava"): {"rooli": None, "kesto": None},
    puhdista_tuotteen_nimi("Valitse värisi"): {"rooli": None, "kesto": timedelta(days=7)},
    puhdista_tuotteen_nimi("Valitse emoji"): {"rooli": None, "kesto": timedelta(days=7)},
    puhdista_tuotteen_nimi("Soundboard-oikeus"): {"rooli": "SoundboardAccess", "kesto": timedelta(days=3)},
    puhdista_tuotteen_nimi("Streak palautus"): {"rooli": None, "kesto": None},
    puhdista_tuotteen_nimi("Tehtävien armonantamisen nollaus"): {"rooli": None, "kesto": None},
}

if not tuotteet_polku.exists():
    with open(tuotteet_polku, "w", encoding="utf-8") as f:
        json.dump(kauppa_tuotteet, f, ensure_ascii=False, indent=2)
    print("✅ tuotteet.json luotu.")
else:
    print("ℹ️ tuotteet.json on jo olemassa. Ei ylikirjoitettu.")

from discord.ext import tasks

@tasks.loop(hours=1)
async def tarkista_ostojen_kuukausi():
    try:
        ostot = lue_ostokset()

        kaikki_paivamaarat = []
        for ostot_lista in ostot.values():
            for ostos in ostot_lista:
                if "pvm" in ostos:
                    try:
                        pvm = datetime.fromisoformat(ostos["pvm"])
                        if pvm.tzinfo is None:
                            pvm = pvm.replace(tzinfo=timezone.utc)
                        kaikki_paivamaarat.append(pvm)
                    except Exception:
                        continue

        if not kaikki_paivamaarat:
            return  

        nyt = datetime.now(timezone.utc)
        viimeisin = max(kaikki_paivamaarat)

        if viimeisin.month != nyt.month:
            print("Tyhjennetään ostot (uusi kuukausi)")
            tallenna_ostokset({})
    except Exception as e:
        print(f"Ostojen tarkistus epäonnistui: {e}")

from datetime import datetime, timezone

@tasks.loop(hours=1)
async def tarkista_vanhentuneet_oikeudet():
    ostot = lue_ostokset()
    nyt = datetime.now(timezone.utc)  

    for user_id, ostoslista in ostot.items():
        guild = bot.guilds[0]
        member = guild.get_member(int(user_id))
        if not member:
            continue

        for ostos in ostoslista:
            try:
                pvm_str = ostos.get("pvm", "")
                pvm = datetime.fromisoformat(pvm_str)

                if pvm.tzinfo is None:
                    pvm = pvm.replace(tzinfo=timezone.utc)

                nimi = ostos.get("nimi", "")

                for avain, tiedot in TUOTELOGIIKKA.items():
                    if avain.lower() in nimi.lower():
                        kesto = tiedot.get("kesto")
                        if not kesto:
                            continue

                        if (nyt - pvm) > kesto:
                            rooli = discord.utils.get(guild.roles, name=tiedot["rooli"])
                            if rooli and rooli in member.roles:
                                await member.remove_roles(rooli)
                                print(f"🧹 Poistettu rooli {rooli.name} käyttäjältä {member.name}")
                                try:
                                    await member.send(
                                        f"⌛ Oikeutesi **{rooli.name}** on vanhentunut.\n"
                                        f"🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉"
                                    )
                                except discord.Forbidden:
                                    print(f"❌ DM-viesti epäonnistui käyttäjälle {member.name}")
            except Exception as e:
                print(f"⚠️ Virhe roolin poistossa: {e}")

    for user_id, emoji in list(auto_react_users.items()):
        member = guild.get_member(int(user_id))
        if not member:
            continue

        emoji_ostot = ostot.get(str(user_id), [])
        for ostos in emoji_ostot:
            if "valitse emoji" in ostos.get("nimi", "").lower():
                pvm = datetime.fromisoformat(ostos.get("pvm", ""))
                if (nyt - pvm) > timedelta(days=7):
                    auto_react_users.pop(user_id, None)
                    print(f"🧹 Poistettu emoji-oikeus käyttäjältä {member.name}")
                    try:
                        await member.send(
                            f"⌛ Emoji-oikeutesi ({emoji}) on päättynyt.\n"
                            f"🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉"
                        )
                    except discord.Forbidden:
                        print(f"❌ DM-viesti epäonnistui käyttäjälle {member.name}")

@tasks.loop(hours=1)
async def paivita_valikoima():
    try:
        periodi = nykyinen_periodi()
        tuotteet = kauppa_tuotteet[periodi*2:(periodi+1)*2]
        with open(VALIKOIMA_POLKU, "w", encoding="utf-8") as f:
            json.dump(tuotteet, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Valikoiman automaattinen päivitys epäonnistui: {e}")

@tasks.loop(hours=1)
async def paivita_tarjous_automatisoitu():
    try:
        nykyinen = nykyinen_periodi()
        try:
            with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
                data = json.load(f)
                edellinen = data.get("periodi")
                if edellinen == nykyinen:
                    return  
        except:
            pass

        hae_tai_paivita_tarjous()
        print("✅ Tarjous päivitetty automaattisesti.")
    except Exception as e:
        print(f"Tarjouksen automaattinen päivitys epäonnistui: {e}")

JSON_DIR = Path(os.getenv("JSON_DIRS"))
TARJOUS_TIEDOSTO = JSON_DIR / "tarjous.json"

def hae_tai_paivita_tarjous():
    periodi = nykyinen_periodi()

    try:
        with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
            data = json.load(f)
            edellinen_periodi = data.get("periodi")

            if edellinen_periodi == periodi:
                tuote = data.get("tuote")
                if isinstance(tuote, dict):
                    return [tuote]
                elif isinstance(tuote, list) and all(isinstance(t, dict) for t in tuote):
                    return tuote
                else:
                    return []
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        pass

    normaalit = kauppa_tuotteet[periodi * 2:(periodi + 1) * 2]
    valittavat = [t for t in kauppa_tuotteet if t.get("tarjousprosentti") and t not in normaalit]

    if not valittavat:
        return []

    valittu = random.choice(valittavat)
    alennettu_hinta = max(100, int(valittu["hinta"] * (1 - valittu["tarjousprosentti"] / 100)))

    tarjous = {
        "nimi": f"{valittu['nimi']} (Tarjous!)",
        "kuvaus": f"{valittu['kuvaus']} – nyt {valittu['tarjousprosentti']}% alennuksessa!",
        "hinta": alennettu_hinta,
        "kertakäyttöinen": valittu["kertakäyttöinen"],
        "emoji": valittu.get("emoji", "🔥"),
        "tarjous": True
    }

    with open(TARJOUS_TIEDOSTO, "w", encoding="utf-8") as f:
        json.dump({
            "paivamaara": datetime.now(timezone.utc).isoformat(),
            "periodi": periodi,
            "tuote": tarjous
        }, f, ensure_ascii=False, indent=2)

    return [tarjous]

def hae_tarjous_vain():
    try:
        with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
            data = json.load(f)
            tuote = data.get("tuote")
            if isinstance(tuote, dict):
                return [tuote]
            elif isinstance(tuote, list) and all(isinstance(t, dict) for t in tuote):
                return tuote
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return []

def tarkista_kuponki(koodi: str, tuotteen_nimi: str, user_id: str, interaction: discord.Interaction) -> int:
    polku = Path(os.getenv("JSON_DIRS")) / "kuponki.json"
    tuotteen_nimi = tuotteen_nimi.strip().lower()
    koodi = koodi.strip().upper()

    try:
        with open(polku, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Kuponkidatan lataus epäonnistui: {e}")
        return 0

    kuponki = data.get(koodi)
    if not kuponki:
        print(f"❌ Kuponkia {koodi} ei löytynyt.")
        return 0

    try:
        vanhentuu = datetime.fromisoformat(kuponki["vanhentuu"])
        if datetime.now() > vanhentuu:
            print(f"⏰ Kuponki {koodi} on vanhentunut.")
            return 0
    except Exception as e:
        print(f"❌ Vanhentumispäivän käsittely epäonnistui: {e}")
        return 0

    if kuponki.get("maxkayttoja", -1) != -1 and kuponki.get("kayttoja", 0) >= kuponki["maxkayttoja"]:
        print(f"🚫 Kuponki {koodi} on käytetty maksimimäärän verran.")
        return 0

    sallitut_tuotteet = [t.strip().lower() for t in kuponki.get("tuotteet", [])]
    if sallitut_tuotteet and tuotteen_nimi not in sallitut_tuotteet:
        print(f"🚫 Tuote '{tuotteen_nimi}' ei ole sallittu kupongille {koodi}.")
        return 0

    sallitut_kayttajat_raw = kuponki.get("kayttajat", [])
    if sallitut_kayttajat_raw:
        kayttaja_ids = [v for v in sallitut_kayttajat_raw if not v.startswith("rooli:")]
        rooli_ids = [v.replace("rooli:", "") for v in sallitut_kayttajat_raw if v.startswith("rooli:")]

        member = interaction.guild.get_member(interaction.user.id)
        kuuluu_rooliin = member and any(discord.utils.get(member.roles, id=int(rid)) for rid in rooli_ids)
        on_hyvaksytty_kayttaja = str(user_id) in kayttaja_ids

        if not on_hyvaksytty_kayttaja and not kuuluu_rooliin:
            print(f"🚫 Käyttäjä {user_id} ei ole sallittu kupongille {koodi}.")
            return 0

    kayttaja_key = str(user_id)  
    kayttaja_kayttoja = kuponki.setdefault("kayttajat_dict", {}).get(kayttaja_key, 0)

    if kuponki.get("maxkayttoja_per_jasen", -1) != -1 and kayttaja_kayttoja >= kuponki["maxkayttoja_per_jasen"]:
        print(f"🚫 Käyttäjä {user_id} on käyttänyt kupongin {koodi} jo maksimimäärän verran.")
        return 0

    kuponki["kayttoja"] = kuponki.get("kayttoja", 0) + 1
    kuponki["kayttajat_dict"][kayttaja_key] = kayttaja_kayttoja + 1
    data[koodi] = kuponki

    try:
        with open(polku, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Kuponkidatan tallennus epäonnistui: {e}")

    print(f"✅ Kuponki {koodi} hyväksytty. Alennus: {kuponki.get('prosentti', 0)}%")
    return kuponki.get("prosentti", 0)

def hae_campaign():
    try:
        with open(SHOP_CAMPAIGN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def _parse_iso(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def onko_tuote_voimassa(user_id: str, tuotteen_nimi: str) -> Optional[timedelta]:
    ostot = lue_ostokset()
    kayttajan_ostot = ostot.get(user_id, [])
    nyt = datetime.now(timezone.utc)
    kohde = puhdista_tuotteen_nimi(tuotteen_nimi)

    voimassa_jaljella = None
    for o in kayttajan_ostot:
        if puhdista_tuotteen_nimi(o.get("nimi", "")) != kohde:
            continue
        exp = _parse_iso(o.get("expires_at", ""))
        if not exp and o.get("pvm"):  
            canon = TUOTELOGIIKKA.get(kohde)
            if canon and canon.get("kesto"):
                exp = datetime.fromisoformat(o["pvm"]) + canon["kesto"]
        if exp and exp > nyt:
            diff = exp - nyt
            if not voimassa_jaljella or diff > voimassa_jaljella:
                voimassa_jaljella = diff

    return voimassa_jaljella

def voiko_ostaa(user_id: str, tuote_nimi: str) -> tuple[bool, Optional[datetime]]:
    ostot = lue_ostokset()
    canon = puhdista_tuotteen_nimi(tuote_nimi)
    nyt = datetime.now(timezone.utc)

    for o in ostot.get(user_id, []):
        if puhdista_tuotteen_nimi(o.get("nimi", "")) == canon:
            exp = _parse_iso(o.get("expires_at"))
            if exp and exp > nyt:
                return False, exp
            if not exp:
                return False, None
    return True, None

async def onko_modal_kaytetty(bot, user: discord.User, modal_nimi: str) -> bool:
    log_channel = bot.get_channel(int(os.getenv("MOD_LOG_CHANNEL_ID")))
    if not log_channel:
        return False

    async for msg in log_channel.history(limit=100):
        if msg.embeds:
            embed = msg.embeds[0]
            if embed.footer.text == f"ID: {user.id}" and modal_nimi in embed.title:
                return True
    return False

async def kirjaa_modal_kaytto(bot, user: discord.User, modal_nimi: str, lisatieto: Optional[str] = None):
    log_channel = bot.get_channel(int(os.getenv("MOD_LOG_CHANNEL_ID")))
    if not log_channel:
        return

    embed = discord.Embed(
        title=f"🔐 {modal_nimi} käytetty",
        description=f"**Käyttäjä:** {user.mention}\n**ID:** {user.id}" +
                    (f"\n**Lisätieto:** {lisatieto}" if lisatieto else ""),
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"ID: {user.id}")
    await log_channel.send(embed=embed)

class StreakPalautusModal(discord.ui.Modal, title="Valitse streak palautettavaksi"):
    def __init__(self):
        super().__init__()
        self.streak_input = discord.ui.TextInput(
            label="Streakin tyyppi",
            placeholder="daily / weekly / monthly",
            required=True,
            max_length=20
        )
        self.add_item(self.streak_input)

    async def on_submit(self, interaction: discord.Interaction):
        from bot.utils.tasks_utils import load_streaks, save_streaks

        uid = str(interaction.user.id)
        valinta = self.streak_input.value.lower()
        sallitut_tyypit = {"daily", "weekly", "monthly"}

        if valinta not in sallitut_tyypit:
            await interaction.response.send_message("❌ Anna jokin seuraavista: daily, weekly tai monthly.", ephemeral=True)
            return

        streaks = load_streaks()
        if uid not in streaks or valinta not in streaks[uid]:
            await interaction.response.send_message("❌ Tälle streakille ei löytynyt dataa.", ephemeral=True)
            return

        data = streaks[uid][valinta]
        if data.get("streak", 0) < data.get("max_streak", 0):
            data["streak"] = data["max_streak"]
            save_streaks(streaks)

            if hasattr(self, "kirjaa_kaytto"):
                self.kirjaa_kaytto(valinta)

            embed = discord.Embed(
                title="♻️ Streak palautettu!",
                description=f"**{valinta.capitalize()}** streak on nyt arvoissa {data['max_streak']} 🔥",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Streak on jo ennätyksessä, ei palautettavaa.", ephemeral=True)

class ModalDropdown(discord.ui.Select):
    def __init__(self, modal: discord.ui.Modal, otsikko: str):
        options = [
            discord.SelectOption(label=otsikko, description="Avaa lisäasetukset")
        ]
        super().__init__(placeholder="Valitse toiminto...", min_values=1, max_values=1, options=options)
        self.modal = modal

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.modal)

class ModalDropdownView(discord.ui.View):
    def __init__(self, modal: discord.ui.Modal, otsikko: str):
        super().__init__(timeout=None)
        self.add_item(ModalDropdown(modal, otsikko))

def nykyinen_periodi():
    nyt = datetime.now(timezone.utc)
    alku = datetime(nyt.year, nyt.month, 1, tzinfo=timezone.utc)  
    delta = nyt - alku
    periodi = (delta.days // 4) % (len(kauppa_tuotteet) // 2)
    return periodi

def nayta_kauppa_embed(interaction: discord.Interaction, tarjoukset: list, tuotteet: list):
    user_id = str(interaction.user.id)
    campaign = hae_campaign()
    now = datetime.now(timezone.utc).date()

    xp_data = load_xp_data()
    user_xp = xp_data.get(user_id, {}).get("xp", 0)

    ostot = lue_ostokset()
    omistetut = ostot.get(user_id, [])
    omistetut_nimet = [puhdista_tuotteen_nimi(o["nimi"]) for o in omistetut if isinstance(o, dict) and "nimi" in o]

    embed = discord.Embed(
        title="🛒 Sannamaija Shop!",
        description=f"Tässä ovat tämänhetkiset tuotteet:\n**Sinulla on {user_xp} XP:tä käytettävissä** ✨",
        color=discord.Color.gold()
    )

    if campaign and campaign.get("active"):
        alku = datetime.fromisoformat(campaign["alku"]).date()
        loppu = datetime.fromisoformat(campaign["loppu"]).date()
        if alku <= now <= loppu:
            embed.add_field(
                name=campaign["title"],
                value=f"{campaign['banner']}\nVoimassa {alku.strftime('%d.%m.%Y')} - {loppu.strftime('%d.%m.%Y')}",
                inline=False
            )

    kertakayttoiset = [t for t in tuotteet if t.get("kertakäyttöinen")]
    if kertakayttoiset:
        embed.add_field(name="🔁 Kertakäyttöiset tuotteet", value="\u200b", inline=False)
        for t in kertakayttoiset:
            emoji = t.get("emoji", "🛍️")
            omistaa = "✅ Omistat" if puhdista_tuotteen_nimi(t["nimi"]) in omistetut_nimet else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n{omistaa}",
                inline=False
            )

    monikayttoiset = [t for t in tuotteet if not t.get("kertakäyttöinen")]
    if monikayttoiset:
        embed.add_field(name="♻️ Monikäyttöiset tuotteet", value="\u200b", inline=False)
        for t in monikayttoiset:
            emoji = t.get("emoji", "🎁")
            omistaa = "✅ Omistat" if puhdista_tuotteen_nimi(t["nimi"]) in omistetut_nimet else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n{omistaa}",
                inline=False
            )

    if tarjoukset:
        embed.add_field(name="━━━━━━━━━━━━━━", value="\u200b", inline=False)
        embed.add_field(name="🎉 Tarjoukset", value="\u200b", inline=False)
        for t in tarjoukset:
            emoji = t.get("emoji", "🔥")
            tyyppi = "Kertakäyttöinen" if t.get("kertakäyttöinen") else "Monikäyttöinen"
            omistaa = "✅ Omistat" if puhdista_tuotteen_nimi(t["nimi"]) in omistetut_nimet else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n*Tyyppi: {tyyppi}* {omistaa}",
                inline=False
            )

    nyt = datetime.now(timezone.utc)
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    seuraava_uusiutuminen = nyt.date() + timedelta(days=(4 - (nyt - alku).days % 4))
    embed.set_footer(
        text=f"Kauppa uusiutuu {seuraava_uusiutuminen.strftime('%d.%m.%Y')}."
    )

    return embed

ostot = {}
JSON_DIR = Path(os.getenv("JSON_DIRS"))
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

def puhdista_tuotteen_nimi(nimi: str) -> str:
    return nimi.replace(" (Tarjous!)", "").strip().lower()

def tallenna_osto(user_id: str, tuote: dict):
    ostot = lue_ostokset()
    nyt = datetime.now(timezone.utc)

    canon = puhdista_tuotteen_nimi(tuote["nimi"])
    logiikka = TUOTELOGIIKKA.get(canon)

    ostorivi = {
        "nimi": tuote["nimi"],
        "pvm": nyt.isoformat(),
    }
    if logiikka and logiikka.get("kesto"):
        ostorivi["expires_at"] = (nyt + logiikka["kesto"]).isoformat()
    elif tuote.get("kertakäyttöinen"):
        ostorivi["expires_at"] = (nyt + timedelta(days=4)).isoformat()

    kayttajan_ostot = ostot.get(user_id, [])
    kayttajan_ostot.append(ostorivi)
    ostot[user_id] = kayttajan_ostot

    tallenna_ostokset(ostot)

class EmojiModal(discord.ui.Modal, title="Valitse emoji"):
    emoji = discord.ui.TextInput(label="Emoji", placeholder="Esim. 😎, 🔥, 🤖")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        valinta = self.emoji.value.strip()
        if not valinta:
            await interaction.response.send_message("❌ Emojia ei annettu. Toiminto peruutettu.", ephemeral=True)
            return

        auto_react_users[str(interaction.user.id)] = valinta
        if self.kirjaa_kaytto:
            self.kirjaa_kaytto(valinta)

        await interaction.response.send_message(
            f"🤖 Bot reagoi viesteihisi emojilla {valinta} seuraavat 7 päivää!",
            ephemeral=True
        )

class VariModal(discord.ui.Modal, title="Valitse värisi"):
    vari = discord.ui.TextInput(label="Väri", placeholder="punainen, sininen, vihreä, jne.")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        varit = {
            "punainen": discord.Colour.red(),
            "sininen": discord.Colour.blue(),
            "vihreä": discord.Colour.green(),
            "keltainen": discord.Colour.gold(),
            "violetti": discord.Colour.purple(),
            "oranssi": discord.Colour.orange(),
            "musta": discord.Colour.dark_theme(),
            "valkoinen": discord.Colour.light_grey()
        }

        valinta = self.vari.value.strip().lower()
        vari = varit.get(valinta)

        if not vari:
            await interaction.response.send_message("❌ Väriä ei tunnistettu. Toiminto peruutettu.", ephemeral=True)
            return

        rooli = await interaction.guild.create_role(name=f"{interaction.user.name}-{valinta}", colour=vari, hoist=True)
        referenssi_rooli = discord.utils.get(interaction.guild.roles, name="-- Osto roolit --")
        if referenssi_rooli:
            uusi_position = referenssi_rooli.position + 1
            await interaction.guild.edit_role_positions(positions={rooli: uusi_position})

        await interaction.user.add_roles(rooli)
        if self.kirjaa_kaytto:
            self.kirjaa_kaytto(valinta)

        await interaction.response.send_message(
            f"🧬 Roolisi **{rooli.name}** luotiin värillä {valinta} ja sijoitettiin 24G-roolisi yläpuolelle!",
            ephemeral=True
        )

class CustomRooliModal(discord.ui.Modal, title="Anna roolisi nimi"):
    roolin_nimi = discord.ui.TextInput(label="Roolin nimi", placeholder="Esim. Legendaarinen Käyttäjä")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        nimi = self.roolin_nimi.value.strip()
        if not nimi:
            await interaction.response.send_message("❌ Roolin nimeä ei annettu. Toiminto peruutettu.", ephemeral=True)
            return

        rooli = await interaction.guild.create_role(name=nimi, hoist=True)
        referenssi_rooli = discord.utils.get(interaction.guild.roles, name="-- Osto roolit --")
        if referenssi_rooli:
            uusi_position = referenssi_rooli.position + 1
            await interaction.guild.edit_role_positions(positions={rooli: uusi_position})

        await interaction.user.add_roles(rooli)
        if self.kirjaa_kaytto:
            self.kirjaa_kaytto(nimi)

        await interaction.response.send_message(
            f"🎨 Roolisi **{rooli.name}** on luotu ja lisätty sinulle!",
            ephemeral=True
        )

class KomentoModal(discord.ui.Modal, title="Anna komennon nimi"):
    komento = discord.ui.TextInput(label="Komento", placeholder="Esim. status, info, ping")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        komennon_nimi = self.komento.value.strip()
        if not komennon_nimi:
            await interaction.response.send_message("❌ Komennon nimeä ei annettu. Toiminto peruutettu.", ephemeral=True)
            return

        if self.kirjaa_kaytto:
            self.kirjaa_kaytto(komennon_nimi)

        await interaction.response.send_message(
            f"🛠️ Komento **/{komennon_nimi}** on odottamassa vuoroaan ja tekeillä!",
            ephemeral=True
        )

class OmaPuhekanavaModal(discord.ui.Modal, title="Anna puhekanavan nimi"):
    kanavan_nimi = discord.ui.TextInput(label="Kanavan nimi", placeholder="Esim. Julius Lounge")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        nimi = self.kanavan_nimi.value.strip()
        if not nimi:
            await interaction.response.send_message("❌ Kanavan nimeä ei annettu. Toiminto peruutettu.", ephemeral=True)
            return

        vip_kategoria = discord.utils.get(interaction.guild.categories, name="⭐VIP kanavat")
        if not vip_kategoria:
            await interaction.response.send_message("❌ VIP-kategoriaa ei löytynyt. Toiminto peruutettu.", ephemeral=True)
            return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True)
        }

        try:
            kanava = await interaction.guild.create_voice_channel(
                name=nimi,
                overwrites=overwrites,
                category=vip_kategoria
            )

            alin_position = max([c.position for c in vip_kategoria.channels], default=0)
            await kanava.edit(position=alin_position + 1)

            if self.kirjaa_kaytto:
                self.kirjaa_kaytto(nimi)

            await interaction.response.send_message(
                f"🎙️ Oma puhekanavasi **{kanava.name}** luotiin ⭐VIP kanavat -kategoriaan!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Kanavan luonti epäonnistui: {e}", ephemeral=True)
            if self.kirjaa_kaytto:
                self.kirjaa_kaytto(f"Virhe: {e}")

class KanavaModal(discord.ui.Modal, title="Luo oma kanava"):
    nimi = discord.ui.TextInput(label="Kanavan nimi", placeholder="esim. oma-kanava")
    tyyppi = discord.ui.TextInput(label="Tyyppi (teksti/puhe)", placeholder="teksti tai puhe")

    def __init__(self):
        super().__init__()
        self.kirjaa_kaytto = None

    async def on_submit(self, interaction: discord.Interaction):
        vip_kategoria = discord.utils.get(interaction.guild.categories, name="⭐VIP kanavat")
        if not vip_kategoria:
            await interaction.response.send_message("❌ VIP-kategoriaa ei löytynyt. Toiminto peruutettu.", ephemeral=True)
            return

        try:
            if self.tyyppi.value.lower() == "puhe":
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                    interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True)
                }
                kanava = await interaction.guild.create_voice_channel(
                    name=self.nimi.value,
                    overwrites=overwrites,
                    category=vip_kategoria
                )
            else:
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, read_messages=False),
                    interaction.user: discord.PermissionOverwrite(view_channel=True, read_messages=True)
                }
                kanava = await interaction.guild.create_text_channel(
                    name=self.nimi.value,
                    overwrites=overwrites,
                    category=vip_kategoria
                )

            if self.kirjaa_kaytto:
                self.kirjaa_kaytto(self.nimi.value)

            await interaction.response.send_message(
                f"📢 Kanava **{kanava.mention}** ({self.tyyppi.value.lower()}) luotu ⭐VIP kanavat -kategoriaan nimellä **{self.nimi.value}**!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Kanavan luonti epäonnistui: {e}", ephemeral=True)
            if self.kirjaa_kaytto:
                self.kirjaa_kaytto(f"Virhe: {e}")

class ArmoNollausDropdownModal(discord.ui.Modal, title="Valitse streak, jonka armot nollataan"):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = str(user_id)

        json_path = os.path.join(os.getenv("JSON_DIR"), "streaks.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.streaks = data.get(self.user_id, {})
        except:
            self.streaks = {}

        options = []
        for key in ["daily", "weekly", "monthly"]:
            grace = self.streaks.get(key, {}).get("grace_fails", None)
            if grace is not None:
                label = key.capitalize()
                description = f"Nykyinen grace_fails: {grace}"
                options.append(discord.SelectOption(label=label, value=key, description=description))

        self.dropdown = discord.ui.Select(
            placeholder="Valitse streak-tyyppi nollattavaksi",
            min_values=1,
            max_values=1,
            options=options
        )
        self.add_item(self.dropdown)

    async def on_submit(self, interaction: discord.Interaction):
        valinta = self.dropdown.values[0]
        json_path = os.path.join(os.getenv("JSON_DIR"), "streaks.json")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if self.user_id not in data or valinta not in data[self.user_id]:
                await interaction.response.send_message("❌ Tälle streakille ei löytynyt dataa.", ephemeral=True)
                return

            current_grace = data[self.user_id][valinta].get("grace_fails", 0)
            if current_grace == 0:
                await interaction.response.send_message(f"ℹ️ {valinta.capitalize()} streakin grace_fails on jo 0 – ei nollattavaa.", ephemeral=True)
                return

            data[self.user_id][valinta]["grace_fails"] = 0

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if hasattr(self, "kirjaa_kaytto"):
                self.kirjaa_kaytto(valinta)

            embed = discord.Embed(
                title="🧼 Armot nollattu!",
                description=f"**{valinta.capitalize()}** streakin grace_fails on nyt 0.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ Virhe grace_fails-nollauksessa: {e}", ephemeral=True)

async def kasittele_tuote(interaction, nimi: str) -> tuple[str, Optional[discord.ui.Modal], Optional[str]]:
    lisatieto = ""
    modal = None
    viesti = None

    if nimi == "erikoisemoji":
        rooli = discord.utils.get(interaction.guild.roles, name="Erikoisemoji")
        if rooli:
            await interaction.user.add_roles(rooli)
        viesti = "😎 Erikoisemoji on nyt käytössäsi!"
        lisatieto = "\n😎 Erikoisemoji myönnetty"

    elif "double xp" in nimi.lower():
        rooli = discord.utils.get(interaction.guild.roles, name="Double XP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="Double XP")
        await interaction.user.add_roles(rooli)
        viesti = "⚡ Sait Double XP -roolin!"
        lisatieto = "\n⚡ Double XP myönnetty"

    elif "custom rooli" in nimi:
        if await onko_modal_kaytetty(bot, interaction.user, "Custom rooli luotu"):
            await interaction.response.send_message("🚫 Olet jo luonut roolin tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = CustomRooliModal()
        modal.kirjaa_kaytto = lambda nimi: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Custom rooli luotu", f"Rooli: {nimi}")
        )
        return "", modal, "Luo rooli"

    elif nimi == "vip-rooli":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            viesti = "⚠️ VIP-roolia ei löytynyt palvelimelta. Luo se ensin manuaalisesti!"
            return "", None, viesti
        await interaction.user.add_roles(rooli)
        viesti = "👑 VIP-rooli myönnetty sinulle!"
        lisatieto = "\n👑 VIP-rooli myönnetty"

    elif nimi == "oma puhekanava":
        if await onko_modal_kaytetty(bot, interaction.user, "Puhekanava luotu"):
            await interaction.response.send_message("🚫 Olet jo luonut puhekanavan tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = OmaPuhekanavaModal()
        modal.kirjaa_kaytto = lambda nimi: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Puhekanava luotu", f"Kanava: {nimi}")
        )
        return "", modal, "Luo puhekanava"

    elif "valitse emoji" in nimi:
        if await onko_modal_kaytetty(bot, interaction.user, "Emoji valittu"):
            await interaction.response.send_message("🚫 Olet jo valinnut emojin tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = EmojiModal()
        modal.kirjaa_kaytto = lambda emoji: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Emoji valittu", f"Emoji: {emoji}")
        )
        return "", modal, "Valitse emoji"

    elif "valitse värisi" in nimi:
        if await onko_modal_kaytetty(bot, interaction.user, "Väri valittu"):
            await interaction.response.send_message("🚫 Olet jo valinnut värin tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = VariModal()
        modal.kirjaa_kaytto = lambda vari: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Väri valittu", f"Väri: {vari}")
        )
        return "", modal, "Valitse väri"

    elif nimi == "soundboard-oikeus":
        rooli = discord.utils.get(interaction.guild.roles, name="SoundboardAccess")
        if not rooli:
            rooli = await interaction.guild.create_role(name="SoundboardAccess")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("🔊 Soundboard-oikeus myönnetty puhekanavalle!", ephemeral=True)

    elif nimi == "streak palautus":
        valittu_streak = "unknown"
        if await onko_modal_kaytetty(bot, interaction.user, "Streak palautus"):
            await interaction.response.send_message("🚫 Olet jo käyttänyt streak-palautuksen.", ephemeral=True)
            return "", None, None

        modal = StreakPalautusModal()
        modal.kirjaa_kaytto = lambda valinta: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Streak palautus", f"Streak: {valinta}")
        )

        return "", modal, "Palauta streak"

    elif "kanava" in nimi:
        if await onko_modal_kaytetty(bot, interaction.user, "Kanava luotu"):
            await interaction.response.send_message("🚫 Olet jo luonut kanavan tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = KanavaModal()
        modal.kirjaa_kaytto = lambda nimi: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Kanava luotu", f"Kanava: {nimi}")
        )

        return "", modal, "Luo kanava"

    elif "komento" in nimi:
        if await onko_modal_kaytetty(bot, interaction.user, "Komento luotu"):
            await interaction.response.send_message("🚫 Olet jo luonut komennon tällä toiminnolla.", ephemeral=True)
            return "", None, None

        modal = KomentoModal()
        modal.kirjaa_kaytto = lambda nimi: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Komento luotu", f"Komento: {nimi}")
        )
        return "", modal, "Luo komento"
    
    elif nimi == "Tehtävien armonantamisen nollaus":
        if await onko_modal_kaytetty(bot, interaction.user, "Tehtävien armonantamisen nollaus"):
            await interaction.response.send_message("🚫 Olet jo käyttänyt armojen nollauksen.", ephemeral=True)
            return "", None, None

        modal = ArmoNollausDropdownModal(interaction.user.id)
        modal.kirjaa_kaytto = lambda valinta: asyncio.create_task(
            kirjaa_modal_kaytto(bot, interaction.user, "Tehtävien armonantamisen nollaus", f"Nollattu: {valinta}")
        )

        return "", modal, "Nollaa grace_fails"
   
from dotenv import load_dotenv

async def osta_command(bot, interaction, tuotteen_nimi, tarjoukset, alennus=0, kuponki=None):
    user_id = str(interaction.user.id)
    tuotteet = kauppa_tuotteet + tarjoukset

    tuote = next(
        (t for t in tuotteet if puhdista_tuotteen_nimi(t["nimi"]) == puhdista_tuotteen_nimi(tuotteen_nimi)),
        None
    )

    if not tuote:
        await interaction.response.send_message(
            f"❌ Tuotetta **{tuotteen_nimi}** ei löytynyt.",
            ephemeral=True
        )
        return

    ok, exp = voiko_ostaa(user_id, tuote["nimi"])
    if not ok:
        if exp:
            loppuu = exp.strftime("%d.%m.%Y %H:%M")
            await interaction.response.send_message(
                f"🚫 Et voi ostaa tuotetta **{tuote['nimi']}** uudelleen juuri nyt.\n"
                f"⌛ Rajoitus päättyy {loppuu}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🚫 Tuote **{tuote['nimi']}** on kertakäyttöinen eikä sitä voi ostaa uudelleen.",
                ephemeral=True
            )
        return

    voimassa_jaljella = onko_tuote_voimassa(user_id, tuote["nimi"])
    if voimassa_jaljella:
        paattyy = datetime.now(timezone.utc) + voimassa_jaljella
        paattyy_str = paattyy.strftime("%d.%m.%Y klo %H:%M")
        await interaction.response.send_message(
            f"🚫 Tuote **{tuote['nimi']}** on jo käytössäsi.\n"
            f"⏳ Jäljellä noin **{voimassa_jaljella.days} pv {voimassa_jaljella.seconds//3600} h** "
            f"(päättyy {paattyy_str}).\n"
            f"🛒 Voit ostaa tuotteen uudelleen, kun oikeus on vanhentunut.",
            ephemeral=True
        )
        return

    periodi = nykyinen_periodi()
    tarjousnimet = [puhdista_tuotteen_nimi(t["nimi"]) for t in tarjoukset]
    vaihdettavat = [puhdista_tuotteen_nimi(t["nimi"]) for t in kauppa_tuotteet[periodi*2:(periodi+1)*2]]
    sallitut_tuotteet = vaihdettavat + tarjousnimet

    if puhdista_tuotteen_nimi(tuote["nimi"]) not in sallitut_tuotteet:
        await interaction.response.send_message("❌ Tämä tuote ei ole tällä hetkellä saatavilla kaupassa.", ephemeral=True)
        return

    if kuponki:
        alennus_prosentti = tarkista_kuponki(kuponki, tuote["nimi"], user_id, interaction)
        if alennus_prosentti == 0:
            await interaction.response.send_message(
                "❌ Kuponki ei kelpaa tälle tuotteelle, vanhentunut tai käyttöraja täynnä. Osto peruutettu.",
                ephemeral=True
            )
            return
    else:
        alennus_prosentti = alennus

    hinta = tuote["hinta"]
    hinta_alennettu = max(0, int(hinta * (1 - alennus_prosentti / 100)))

    tallenna_osto(user_id, tuote)

    kuponkiviesti = f"\n📄 Käytit koodin **{kuponki}** (-{alennus_prosentti}%)" if kuponki else ""

    nimi = puhdista_tuotteen_nimi(tuote["nimi"])
    lisatieto, modal, dropdown_otsikko = await kasittele_tuote(interaction, nimi)
    view = ModalDropdownView(modal, dropdown_otsikko) if modal else None

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Ostettu onnistuneesti!",
            description=f"Ostit tuotteen **{tuote['emoji']} {tuote['nimi']}** ({hinta_alennettu} XP) {kuponkiviesti}\nSe on nyt käytössäsi! Jos haluat perua ostoksen, ota yhteyttä ``/help``.",
            color=discord.Color.green()
        ),
        view=view,
        ephemeral=True
    )

    try:
        kanava_id = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
        lokikanava = bot.get_channel(kanava_id)
        if lokikanava:
            view = PeruOstosView(interaction.user, tuote["nimi"])
            await lokikanava.send(
                f"🧾 {interaction.user.mention} osti tuotteen **{tuote['nimi']}** ({hinta_alennettu} XP)" +
                (lisatieto if lisatieto else f"\nℹ️ Tuote {tuote['nimi']} aktivoitu") +
                (f"\n📄 Kuponki: **{kuponki}** (-{alennus_prosentti}%)" if kuponki else ""),
                view=view
            )
    except Exception as e:
        print(f"Lokitus epäonnistui: {e}")

class PeruOstosView(View):
    def __init__(self, user: discord.Member, tuotteen_nimi: str):
        super().__init__(timeout=None)
        self.user = user
        self.tuotteen_nimi = tuotteen_nimi

    @discord.ui.button(label="Peru ostos", style=discord.ButtonStyle.danger, emoji="❌")
    async def peru_ostos_button(self, interaction: discord.Interaction, button: Button):
        sallitut_roolit = os.getenv("OSTOS_PERU_ROOLIT", "")
        sallitut_rooli_idt = [int(rid.strip()) for rid in sallitut_roolit.split(",") if rid.strip().isdigit()]

        kayttajan_roolit = [r.id for r in interaction.user.roles]
        if not any(rid in kayttajan_roolit for rid in sallitut_rooli_idt):
            await interaction.response.send_message("❌ Sinulla ei ole oikeutta perua ostoksia.", ephemeral=True)
            return

        await peru_ostos(interaction, self.user, self.tuotteen_nimi)
        self.stop()

async def peru_ostos(interaction: discord.Interaction, user: discord.Member, tuotteen_nimi: str):
    user_id = str(user.id)
    ostot = lue_ostokset()
    tuotteen_nimi_puhdistettu = puhdista_tuotteen_nimi(tuotteen_nimi)

    alkuperaiset = ostot.get(user_id, [])
    ostot[user_id] = [o for o in alkuperaiset if puhdista_tuotteen_nimi(o.get("nimi", "")) != tuotteen_nimi_puhdistettu]
    tallenna_ostokset(ostot)

    try:
        if tuotteen_nimi_puhdistettu == "erikoisemoji":
            rooli = discord.utils.get(user.guild.roles, name="Erikoisemoji")
            if rooli:
                await user.remove_roles(rooli)

        elif tuotteen_nimi_puhdistettu == "double xp -päivä":
            rooli = discord.utils.get(user.guild.roles, name="Double XP")
            if rooli:
                await user.remove_roles(rooli)

        elif tuotteen_nimi_puhdistettu == "vip-chat" or tuotteen_nimi_puhdistettu == "vip-rooli":
            rooli = discord.utils.get(user.guild.roles, name="VIP")
            if rooli:
                await user.remove_roles(rooli)

        elif tuotteen_nimi_puhdistettu == "soundboard-oikeus":
            rooli = discord.utils.get(user.guild.roles, name="SoundboardAccess")
            if rooli:
                await user.remove_roles(rooli)

        elif tuotteen_nimi_puhdistettu == "valitse emoji":
            auto_react_users.pop(user_id, None)

        elif tuotteen_nimi_puhdistettu.startswith(f"{user.name}-"):
            rooli = discord.utils.get(user.guild.roles, name__startswith=f"{user.name}-")
            if rooli:
                await user.remove_roles(rooli)
                await rooli.delete()

    except Exception as e:
        print(f"Oikeuksien poisto epäonnistui: {e}")

    try:
        kanava_id = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
        lokikanava = bot.get_channel(kanava_id)
        if lokikanava:
            await lokikanava.send(f"❌ {user.mention} perui ostoksen **{tuotteen_nimi}**. Oikeudet poistettu.")
    except Exception as e:
        print(f"Peruutuslokitus epäonnistui: {e}")

    await interaction.response.send_message(f"✅ Ostos **{tuotteen_nimi}** peruttu ja oikeudet poistettu käyttäjältä {user.mention}.", ephemeral=True)