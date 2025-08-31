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

load_dotenv()
OSTOSLOKI_KANAVA_ID = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))
JSON_DIRS = Path(os.getenv("JSON_DIRS"))
tuotteet_polku = JSON_DIRS / "tuotteet.json"

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
    {"nimi": "Streak palautus", "kuvaus": "Palauttaa valitsemasi streakin aiempaan pisin-arvoon.", "hinta": 3000, "kertakäyttöinen": True, "emoji": "♻️", "tarjousprosentti": 20}
]

TUOTELOGIIKKA = {
    "VIP-chat": {"rooli": "VIP", "kesto": timedelta(days=30)},
    "Valitse emoji": {"rooli": "EmojiValinta", "kesto": timedelta(days=14)},
    "Oma komento": {"rooli": "KomentoKäyttäjä", "kesto": timedelta(days=14)},
    "Custom rooli": {"rooli": "CustomRooli", "kesto": timedelta(days=30)},
    "Soundboard-oikeus": {"rooli": "Soundboard", "kesto": timedelta(days=7)},
    # Lisää tarvittaessa muita tuotteita
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
                        kaikki_paivamaarat.append(pvm)
                    except:
                        continue

        if not kaikki_paivamaarat:
            return  

        nyt = datetime.now()
        viimeisin = max(kaikki_paivamaarat)

        if viimeisin.month != nyt.month:
            print("Tyhjennetään ostot (uusi kuukausi)")
            tallenna_ostokset({})
    except Exception as e:
        print(f"Ostojen tarkistus epäonnistui: {e}")

@tasks.loop(hours=1)
async def tarkista_vanhentuneet_oikeudet():
    ostot = lue_ostokset()
    nyt = datetime.now()

    for user_id, ostoslista in ostot.items():
        guild = discord.utils.get(bot.guilds)
        member = guild.get_member(int(user_id))
        if not member:
            continue

        for ostos in ostoslista:
            try:
                pvm = datetime.fromisoformat(ostos.get("pvm", ""))
                nimi = ostos.get("nimi", "")

                for avain, tiedot in TUOTELOGIIKKA.items():
                    if avain.lower() in nimi.lower():
                        if (nyt - pvm) > tiedot["kesto"]:
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

def onko_tuote_voimassa(user_id: str, tuotteen_nimi: str) -> Optional[timedelta]:
    ostot = lue_ostokset()
    kayttajan_ostot = ostot.get(user_id, [])
    nyt = datetime.now()

    for o in kayttajan_ostot:
        nimi = puhdista_tuotteen_nimi(o.get("nimi", ""))
        if nimi == puhdista_tuotteen_nimi(tuotteen_nimi):
            pvm = datetime.fromisoformat(o.get("pvm", ""))
            tuotelogiikka = TUOTELOGIIKKA.get(nimi.lower())
            if tuotelogiikka:
                kesto = tuotelogiikka["kesto"]
                paattymisaika = pvm + kesto
                if nyt < paattymisaika:
                    return paattymisaika - nyt
    return None

class StreakPalautusModal(Modal, title="Valitse streak palautettavaksi"):
    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction
        self.select = Select(
            placeholder="Valitse streakin tyyppi",
            options=[
                discord.SelectOption(label="Päivittäinen", value="daily"),
                discord.SelectOption(label="Viikoittainen", value="weekly"),
                discord.SelectOption(label="Kuukausittainen", value="monthly"),
                discord.SelectOption(label="Puhe", value="voice")
            ]
        )
        self.add_item(self.select)

    async def on_submit(self, interaction: discord.Interaction):
        from bot.utils.tasks_utils import load_streaks, save_streaks
        uid = str(interaction.user.id)
        streaks = load_streaks()
        valinta = self.select.values[0]

        if uid not in streaks or valinta not in streaks[uid]:
            await interaction.response.send_message("❌ Tälle streakille ei löytynyt dataa.", ephemeral=True)
            return

        data = streaks[uid][valinta]
        if data.get("streak", 0) < data.get("max_streak", 0):
            data["streak"] = data["max_streak"]
            save_streaks(streaks)
            await interaction.response.send_message(
                f"♻️ {valinta.capitalize()} streak palautettu arvoon {data['max_streak']}! 🔥",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("ℹ️ Streak on jo ennätyksessä, ei palautettavaa.", ephemeral=True)

def nykyinen_periodi():
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - alku
    periodi = (delta.days // 4) % (len(kauppa_tuotteet) // 2)
    return periodi

def nayta_kauppa_embed(interaction, tarjoukset):
    user_id = str(interaction.user.id)

    xp_data = load_xp_data()
    user_xp = xp_data.get(user_id, {}).get("xp", 0)

    ostot = lue_ostokset()
    omistetut = ostot.get(user_id, [])
    omistetut_nimet = [puhdista_tuotteen_nimi(o["nimi"]) for o in omistetut if isinstance(o, dict) and "nimi" in o]

    periodi = nykyinen_periodi()
    tarjousnimet = [t["nimi"].replace(" (Tarjous!)", "") for t in tarjoukset]
    vaihdettavat = [t for t in kauppa_tuotteet[periodi*2:(periodi+1)*2] if t["nimi"] not in tarjousnimet]    

    embed = discord.Embed(
        title="🛒 Sannamaija Shop!",
        description=f"Tässä ovat tämänhetkiset tuotteet:\n**Sinulla on {user_xp} XP:tä käytettävissä** ✨",
        color=discord.Color.gold()
    )

    kertakayttoiset = [t for t in vaihdettavat if t["kertakäyttöinen"]]
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

    monikayttoiset = [t for t in vaihdettavat if not t["kertakäyttöinen"]]
    if monikayttoiset:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
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
        embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━", inline=False)  
        embed.add_field(name="🎉 Tarjoukset", value="\u200b", inline=False)
        for t in tarjoukset:
            emoji = t.get("emoji", "🔥")
            tyyppi = "Kertakäyttöinen" if t["kertakäyttöinen"] else "Monikäyttöinen"
            omistaa = "✅ Omistat" if puhdista_tuotteen_nimi(t["nimi"]) in omistetut_nimet else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n*Tyyppi: {tyyppi}* {omistaa}",
                inline=False
            )

    nyt = datetime.now(timezone.utc)
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    seuraava_uusiutuminen = nyt.date() + timedelta(days=(4 - (nyt - alku).days % 4))
    embed.set_footer(text=f"Kauppa uusiutuu {seuraava_uusiutuminen.strftime('%d.%m.%Y')}.\nKäytä /kauppa [tuotteen nimi] ostaaksesi.\nSinulta EI vähenny XP määrä ostoksia tekemällä!")

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

def puhdista_tuotteen_nimi(nimi: str) -> str:
    return nimi.replace(" (Tarjous!)", "").strip().lower()

class KanavaModal(Modal, title="Luo oma kanava"):
    nimi = TextInput(label="Kanavan nimi", placeholder="esim. oma-kanava")
    tyyppi = TextInput(label="Tyyppi (teksti/puhe)", placeholder="teksti tai puhe")

    async def on_submit(self, interaction: discord.Interaction):
        vip_kategoria = discord.utils.get(interaction.guild.categories, name="⭐VIP kanavat")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True)
        }

        if self.tyyppi.value.lower() == "puhe":
            kanava = await interaction.guild.create_voice_channel(
                name=self.nimi.value,
                overwrites=overwrites,
                category=vip_kategoria
            )
        else:
            kanava = await interaction.guild.create_text_channel(
                name=self.nimi.value,
                overwrites=overwrites,
                category=vip_kategoria
            )

        await interaction.response.send_message(
            f"📢 Kanava **{kanava.mention}** luotu ⭐VIP kanavat -kategoriaan ja näkyy sinulle!",
            ephemeral=True
        )

