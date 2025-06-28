import discord
import asyncio
import os
import json
import random
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import tasks, commands
from bot.utils.bot_setup import bot
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from pathlib import Path


def start_store_loops():
    asyncio.create_task(tarkista_ostojen_kuukausi())

load_dotenv()
OSTOSLOKI_KANAVA_ID = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

kauppa_tuotteet = [
    {"nimi": "Erikoisemoji", "kuvaus": "Käytä erikoisemojeita", "hinta": 1000, "kertakäyttöinen": True, "emoji": "😎", "tarjousprosentti": 30},
    {"nimi": "Double XP -päivä", "kuvaus": "Saat tuplat XP:t 24h", "hinta": 2000, "kertakäyttöinen": True, "emoji": "⚡", "tarjousprosentti": 50},
    {"nimi": "Custom rooli", "kuvaus": "Saat oman roolin", "hinta": 5000, "kertakäyttöinen": True, "emoji": "🎨", "tarjousprosentti": 20},
    {"nimi": "VIP-chat", "kuvaus": "Pääsy VIP-kanavalle", "hinta": 3000, "kertakäyttöinen": False, "emoji": "💎", "tarjousprosentti": 25},
    {"nimi": "VIP-rooli (7 päivää)", "kuvaus": "Saat VIP-roolin viikoksi", "hinta": 2500, "kertakäyttöinen": True, "emoji": "👑", "tarjousprosentti": 40},
    {"nimi": "Oma komento", "kuvaus": "Saat tehdä oman /komennon", "hinta": 6000, "kertakäyttöinen": True, "emoji": "🛠️", "tarjousprosentti": 35},
    {"nimi": "Oma kanava", "kuvaus": "Saat oman tekstikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "📢", "tarjousprosentti": 30},
    {"nimi": "Oma puhekanava", "kuvaus": "Saat oman äänikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "🎙️", "tarjousprosentti": 30},
]

from discord.ext import tasks

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

TARJOUS_TIEDOSTO = Path("data/shop/tarjous.json")

def hae_tai_paivita_tarjous():
    nyt = datetime.now(timezone.utc).date()

    try:
        with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
            data = json.load(f)
            paivamaara = datetime.fromisoformat(data.get("paivamaara"))
            if (nyt - paivamaara.date()).days < 4:
                tuote = data.get("tuote")
                if isinstance(tuote, dict):
                    return [tuote]
                elif isinstance(tuote, list) and all(isinstance(t, dict) for t in tuote):
                    return tuote
                else:
                    return []
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        pass

    periodi = nykyinen_periodi()
    normaalit = kauppa_tuotteet[periodi*2:(periodi+1)*2]

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
        json.dump({"paivamaara": datetime.now(timezone.utc).isoformat(), "tuote": tarjous}, f, ensure_ascii=False, indent=2)

    return [tarjous]

def nykyinen_periodi():
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - alku
    periodi = (delta.days // 4) % (len(kauppa_tuotteet) // 2)
    return periodi

from datetime import datetime, timedelta, timezone

def nayta_kauppa_embed(interaction, tarjoukset):
    user_id = str(interaction.user.id)
    ostot = lue_ostokset()
    omistetut = ostot.get(user_id, [])

    periodi = nykyinen_periodi()
    tarjousnimet = [t["nimi"].replace(" (Tarjous!)", "") for t in tarjoukset]
    vaihdettavat = [t for t in kauppa_tuotteet[periodi*2:(periodi+1)*2] if t["nimi"] not in tarjousnimet]    

    embed = discord.Embed(
        title="🛒 Sannamaija Shop!",
        description="Tässä ovat tämänhetkiset tuotteet:",
        color=discord.Color.gold()
    )

    # 🔁 Kertakäyttöiset tuotteet
    kertakayttoiset = [t for t in vaihdettavat if t["kertakäyttöinen"]]
    if kertakayttoiset:
        embed.add_field(name="🔁 Kertakäyttöiset tuotteet", value="\u200b", inline=False)
        for t in kertakayttoiset:
            emoji = t.get("emoji", "🛍️")
            omistaa = "✅ Omistat" if t["nimi"] in omistetut else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n{omistaa}",
                inline=False
            )

    # ♻️ Monikäyttöiset tuotteet
    monikayttoiset = [t for t in vaihdettavat if not t["kertakäyttöinen"]]
    if monikayttoiset:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="♻️ Monikäyttöiset tuotteet", value="\u200b", inline=False)
        for t in monikayttoiset:
            emoji = t.get("emoji", "🎁")
            omistaa = "✅ Omistat" if t["nimi"] in omistetut else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n{omistaa}",
                inline=False
            )

    # 🎉 Tarjoukset
    if tarjoukset:
        embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━", inline=False)  
        embed.add_field(name="🎉 Tarjoukset", value="\u200b", inline=False)
        for t in tarjoukset:
            emoji = t.get("emoji", "🔥")
            tyyppi = "Kertakäyttöinen" if t["kertakäyttöinen"] else "Monikäyttöinen"
            omistaa = "✅ Omistat" if t["nimi"] in omistetut else ""
            embed.add_field(
                name=f"{emoji} {t['nimi']} ({t['hinta']} XP)",
                value=f"{t['kuvaus']}\n*Tyyppi: {tyyppi}* {omistaa}",
                inline=False
            )

    # Footer: uusiutumispäivä
    nyt = datetime.now(timezone.utc)
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    seuraava_uusiutuminen = nyt.date() + timedelta(days=(4 - (nyt - alku).days % 4))
    embed.set_footer(text=f"Kauppa uusiutuu {seuraava_uusiutuminen.strftime('%d.%m.%Y')}.\nKäytä /kauppa [tuotteen nimi] ostaaksesi.\nSinulta EI vähenny XP määrä ostoksia tekemällä!")

    return embed

