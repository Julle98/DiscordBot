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
    "XP-streakit": XP_JSON_PATH / "users_streak.json",
}

KATEGORIAT = list(TIEDOSTOT.keys()) + ["Moderointi", "Toiminta"]

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

async def laske_käyttäjän_komennot(user_id: int):
    kanava = bot.get_channel(LOG_CHANNEL_ID)
    count = 0
    async for msg in kanava.history(limit=1000):
        if "📝 Komento:" in msg.content and f"({user_id})" in msg.content:
            count += 1
    return count

async def hae_käyttäjän_komennot_lista(user_id: int):
    log_channel = bot.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
    laskuri = Counter()

    if not log_channel:
        return {}

    async for msg in log_channel.history(limit=1000):
        if f"({user_id})" in msg.content:
            if (match := re.search(r"Komento: `(.+?)`", msg.content)):
                komento = match.group(1)
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

async def muodosta_kategoria_embed(kategoria: str, user: discord.User):
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

        if not user_data:
            embed.add_field(name="ℹ️ Ei tietoja", value="Käyttäjällä ei ole dataa tässä kategoriassa.", inline=False)
        else:
            if kategoria == "Tehtävät":
                tehtäväviestit = await hae_tehtäväviestit(uid)
                määrä = len(tehtäväviestit)

                if määrä > 0:
                    embed.add_field(
                        name="📊 Tehtävien määrä",
                        value=f"{määrä} kpl",
                        inline=False
                    )
                    for i, tehtävä in enumerate(tehtäväviestit[:5]):
                        kuvaus = tehtävä.get("task", "Tuntematon tehtävä")
                        aikaleima = tehtävä.get("timestamp")
                        try:
                            aika = datetime.fromisoformat(aikaleima).strftime("%d.%m.%Y %H:%M") if aikaleima else "?"
                        except:
                            aika = "?"
                        embed.add_field(
                            name=f"📘 Tehtävä {i+1}",
                            value=f"{kuvaus}\n🕒 {aika}",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="📘 Tehtävät",
                        value="Ei löydettyjä tehtäväviestejä.",
                        inline=False
                    )

            elif kategoria == "Ostokset":
                ostoslista = user_data.get("ostot", [])
                if isinstance(ostoslista, list) and ostoslista:
                    for ostos in ostoslista[:5]:
                        nimi = ostos.get("nimi", "Tuntematon tuote")
                        aika = ostos.get("aika")
                        pvm = datetime.fromtimestamp(aika).strftime("%d.%m.%Y %H:%M") if aika else "?"
                        embed.add_field(name=f"🛒 {nimi}", value=f"🗓️ {pvm}", inline=False)
                else:
                    embed.add_field(name="🛒 Ostokset", value="Ei ostoksia kirjattuna.", inline=False)

            elif kategoria == "Streakit":
                streak = user_data.get("streak", 0)
                embed.add_field(name="🔥 Streak", value=f"{streak} päivää", inline=False)

            elif kategoria == "Tarjous":
                tarjousviestit = await hae_tarjousviestit(uid)
                if tarjousviestit:
                    for viesti in tarjousviestit[:5]:
                        aika = viesti.created_at.strftime("%d.%m.%Y %H:%M")
                        teksti = viesti.content.split(" (")[0]  
                        embed.add_field(
                            name="🎁 Tarjous",
                            value=f"{teksti}\n🗓️ {aika}",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="🎁 Tarjous",
                        value="Ei löydettyjä tarjousviestejä.",
                        inline=False
                    )

            elif kategoria == "XP-data":
                xp = user_data.get("xp", 0)
                level = user_data.get("level", 0)
                embed.add_field(name="✨ XP", value=f"{xp} XP\n📈 Taso {level}", inline=False)

            elif kategoria == "XP-streakit":
                streak = user_data.get("streak", 0)
                alku_aika = user_data.get("alku")
                historia = user_data.get("historia", [])

                pvm = datetime.fromtimestamp(alku_aika).strftime("%d.%m.%Y %H:%M") if alku_aika else "Tuntematon"
                embed.add_field(
                    name="⚡ XP-Streak",
                    value=f"🔥 {streak} päivää\n📅 Alkoi: {pvm}",
                    inline=False
                )

            if historia:
                viimeisin = historia[-1]
                viimeisin_pvm = datetime.fromtimestamp(viimeisin["timestamp"]).strftime("%d.%m.%Y %H:%M")
                embed.add_field(name="📊 Viimeisin päivitys", value=viimeisin_pvm, inline=False)
                embed.add_field(name="📈 Muutoksia yhteensä", value=f"{len(historia)} kpl", inline=False)
            else:
                embed.add_field(name="📊 Historia", value="Ei muutoksia tallennettu.", inline=False)

    elif kategoria == "Moderointi":
        varoituskanava = bot.get_channel(MODLOG_CHANNEL_ID)
        mutekanava = bot.get_channel(MODLOG_CHANNEL_ID)
        varoitukset = []
        mute_count = 0

        async for msg in varoituskanava.history(limit=1000):
            if f"ID: {user.id}" in msg.content:
                varoitukset.append(msg)

        if mutekanava:
            async for msg in mutekanava.history(limit=1000):
                if f"{user.mention}" in msg.content and "🔇 **Jäähy asetettu**" in msg.content:
                    mute_count += 1

        if varoitukset:
            for i, viesti in enumerate(varoitukset[:5]):
                syy = viesti.content.split(" | Syy: ")[-1].split(" |")[0]
                aika = viesti.created_at.strftime("%d.%m.%Y %H:%M")
                embed.add_field(name=f"⚠️ Varoitus {i+1}", value=f"📝 {syy}\n🕒 {aika}", inline=False)
        else:
            embed.add_field(name="✅ Ei varoituksia", value="Käyttäjällä ei ole merkintöjä.", inline=False)

        embed.add_field(name="🔇 Jäähyt (mute)", value=f"{mute_count} kertaa", inline=False)

    elif kategoria == "Toiminta":
        tehtävät = await hae_tehtävien_määrä(uid)
        ostot = await hae_ostosmäärä(uid)
        komentolista = await hae_käyttäjän_komennot_lista(user.id)
        komennot = sum(komentolista.values())

        embed.add_field(name="📘 Tehtävät", value=f"{tehtävät} kpl", inline=True)
        embed.add_field(name="🛒 Ostokset", value=f"{ostot} kpl", inline=True)
        embed.add_field(name="💬 Komennot", value=f"{komennot} kpl", inline=True)

        if komentolista:
            rivit = [f"- {nimi} ({määrä}×)" for nimi, määrä in komentolista.most_common(5)]
            embed.add_field(
                name="📚 Käytetyt komennot",
                value="\n".join(rivit),
                inline=False
            )
        else:
            embed.add_field(
                name="📚 Käytetyt komennot",
                value="Ei komentoja havaittu.",
                inline=False
            )

        viimeisin = await hae_viimeisin_aktiivisuusviesti(uid)
        if viimeisin:
            pvm = viimeisin.strftime("%d.%m.%Y %H:%M")
            embed.add_field(name="⏳ Viimeisin aktiivisuus", value=f"{pvm}", inline=False)
        else:
            embed.add_field(name="⏳ Viimeisin aktiivisuus", value="Ei havaittua toimintaa.", inline=False)

    else:
        embed.add_field(name="❓ Tuntematon kategoria", value="Ei sisältöä saatavilla.", inline=False)

    embed.set_footer(text="📁 Kategorianäkymä • Tiedot päivittyvät reaaliaikaisesti")
    return embed

