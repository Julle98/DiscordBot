import discord
import os
import json
from io import BytesIO
import zipfile
from pathlib import Path
from discord import ui
from dotenv import load_dotenv
from collections import Counter
from bot.utils.bot_setup import bot

load_dotenv()

JSON_DIR = Path(os.getenv("JSON_DIR"))
JSON_DIRS = Path(os.getenv("JSON_DIRS"))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
BACKUP_JSON_PATH = Path(os.getenv("BACKUP_JSON_PATH", "backup"))

TIEDOSTOT = {
    "Tehtävät": JSON_DIR / "tasks.json",
    "Ostokset": JSON_DIRS / "ostot.json",
    "Streakit": JSON_DIR / "streaks.json",
    "Tarjous": JSON_DIRS / "tarjous.json",
    "XP-data": XP_JSON_PATH / "users_xp.json",
    "XP-streakit": XP_JSON_PATH / "users_streak.json",
}

KATEGORIAT = list(TIEDOSTOT.keys()) + ["Moderointi", "Toiminta"]

def varmuuskopioi_json_tiedostot():
    BACKUP_JSON_PATH.mkdir(parents=True, exist_ok=True)
    for nimi, polku in TIEDOSTOT.items():
        if polku.exists():
            backup_polku = BACKUP_JSON_PATH / f"{nimi}_{int(discord.utils.utcnow().timestamp())}.json"
            try:
                with open(polku, "r", encoding="utf-8") as src, open(backup_polku, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"Varmuuskopiointivirhe tiedostolle {nimi}:", e)

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

async def hae_ostosmäärä(user_id: str):
    channel = bot.get_channel(int(os.getenv("OSTOSLOKI_KANAVA_ID")))
    if not channel:
        return 0
    count = 0
    async for msg in channel.history(limit=500):
        if f"<@{user_id}>" in msg.content:
            count += 1
    return count

async def laske_käyttäjän_komennot(user_id: int):
    laskuri = Counter()
    logi_kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    async for msg in logi_kanava.history(limit=1000):
        if f"({user_id})" in msg.content:
            laskuri[user_id] += 1
    return laskuri[user_id]

async def muodosta_embed_käyttäjälle(user: discord.User):
    varmuuskopioi_json_tiedostot()
    uid = str(user.id)
    embed = discord.Embed(title=f"📦 Bottidata: {user.display_name}", color=discord.Color.teal())
    try:
        with open(TIEDOSTOT["XP-data"], encoding="utf-8") as f:
            data = json.load(f).get(uid, {})
            xp = data.get("xp", 0)
            level = data.get("level", 0)
        embed.add_field(name="✨ XP", value=f"{xp} XP (Taso {level})", inline=False)
    except:
        embed.add_field(name="✨ XP", value="Ei saatavilla", inline=False)

    try:
        with open(TIEDOSTOT["XP-streakit"], encoding="utf-8") as f:
            streak_data = json.load(f).get(uid, {})
            streak = streak_data.get("streak", 0)
        embed.add_field(name="🔥 Streak", value=f"{streak} päivää", inline=False)
    except:
        embed.add_field(name="🔥 Streak", value="Ei saatavilla", inline=False)

    tehtävät = await hae_tehtävien_määrä(uid)
    embed.add_field(name="📘 Suoritetut tehtävät", value=f"{tehtävät} kpl", inline=False)
    ostot = await hae_ostosmäärä(uid)
    embed.add_field(name="🛒 Ostokset", value=f"{ostot} kpl", inline=False)
    komennot = await laske_käyttäjän_komennot(user.id)
    embed.add_field(name="💬 Käytetyt komennot", value=f"{komennot} kpl", inline=False)

    aktiivisuus = xp + tehtävät * 10 + ostot * 5 + komennot * 3
    embed.add_field(name="📊 Aktiivisuuspisteet", value=f"{aktiivisuus} pistettä", inline=False)
    embed.set_footer(text="Tiedot lasketaan reaaliaikaisesti kanavien historiasta.")
    return embed

class DataValintaView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        for nimi in KATEGORIAT:
            self.add_item(ui.Button(label=nimi, style=discord.ButtonStyle.primary, custom_id=nimi))

    async def interaction_check(self, interaction):
        valinta = interaction.data["custom_id"]
        await interaction.response.edit_message(content=f"🔍 Valitsit kategorian: {valinta}", view=KategoriaView(valinta, self.user))
        return False