ostot = {}
OSTO_TIEDOSTO = Path("data/shop/ostot.json")

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

from discord.ui import Modal, TextInput

class KanavaModal(Modal, title="Luo oma kanava"):
    nimi = TextInput(label="Kanavan nimi", placeholder="esim. oma-kanava")
    tyyppi = TextInput(label="Tyyppi (teksti/puhe)", placeholder="teksti tai puhe")

    async def on_submit(self, interaction: discord.Interaction):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True)
        }

        if self.tyyppi.value.lower() == "puhe":
            kanava = await interaction.guild.create_voice_channel(name=self.nimi.value, overwrites=overwrites)
        else:
            kanava = await interaction.guild.create_text_channel(name=self.nimi.value, overwrites=overwrites)

        await interaction.response.send_message(f"📢 Kanava **{kanava.mention}** luotu ja näkyy sinulle!", ephemeral=True)

async def kasittele_tuote(interaction, nimi: str) -> str:
    lisatieto = ""

    if nimi == "erikoisemoji":
        rooli = discord.utils.get(interaction.guild.roles, name="Erikoisemoji")
        if rooli:
            await interaction.user.add_roles(rooli)
        await interaction.followup.send("😎 Erikoisemoji on nyt käytössäsi!")

    elif nimi == "double xp -päivä":
        rooli = discord.utils.get(interaction.guild.roles, name="Double XP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="Double XP")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("⚡ Sait Double XP -roolin 24 tunniksi!")

        async def poista_rooli_viiveella():
            await asyncio.sleep(24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send("⏳ Double XP -roolisi on vanhentunut.")
            except:
                pass
        bot.loop.create_task(poista_rooli_viiveella())

    elif nimi == "vip-chat":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="VIP")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("💎 Sait pääsyn VIP-chattiin!")

    elif nimi == "oma puhekanava":
        nimi_kanava = await kysy_kayttajalta(interaction, "Mikä on kanavasi nimi?")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(connect=False),
            interaction.user: discord.PermissionOverwrite(connect=True)
        }
        kanava = await interaction.guild.create_voice_channel(name=nimi_kanava, overwrites=overwrites)
        await interaction.followup.send(f"🎙️ Oma puhekanavasi **{kanava.name}** on luotu!")

    elif "rooli" in nimi:
        if "vip-rooli" in nimi:
            roolinimi = "VIP"
        else:
            roolinimi = await kysy_kayttajalta(interaction, "Mikä on roolisi nimi?")
            if not roolinimi:
                return ""

        lisatieto = f" (nimi: {roolinimi})"
        rooli = await interaction.guild.create_role(name=roolinimi)
        await interaction.user.add_roles(rooli)
        await interaction.followup.send(f"🎉 Rooli **{roolinimi}** luotu ja lisätty sinulle!")

        if "7 päivää" in nimi:
            async def poista_rooli_viiveella():
                await asyncio.sleep(7 * 24 * 60 * 60)
                try:
                    await interaction.user.remove_roles(rooli)
                    await interaction.user.send(f"⏳ Rooli **{rooli.name}** on nyt vanhentunut ja poistettu.")
                except:
                    pass
            bot.loop.create_task(poista_rooli_viiveella())

    elif "kanava" in nimi:
        await interaction.response.send_modal(KanavaModal())
        return ""

    elif "komento" in nimi:
        komennon_nimi = await kysy_kayttajalta(interaction, "Mikä on komennon nimi?")
        if komennon_nimi:
            lisatieto = f" (nimi: {komennon_nimi})"
            await interaction.followup.send(f"🛠️ Komento **/{komennon_nimi}** on odottamassa vuoroaan ja tekeillä!")

    return lisatieto
        