class DataValintaView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user
        for nimi in KATEGORIAT:
            self.add_item(ui.Button(label=nimi, style=discord.ButtonStyle.primary, custom_id=nimi))

    async def interaction_check(self, interaction: discord.Interaction):
        valinta = interaction.data["custom_id"]

        if valinta == "palaa":
            await interaction.response.edit_message(
                content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
                embed=None,
                view=KategoriaView(None, self.user)
            )
            return False

        uusi_embed = await muodosta_kategoria_embed(valinta, self.user)
        await interaction.response.edit_message(
            content=f"📁 Näytetään tiedot kategoriasta: **{valinta}**",
            embed=uusi_embed,
            view=KategoriaView(valinta, self.user)
        )
        return False

class KategoriaNappi(ui.Button):
    def __init__(self, nimi, user):
        super().__init__(label=nimi, style=discord.ButtonStyle.primary, custom_id=nimi)
        self.nimi = nimi
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        embed = await muodosta_kategoria_embed(self.nimi, self.user)
        await interaction.response.edit_message(
            content=f"📁 Näytetään tiedot kategoriasta: **{self.nimi}**",
            embed=embed,
            view=KategoriaView(self.nimi, self.user)
        )

class KategoriaView(ui.View):
    def __init__(self, valittu_kategoria, user):
        super().__init__(timeout=300)
        self.user = user
        self.valittu = valittu_kategoria

        if not valittu_kategoria:
            for nimi in KATEGORIAT:
                self.add_item(KategoriaNappi(nimi, self.user))
        else:
            self.add_item(LataaNappi(valittu_kategoria, self.user))
            self.add_item(PoistaNappi(valittu_kategoria, self.user))
            self.add_item(PalaaNappi(user))

class KatsoNappi(ui.Button):
    def __init__(self, user):
        super().__init__(label="Katso tiedot", style=discord.ButtonStyle.secondary)
        self.user = user

    async def callback(self, interaction):
        await interaction.response.edit_message(
            content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
            embed=None,
            view=KategoriaView(None, self.user)
        )

class PalaaNappi(ui.Button):
    def __init__(self, user):
        super().__init__(label="🔙 Palaa alkuun", style=discord.ButtonStyle.secondary)
        self.user = user

    async def callback(self, interaction):
        await interaction.response.edit_message(
            content="📁 Valitse kategoria, jonka tiedot haluat nähdä:",
            embed=None,
            view=KategoriaView(None, self.user)
        )

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