async def kasittele_tuote(interaction, nimi: str) -> str:
    lisatieto = ""

    if nimi == "erikoisemoji":
        rooli = discord.utils.get(interaction.guild.roles, name="Erikoisemoji")
        if rooli:
            await interaction.user.add_roles(rooli)
        await interaction.followup.send("😎 Erikoisemoji on nyt käytössäsi!", ephemeral=True)

    elif nimi == "double xp -päivä":
        rooli = discord.utils.get(interaction.guild.roles, name="Double XP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="Double XP")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("⚡ Sait Double XP -roolin!", ephemeral=True)

    elif nimi == "custom rooli":
        roolin_nimi = await kysy_kayttajalta(interaction, "Mikä on roolisi nimi?")
        if not roolin_nimi:
            await interaction.followup.send("❌ Roolin nimeä ei annettu. Toiminto peruutettu.", ephemeral=True)
            return ""

        rooli = await interaction.guild.create_role(name=roolin_nimi, hoist=True)
        referenssi_rooli = discord.utils.get(interaction.guild.roles, name="-- Osto roolit --")
        if referenssi_rooli:
            uusi_position = referenssi_rooli.position + 1
            await interaction.guild.edit_role_positions(positions={rooli: uusi_position})

        await interaction.user.add_roles(rooli)
        await interaction.followup.send(f"🎨 Roolisi **{rooli.name}** on luotu ja lisätty sinulle!", ephemeral=True)
        lisatieto = f" (rooli: {roolin_nimi})"

    elif nimi == "vip-chat":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="VIP")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("💎 Sait pääsyn VIP-chattiin!", ephemeral=True)

    elif nimi == "oma puhekanava":
        nimi_kanava = await kysy_kayttajalta(interaction, "Mikä on kanavasi nimi?")
        vip_kategoria = discord.utils.get(interaction.guild.categories, name="⭐VIP kanavat")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(connect=False),
            interaction.user: discord.PermissionOverwrite(connect=True)
        }

        kanava = await interaction.guild.create_voice_channel(
            name=nimi_kanava,
            overwrites=overwrites,
            category=vip_kategoria
        )

        kanavat_kategoriassa = vip_kategoria.channels
        alin_position = max([c.position for c in kanavat_kategoriassa], default=0)
        await kanava.edit(position=alin_position + 1)

        await interaction.followup.send(
            f"🎙️ Oma puhekanavasi **{kanava.name}** luotiin ⭐VIP kanavat kategoriaan!",
            ephemeral=True
        )

    elif nimi == "valitse värisi":
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

        varivalinta = await kysy_kayttajalta(interaction, "Valitse väri (sininen, punainen, vihreä, keltainen, violetti, oranssi, musta tai valkoinen):")
        vari = varit.get(varivalinta.lower())

        if vari:
            rooli = await interaction.guild.create_role(name=f"{interaction.user.name}-{varivalinta}", colour=vari, hoist=True)

            referenssi_rooli = discord.utils.get(interaction.guild.roles, name="-- Osto roolit --")
            if referenssi_rooli:
                uusi_position = referenssi_rooli.position + 1
                await interaction.guild.edit_role_positions(positions={rooli: uusi_position})

            await interaction.user.add_roles(rooli)
            await interaction.followup.send(f"🧬 Roolisi **{rooli.name}** luotiin värillä {varivalinta} ja sijoitettiin 24G-roolisi yläpuolelle!", ephemeral=True)
            lisatieto = f" (väri: {varivalinta})"
        else:
            await interaction.followup.send("❌ Väriä ei tunnistettu. Toiminto peruutettu.", ephemeral=True)

    elif nimi == "valitse emoji":
        emoji_valinta = await kysy_kayttajalta(interaction, "Millä emojilla botin tulisi reagoida viesteihisi?")
        if emoji_valinta:
            auto_react_users[str(interaction.user.id)] = emoji_valinta
            await interaction.followup.send(f"🤖 Bot reagoi viesteihisi emojilla {emoji_valinta} seuraavat 7 päivää!", ephemeral=True)
            lisatieto = f" (emoji: {emoji_valinta})"

    elif nimi == "soundboard-oikeus":
        rooli = discord.utils.get(interaction.guild.roles, name="SoundboardAccess")
        if not rooli:
            rooli = await interaction.guild.create_role(name="SoundboardAccess")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("🔊 Soundboard-oikeus myönnetty puhekanavalle!", ephemeral=True)

    elif nimi == "vip-rooli":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            await interaction.followup.send("⚠️ VIP-roolia ei löytynyt palvelimelta. Luo se ensin manuaalisesti!", ephemeral=True)
            return ""
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("👑 VIP-rooli myönnetty sinulle!", ephemeral=True)

    elif nimi == "streak palautus":
        await interaction.response.send_modal(StreakPalautusModal(interaction))
        return ""

    elif "kanava" in nimi:
        await interaction.response.send_modal(KanavaModal())
        return ""

    elif "komento" in nimi:
        komennon_nimi = await kysy_kayttajalta(interaction, "Mikä on komennon nimi?")
        if komennon_nimi:
            lisatieto = f" (nimi: {komennon_nimi})"
            await interaction.followup.send(f"🛠️ Komento **/{komennon_nimi}** on odottamassa vuoroaan ja tekeillä!", ephemeral=True)

    return lisatieto
        