from dotenv import load_dotenv

async def osta_command(interaction, tuotteen_nimi, tarjoukset):
    global ostot
    user_id = str(interaction.user.id)
    tuotteet = kauppa_tuotteet + tarjoukset
    tuote = next((t for t in tuotteet if t["nimi"].lower() == tuotteen_nimi.lower()), None)

    if not tuote:
        await interaction.response.send_message("Tuotetta ei löytynyt.")
        return

    periodi = nykyinen_periodi()
    tarjousnimet = [t["nimi"] for t in tarjoukset]
    vaihdettavat = [t["nimi"] for t in kauppa_tuotteet[periodi*2:(periodi+1)*2]]
    sallitut_tuotteet = vaihdettavat + tarjousnimet

    if tuote["nimi"] not in sallitut_tuotteet:
        await interaction.response.send_message("Tämä tuote ei ole tällä hetkellä saatavilla kaupassa.")
        return

    ostot = lue_ostokset()
    if user_id not in ostot:
        ostot[user_id] = []

    # Suodatetaan pois virheelliset ostot
    ostot[user_id] = [o for o in ostot[user_id] if isinstance(o, dict) and "nimi" in o]

    if tuote["kertakäyttöinen"] and any(o.get("nimi") == tuote["nimi"] for o in ostot[user_id]):
        await interaction.response.send_message("Olet jo ostanut tämän kertakäyttöisen tuotteen.")
        return

    ostot[user_id].append({
        "nimi": tuote["nimi"],
        "pvm": datetime.now().isoformat()
    })
    tallenna_ostokset(ostot)

    await interaction.response.send_message(f"✅ Ostit tuotteen **{tuote['nimi']}**!", ephemeral=True)
    await interaction.followup.send("⏳ Käsitellään ostosta...")

    # Käsittele tuote
    nimi = puhdista_tuotteen_nimi(tuote["nimi"])
    lisatieto = await kasittele_tuote(interaction, nimi)

    # Lokitus
    try:
        kanava_id = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
        lokikanava = bot.get_channel(kanava_id)
        if lokikanava:
            await lokikanava.send(
                f"🧾 {interaction.user.mention} osti tuotteen **{tuote['nimi']}** ({tuote['hinta']} XP){lisatieto}"
            )
    except Exception as e:
        print(f"Lokitus epäonnistui: {e}")