class KategoriaView(ui.View):
    def __init__(self, nimi, user):
        super().__init__(timeout=300)
        self.nimi = nimi
        self.user = user
        self.add_item(KatsoNappi(nimi, user))
        if nimi in TIEDOSTOT:
            self.add_item(LataaNappi(nimi, user))
            self.add_item(PoistaNappi(nimi, user))
        elif nimi == "Moderointi":
            self.add_item(IlmoitaVirheNappi(user))
        self.add_item(ui.Button(label="← Takaisin", style=discord.ButtonStyle.secondary, custom_id="takaisin"))

    async def interaction_check(self, interaction):
        if interaction.data["custom_id"] == "takaisin":
            await interaction.response.edit_message(content="📁 Valitse kategoria:", view=DataValintaView(self.user))
            return False
        return True

class KatsoNappi(ui.Button):
    def __init__(self, nimi, user):
        super().__init__(label="Katso tiedot", style=discord.ButtonStyle.secondary)
        self.nimi = nimi
        self.user = user

    async def callback(self, interaction):
        if self.nimi == "Moderointi":
            modlog = bot.get_channel(MOD_LOG_CHANNEL_ID)
            lista = []
            async for msg in modlog.history(limit=1000):
                if f"ID: {self.user.id}" in msg.content:
                    lista.append(msg.content)
            if not lista:
                await interaction.response.send_message("Ei varoituksia.", ephemeral=True)
                return
            vastaus = "\n".join([f"{i+1}. {v.split(' | Syy: ')[-1].split(' |')[0]}" for i, v in enumerate(lista)])
            await interaction.response.send_message(f"{self.user.mention} on saanut {len(lista)} varoitusta:\n{vastaus}", ephemeral=True)

        elif self.nimi == "Toiminta":
            viestimäärät = {}
            kanavat = [c for c in interaction.guild.text_channels if c.permissions_for(self.user).read_messages]
            for kanava in kanavat:
                try:
                    count = sum(1 async for msg in kanava.history(limit=1000) if msg.author == self.user)
                    if count > 0:
                        viestimäärät[kanava] = count
                except discord.Forbidden:
                    continue
            if not viestimäärät:
                await interaction.response.send_message("Ei viestejä löytynyt.", ephemeral=True)
                return
            aktiivisin = max(viestimäärät, key=viestimäärät.get)
            määrä = viestimäärät[aktiivisin]
            await interaction.response.send_message(
                f"**{self.user.display_name}** on lähettänyt eniten viestejä kanavalle {aktiivisin.mention} ({määrä} viestiä).",
                ephemeral=True
            )

        else:
            embed = await muodosta_embed_käyttäjälle(self.user)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class LataaNappi(ui.Button):
    def __init__(self, nimi, user):
        super().__init__(label="Lataa tiedosto", style=discord.ButtonStyle.success)
        self.nimi = nimi
        self.user = user

    async def callback(self, interaction):
        varmuuskopioi_json_tiedostot()
        path = TIEDOSTOT.get(self.nimi)
        if not path or not path.exists():
            await interaction.response.send_message("❌ Tiedostoa ei löytynyt.", ephemeral=True)
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            user_data = data.get(str(self.user.id))
            if not user_data:
                await interaction.response.send_message("ℹ️ Sinulla ei ole dataa tässä tiedostossa.", ephemeral=True)
                return
            buffer = BytesIO()
            json.dump({str(self.user.id): user_data}, buffer, ensure_ascii=False, indent=2)
            buffer.seek(0)
            await interaction.response.send_message(
                file=discord.File(buffer, filename=f"{self.nimi}_{self.user.id}.json"),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("⚠️ Lataus epäonnistui.", ephemeral=True)

class PoistaNappi(ui.Button):
    def __init__(self, nimi, user):
        super().__init__(label="Poista tiedot", style=discord.ButtonStyle.danger)
        self.nimi = nimi
        self.user = user

    async def callback(self, interaction):
        await interaction.response.send_modal(PoistovarmistusModal(self.nimi, [TIEDOSTOT[self.nimi]], self.user))

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

    def __init__(self, nimi: str, polut: list[Path], user: discord.User):
        super().__init__()
        self.nimi = nimi
        self.polut = polut
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        if self.vahvistus.value.lower() != "vahvista":
            await interaction.response.send_message("❌ Vahvistus epäonnistui. Tietoja ei poistettu.", ephemeral=True)
            return
        for polku in self.polut:
            try:
                if polku.exists():
                    with open(polku, "r+", encoding="utf-8") as f:
                        data = json.load(f)
                        if str(self.user.id) in data:
                            del data[str(self.user.id)]
                            f.seek(0)
                            json.dump(data, f, indent=2, ensure_ascii=False)
                            f.truncate()
            except Exception as e:
                print("Poistovirhe:", e)
        await interaction.response.send_message(f"🗑️ Poistettiin tiedot kohteesta: {self.nimi}", ephemeral=True)
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