from dotenv import load_dotenv

async def osta_command(bot, interaction, tuotteen_nimi, tarjoukset, alennus=0, kuponki=None):
    global ostot
    user_id = str(interaction.user.id)
    tuotteet = kauppa_tuotteet + tarjoukset
    tuote = next((t for t in tuotteet if t["nimi"].lower() == tuotteen_nimi.lower()), None)

    if not tuote:
        await interaction.response.send_message("Tuotetta ei löytynyt.", ephemeral=True)
        return

    voimassa_jaljella = onko_tuote_voimassa(user_id, tuote["nimi"])
    if voimassa_jaljella:
        paattyy = datetime.now() + voimassa_jaljella
        paattyy_str = paattyy.strftime("%d.%m.%Y klo %H:%M")
        await interaction.response.send_message(
            f"🚫 Tuote **{tuote['nimi']}** on jo käytössäsi.\n"
            f"⏳ Voimassaoloaikaa jäljellä noin **{voimassa_jaljella.days} päivää** (päättyy {paattyy_str}).\n"
            f"🛒 Voit ostaa tuotteen uudelleen, kun oikeus on vanhentunut.",
            ephemeral=True
        )
        return

    periodi = nykyinen_periodi()
    tarjousnimet = [t["nimi"] for t in tarjoukset]
    vaihdettavat = [t["nimi"] for t in kauppa_tuotteet[periodi*2:(periodi+1)*2]]
    sallitut_tuotteet = vaihdettavat + tarjousnimet

    if tuote["nimi"] not in sallitut_tuotteet:
        await interaction.response.send_message("Tämä tuote ei ole tällä hetkellä saatavilla kaupassa.", ephemeral=True)
        return

    ostot = lue_ostokset()
    if user_id not in ostot:
        ostot[user_id] = []

    ostot[user_id] = [o for o in ostot[user_id] if isinstance(o, dict) and "nimi" in o]

    if kuponki:
        alennus_prosentti = tarkista_kuponki(kuponki, tuote["nimi"], user_id, interaction)
        if alennus_prosentti == 0:
            await interaction.response.send_message("❌ Kuponki ei kelpaa tälle tuotteelle, vanhentunut tai käyttöraja täynnä. Osto peruutettu.", ephemeral=True)
            return
    else:
        alennus_prosentti = alennus

    hinta = tuote["hinta"]
    hinta_alennettu = max(0, int(hinta * (1 - alennus_prosentti / 100)))

    ostot[user_id].append({
        "nimi": tuote["nimi"],
        "pvm": datetime.now().isoformat()
    })
    tallenna_ostokset(ostot)

    kuponkiviesti = f"\n📄 Käytit koodin **{kuponki}** (-{alennus_prosentti}%)" if kuponki else ""

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Ostettu onnistuneesti!",
            description=f"Ostit tuotteen **{tuote['emoji']} {tuote['nimi']}** ({hinta_alennettu} XP) {kuponkiviesti}\nSe on nyt käytössäsi 🎉",
            color=discord.Color.green()
        ),
        ephemeral=True
    )

    nimi = puhdista_tuotteen_nimi(tuote["nimi"])
    lisatieto = await kasittele_tuote(interaction, nimi)

    try:
        kanava_id = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
        lokikanava = bot.get_channel(kanava_id)
        if lokikanava:
            view = PeruOstosView(interaction.user, tuote["nimi"])
            await lokikanava.send(
                f"🧾 {interaction.user.mention} osti tuotteen **{tuote['nimi']}** ({hinta_alennettu} XP){lisatieto}" +
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