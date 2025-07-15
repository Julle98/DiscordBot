import discord
import os
import json
from pathlib import Path
from discord import ui
from dotenv import load_dotenv
from bot.utils.bot_setup import bot

load_dotenv()

JSON_DIR = Path(os.getenv("JSON_DIR"))
JSON_DIRS = Path(os.getenv("JSON_DIRS"))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

TIEDOSTOT = {
    "Tehtävät": JSON_DIR / "tasks.json",
    "Ostokset": JSON_DIRS / "ostot.json",
    "Streakit": JSON_DIR / "streaks.json",
    "Tarjous": JSON_DIRS / "tarjous.json",
    "XP-data": XP_JSON_PATH / "users_xp.json",
    "XP-streakit": XP_JSON_PATH / "users_streak.json",
}

def muodosta_embed_käyttäjälle(user: discord.User):
    tiedot = {}
    for nimi, polku in TIEDOSTOT.items():
        try:
            with open(polku, encoding="utf-8") as f:
                data = json.load(f)
                user_data = data.get(str(user.id), "Ei dataa")
                if isinstance(user_data, (dict, list)):
                    tiedot[nimi] = f"{len(json.dumps(user_data))} merkkiä"
                else:
                    tiedot[nimi] = str(user_data)
        except:
            tiedot[nimi] = "❌ Ei luettavissa"

    embed = discord.Embed(
        title=f"📦 Bottidata: {user.display_name}",
        description="Yhteenveto käyttäjän tiedoista",
        color=discord.Color.teal()
    )
    for nimi, arvo in tiedot.items():
        embed.add_field(name=nimi, value=arvo, inline=False)
    embed.set_footer(text="Voit ladata tai poistaa tiedot alapuolelta.")
    return embed

class DataValintaView(ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.add_item(DataValintaDropdown(user))

class DataValintaDropdown(ui.Select):
    def __init__(self, user: discord.User):
        self.user = user
        options = [
            discord.SelectOption(label="Lataa kaikki tiedot", value="lataa_kaikki", emoji="📥")
        ]

        for nimi in TIEDOSTOT:
            options.append(discord.SelectOption(label=f"Lataa: {nimi}", value=f"lataa_{nimi}", emoji="📄"))
            options.append(discord.SelectOption(label=f"Poista: {nimi}", value=f"poista_{nimi}", emoji="🗑️"))

        options.append(discord.SelectOption(label="⚠️ Poista kaikki", value="poista_kaikki"))

        super().__init__(placeholder="Valitse toiminto...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        valinta = self.values[0]

        if valinta == "lataa_kaikki":
            await self.lähetä_zip(interaction)
        elif valinta.startswith("lataa_"):
            nimi = valinta.replace("lataa_", "")
            await self.lataa_tiedosto(interaction, nimi)
        elif valinta == "poista_kaikki":
            await interaction.response.send_modal(PoistovarmistusModal("Kaikki tiedot", list(TIEDOSTOT.values()), self.user))
        elif valinta.startswith("poista_"):
            nimi = valinta.replace("poista_", "")
            await interaction.response.send_modal(PoistovarmistusModal(nimi, [TIEDOSTOT[nimi]], self.user))

    async def lataa_tiedosto(self, interaction, nimi):
        tiedosto = TIEDOSTOT.get(nimi)
        if tiedosto and tiedosto.exists():
            await interaction.followup.send(file=discord.File(tiedosto), ephemeral=True)
        else:
            await interaction.followup.send("❌ Tiedostoa ei löytynyt.", ephemeral=True)

    async def lähetä_zip(self, interaction):
        import zipfile, io
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for nimi, polku in TIEDOSTOT.items():
                if polku.exists():
                    zf.write(polku, arcname=polku.name)
        zip_buffer.seek(0)
        await interaction.followup.send(file=discord.File(fp=zip_buffer, filename="bottidata.zip"), ephemeral=True)

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