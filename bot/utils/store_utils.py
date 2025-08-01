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
from bot.utils.xp_utils import load_xp_data
from pathlib import Path
from datetime import datetime
import os
import json
from pathlib import Path
import discord

def start_store_loops():
    if not tarkista_ostojen_kuukausi.is_running():
        tarkista_ostojen_kuukausi.start()
    if not paivita_tarjous_automatisoitu.is_running():
        paivita_tarjous_automatisoitu.start()

load_dotenv()
OSTOSLOKI_KANAVA_ID = int(os.getenv("OSTOSLOKI_KANAVA_ID"))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

auto_react_users = {}  # user_id -> emoji

kauppa_tuotteet = [
    {"nimi": "Erikoisemoji", "kuvaus": "Käytä erikoisemojeita", "hinta": 1000, "kertakäyttöinen": True, "emoji": "😎"},
    {"nimi": "Double XP -päivä", "kuvaus": "Saat tuplat XP:t 24h", "hinta": 2000, "kertakäyttöinen": True, "emoji": "⚡", "tarjousprosentti": 50},
    {"nimi": "Custom rooli", "kuvaus": "Saat oman roolin", "hinta": 5000, "kertakäyttöinen": True, "emoji": "🎨", "tarjousprosentti": 20},
    {"nimi": "VIP-chat", "kuvaus": "Pääsy VIP-kanavalle", "hinta": 3000, "kertakäyttöinen": False, "emoji": "💎", "tarjousprosentti": 10},
    {"nimi": "VIP-rooli (7 päivää)", "kuvaus": "Saat VIP-roolin viikoksi", "hinta": 2500, "kertakäyttöinen": True, "emoji": "👑", "tarjousprosentti": 10},
    {"nimi": "Oma komento", "kuvaus": "Saat tehdä oman /komennon", "hinta": 6000, "kertakäyttöinen": True, "emoji": "🛠️", "tarjousprosentti": 25},
    {"nimi": "Oma kanava", "kuvaus": "Saat oman tekstikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "📢", "tarjousprosentti": 25},
    {"nimi": "Oma puhekanava", "kuvaus": "Saat oman äänikanavan", "hinta": 7000, "kertakäyttöinen": True, "emoji": "🎙️", "tarjousprosentti": 25},
    {"nimi": "Valitse värisi", "kuvaus": "Saat värillisen roolin (esim. sininen)", "hinta": 1500, "kertakäyttöinen": False, "emoji": "🧬", "tarjousprosentti": 30},
    {"nimi": "Valitse emoji", "kuvaus": "Bot reagoi viesteihisi valitsemallasi emojilla 7 päivää", "hinta": 3500, "kertakäyttöinen": True, "emoji": "🤖", "tarjousprosentti": 30},
    {"nimi": "Soundboard-oikeus", "kuvaus": "Käyttöoikeus puhekanavan soundboardiin 3 päivää", "hinta": 4000, "kertakäyttöinen": True, "emoji": "🔊", "tarjousprosentti": 10}
]

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
async def paivita_tarjous_automatisoitu():
    try:
        nykyinen = nykyinen_periodi()
        try:
            with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
                data = json.load(f)
                paivamaara = datetime.fromisoformat(data.get("paivamaara"))
                edellinen = (paivamaara.date() - datetime(2025, 1, 1).date()).days // 4
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
    nyt = datetime.now(timezone.utc).date()
    periodi = nykyinen_periodi()

    try:
        with open(TARJOUS_TIEDOSTO, "r", encoding="utf-8") as f:
            data = json.load(f)
            paivamaara = datetime.fromisoformat(data.get("paivamaara"))
            edellinen_periodi = (paivamaara.date() - datetime(2025, 1, 1).date()).days // 4

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
        json.dump({"paivamaara": datetime.now(timezone.utc).isoformat(), "tuote": tarjous}, f, ensure_ascii=False, indent=2)

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
    except Exception:
        return 0

    kuponki = data.get(koodi)
    if not kuponki:
        return 0

    try:
        vanhentuu = datetime.fromisoformat(kuponki["vanhentuu"])
        if datetime.now() > vanhentuu:
            return 0
    except Exception:
        return 0

    maxkayttoja = kuponki.get("maxkayttoja", -1)
    if maxkayttoja != -1 and kuponki.get("kayttoja", 0) >= maxkayttoja:
        return 0

    sallitut_tuotteet = [t.strip().lower() for t in kuponki.get("tuotteet", [])]
    if sallitut_tuotteet and tuotteen_nimi not in sallitut_tuotteet:
        return 0

    sallitut_kayttajat_raw = kuponki.get("kayttajat", [])
    if sallitut_kayttajat_raw:
        kayttaja_ids = [v for v in sallitut_kayttajat_raw if not v.startswith("rooli:")]
        rooli_ids = [v.replace("rooli:", "") for v in sallitut_kayttajat_raw if v.startswith("rooli:")]

        kuuluu_rooliin = any(discord.utils.get(interaction.user.roles, id=int(rid)) for rid in rooli_ids)
        on_hyvaksytty_kayttaja = str(user_id) in kayttaja_ids

        if not on_hyvaksytty_kayttaja and not kuuluu_rooliin:
            return 0

    kayttaja_key = f"user:{user_id}"
    kayttaja_kayttoja = kuponki.setdefault("kayttajat_dict", {}).get(kayttaja_key, 0)

    maxkayttoja_per_jasen = kuponki.get("maxkayttoja_per_jasen", -1)
    if maxkayttoja_per_jasen != -1 and kayttaja_kayttoja >= maxkayttoja_per_jasen:
        return 0

    kuponki["kayttoja"] = kuponki.get("kayttoja", 0) + 1
    kuponki["kayttajat_dict"][kayttaja_key] = kayttaja_kayttoja + 1
    data[koodi] = kuponki

    try:
        with open(polku, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return kuponki.get("prosentti", 0)

def nykyinen_periodi():
    alku = datetime(2025, 1, 1, tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - alku
    periodi = (delta.days // 4) % (len(kauppa_tuotteet) // 2)
    return periodi

from datetime import datetime, timedelta, timezone

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

from discord.ui import Modal, TextInput

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
        await interaction.followup.send("⚡ Sait Double XP -roolin 24 tunniksi!", ephemeral=True)

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

            roolit = interaction.guild.roles
            referenssi_rooli = discord.utils.get(roolit, name="-- Osto roolit --")
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

            async def poista_reaktio():
                await asyncio.sleep(7 * 24 * 60 * 60)
                auto_react_users.pop(str(interaction.user.id), None)
                await interaction.user.send("⌛ Emoji-oikeutesi on päättynyt.")
            bot.loop.create_task(poista_reaktio())
            lisatieto = f" (emoji: {emoji_valinta})"
        return lisatieto

    elif nimi == "soundboard-oikeus":
        rooli = discord.utils.get(interaction.guild.roles, name="SoundboardAccess")
        if not rooli:
            rooli = await interaction.guild.create_role(name="SoundboardAccess")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("🔊 Soundboard-oikeus myönnetty puhekanavalle 3 päiväksi!", ephemeral=True)

        async def poista_soundboard():
            await asyncio.sleep(3 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send("⌛ Soundboard-oikeus on päättynyt.")
            except:
                pass
        bot.loop.create_task(poista_soundboard())
        return lisatieto

    elif nimi == "vip-rooli":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            await interaction.followup.send("⚠️ VIP-roolia ei löytynyt palvelimelta. Luo se ensin manuaalisesti!", ephemeral=True)
            return ""
        
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("👑 VIP-rooli myönnetty sinulle 7 päiväksi!", ephemeral=True)

        async def poista_rooli_viiveella():
            await asyncio.sleep(7 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send("⌛ VIP-roolisi on nyt vanhentunut.")
            except:
                pass
        bot.loop.create_task(poista_rooli_viiveella())

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

    if tuote["kertakäyttöinen"] and any(o.get("nimi") == tuote["nimi"] for o in ostot[user_id]):
        await interaction.response.send_message("Olet jo ostanut tämän kertakäyttöisen tuotteen.", ephemeral=True)
        return

    if kuponki:
        alennus_prosentti = tarkista_kuponki(kuponki, tuote["nimi"], user_id)
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
            await lokikanava.send(
                f"🧾 {interaction.user.mention} osti tuotteen **{tuote['nimi']}** ({hinta_alennettu} XP){lisatieto}" + (f"\n📄 Kuponki: **{kuponki}** (-{alennus_prosentti}%)" if kuponki else "")
            )
    except Exception as e:
        print(f"Lokitus epäonnistui: {e}")