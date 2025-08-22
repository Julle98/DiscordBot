import discord
import asyncio
import os
import json
import random
from datetime import datetime, timedelta, timezone
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
import discord

def start_store_loops():
    if not tarkista_ostojen_kuukausi.is_running():
        tarkista_ostojen_kuukausi.start()
    if not paivita_tarjous_automatisoitu.is_running():
        paivita_tarjous_automatisoitu.start()

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
    {"nimi": "Soundboard-oikeus", "kuvaus": "Käyttöoikeus puhekanavan soundboardiin 3 päiväksi", "hinta": 4000, "kertakäyttöinen": True, "emoji": "🔊", "tarjousprosentti": 10}
]

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

def onko_tuote_voimassa(user_id: str, tuotteen_nimi: str) -> bool:
    ostot = lue_ostokset()
    kayttajan_ostot = ostot.get(user_id, [])
    for o in kayttajan_ostot:
        if puhdista_tuotteen_nimi(o.get("nimi", "")) == puhdista_tuotteen_nimi(tuotteen_nimi):
            return True
    return False

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

        async def poista_erikoisemoji():
            await asyncio.sleep(3 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send("⌛ Erikoisemoji-roolisi on vanhentunut.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
            except:
                pass
        bot.loop.create_task(poista_erikoisemoji())

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
                await interaction.user.send("⏳ Double XP -roolisi on vanhentunut.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
            except:
                pass
        bot.loop.create_task(poista_rooli_viiveella())

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

        async def poista_custom_rooli():
            await asyncio.sleep(7 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send(f"⌛ Custom-roolisi **{rooli.name}** on poistettu.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
                await rooli.delete()
            except:
                pass
        bot.loop.create_task(poista_custom_rooli())

        return f" (rooli: {roolin_nimi})"

    elif nimi == "vip-chat":
        rooli = discord.utils.get(interaction.guild.roles, name="VIP")
        if not rooli:
            rooli = await interaction.guild.create_role(name="VIP")
        await interaction.user.add_roles(rooli)
        await interaction.followup.send("💎 Sait pääsyn VIP-chattiin!", ephemeral=True)

        async def poista_vip_chat():
            await asyncio.sleep(7 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send("⌛ VIP-chat-oikeutesi on päättynyt.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
            except:
                pass
        bot.loop.create_task(poista_vip_chat())

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
        
        async def poista_varirooli():
            await asyncio.sleep(7 * 24 * 60 * 60)
            try:
                await interaction.user.remove_roles(rooli)
                await interaction.user.send(f"🎨 Väriroolisi **{rooli.name}** on poistettu.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
                await rooli.delete()
            except:
                pass
        bot.loop.create_task(poista_varirooli())

    elif nimi == "valitse emoji":
        emoji_valinta = await kysy_kayttajalta(interaction, "Millä emojilla botin tulisi reagoida viesteihisi?")
        if emoji_valinta:
            auto_react_users[str(interaction.user.id)] = emoji_valinta
            await interaction.followup.send(f"🤖 Bot reagoi viesteihisi emojilla {emoji_valinta} seuraavat 7 päivää!", ephemeral=True)

            async def poista_reaktio():
                await asyncio.sleep(7 * 24 * 60 * 60)
                auto_react_users.pop(str(interaction.user.id), None)
                await interaction.user.send("⌛ Emoji-oikeutesi on päättynyt.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
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
                await interaction.user.send("⌛ Soundboard-oikeus on päättynyt.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
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
                await interaction.user.send("⌛ VIP-roolisi on nyt vanhentunut.\n 🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉")
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

    if onko_tuote_voimassa(user_id, tuote["nimi"]):
        await interaction.response.send_message(
            f"🚫 Tuote **{tuote['nimi']}** on jo käytössäsi. Odota, että oikeus päättyy ennen kuin ostat uudestaan.",
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
