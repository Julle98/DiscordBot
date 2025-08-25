import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.vault_utils import salaa, pura
from bot.utils.error_handler import CommandErrorHandler
from discord.ui import Modal, View, Button

MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))

async def laheta_lokiviesti(bot, sisalto: str):
    kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if kanava:
        await kanava.send(sisalto)

class KirjautumisModal(Modal):
    def __init__(self, sisalto, salasana, aikaleima):
        super().__init__(title="🔐 Holvi Kirjautuminen")
        self.add_item(discord.ui.TextInput(label="Sisältö", default=sisalto, style=discord.TextStyle.paragraph, required=False))
        self.add_item(discord.ui.TextInput(label="Salasana", default=salasana, required=False))
        self.add_item(discord.ui.TextInput(label="Aikaleima", default=aikaleima, required=False))

class KirjautumisView(View):
    def __init__(self, user_id, kirjautuneet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.kirjautuneet = kirjautuneet

    @discord.ui.button(label="✅ Merkitse kirjautuneeksi", style=discord.ButtonStyle.success)
    async def merkitse(self, interaction: discord.Interaction, button: Button):
        self.kirjautuneet.add(self.user_id)
        await laheta_lokiviesti(interaction.client, f"✅ <@{self.user_id}> merkitsi itsensä kirjautuneeksi holviin.")
        await interaction.response.send_message("📌 Kirjautuminen merkattu onnistuneesti!", ephemeral=True)

    @discord.ui.button(label="❌ Sulje", style=discord.ButtonStyle.danger)
    async def sulje(self, interaction: discord.Interaction, button: Button):
        await laheta_lokiviesti(interaction.client, f"❌ <@{self.user_id}> sulki modalin ilman kirjautumismerkintää.")
        await interaction.response.send_message("🔒 Modal suljettu.", ephemeral=True)

HOLVI_POLKU = os.getenv("HOLVI_POLKU")

def lataa_holvi():
    if not os.path.exists(HOLVI_POLKU):
        return {}
    with open(HOLVI_POLKU, "r", encoding="utf-8") as f:
        return json.load(f)

def tallenna_holvi(data):
    os.makedirs(os.path.dirname(HOLVI_POLKU), exist_ok=True)
    with open(HOLVI_POLKU, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Vault(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.holvi = lataa_holvi()
        self.kirjautuneet = set()

    @app_commands.command(name="holvi_tallenna", description="Tallenna sisältö holviin salasanalla.")
    @app_commands.describe(salasana="Salasana holviin", sisalto="Tallennettava sisältö")
    @app_commands.checks.has_role("24G")
    async def holvi_tallenna(self, interaction: discord.Interaction, salasana: str, sisalto: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/holvi_tallenna")
        await kirjaa_ga_event(self.bot, interaction.user.id, "holvi_tallenna_komento")

        kayttajan_holvit = [key for key, val in self.holvi.items() if val["kayttaja"] == interaction.user.id]
        max_holvit = 3

        member = interaction.guild.get_member(interaction.user.id)
        if member and any(role.name == "HolviPlus" for role in member.roles):
            max_holvit = 5

        if len(kayttajan_holvit) >= max_holvit:
            await interaction.response.send_message(f"Sinulla on jo {len(kayttajan_holvit)} holvia. Enimmäismäärä on {max_holvit}. 🚫", ephemeral=True)
            return

        self.holvi[salasana] = {
            "sisalto": salaa(sisalto, salasana),
            "kayttaja": interaction.user.id
        }
        tallenna_holvi(self.holvi)

        await laheta_lokiviesti(self.bot, f"Holvi luotu käyttäjältä <@{interaction.user.id}> salasanalla `{salasana}`. 📂")
        await interaction.response.send_message(
            f"Sisältö tallennettu holviin onnistuneesti! ✅\nMuista salasanasi: `{salasana}` 🔐", ephemeral=True
        )

    @app_commands.command(name="holvi_paivita", description="Lisää tekstiä olemassa olevaan holviin.")
    @app_commands.describe(salasana="Holvin salasana", lisa="Lisättävä teksti")
    @app_commands.checks.has_role("24G")
    async def holvi_paivita(self, interaction: discord.Interaction, salasana: str, lisa: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/holvi_paivita")
        await kirjaa_ga_event(self.bot, interaction.user.id, "holvi_paivita_komento")

        entry = self.holvi.get(salasana)
        if not entry:
            await interaction.response.send_message("Salasana ei vastaa mitään holvia. ❌", ephemeral=True)
            return

        if entry["kayttaja"] != interaction.user.id:
            await interaction.response.send_message("Et voi muokata toisen käyttäjän holvia. ⛔", ephemeral=True)
            return

        try:
            nykyinen = pura(entry["sisalto"], salasana)
        except Exception:
            await interaction.response.send_message("Salasanan purku epäonnistui. ❌", ephemeral=True)
            return

        entry["sisalto"] = salaa(nykyinen + f"\n{lisa}", salasana)
        tallenna_holvi(self.holvi)

        aikaleima = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await laheta_lokiviesti(self.bot, f"[{aikaleima}] ✏️ <@{interaction.user.id}> lisäsi tekstiä holviin salasanalla `{salasana}`.")
        await interaction.response.send_message("Teksti lisätty holviin onnistuneesti! ✅", ephemeral=True)

    @app_commands.command(name="holvi_hae", description="Hae sisältö holvista salasanalla ja vaihda tai poista holvi.")
    @app_commands.describe(salasana="Nykyinen salasana", uusi_salasana="(Ei avaa holvia) uusi salasana holville", poista="Poista holvi salasanalla (True/False)")
    @app_commands.checks.has_role("24G")
    async def holvi_hae(self, interaction: discord.Interaction, salasana: str, uusi_salasana: str = None, poista: bool = False):
        await kirjaa_komento_lokiin(self.bot, interaction, "/holvi_hae")
        await kirjaa_ga_event(self.bot, interaction.user.id, "holvi_hae_komento")

        entry = self.holvi.get(salasana)
        if not entry:
            await interaction.response.send_message("Salasana ei vastaa mitään tallennettua sisältöä. ❌", ephemeral=True)
            return

        if entry["kayttaja"] != interaction.user.id:
            await interaction.response.send_message("Tämä sisältö ei ole sinun tallentama. ⛔", ephemeral=True)
            return

        if poista:
            del self.holvi[salasana]
            tallenna_holvi(self.holvi)
            await laheta_lokiviesti(self.bot, f"<@{interaction.user.id}> poisti holvin salasanalla: `{salasana}`. 🗑️")
            await interaction.response.send_message(f"Holvi salasanalla `{salasana}` poistettu. ✅", ephemeral=True)
            return

        if uusi_salasana:
            try:
                sisalto = pura(entry["sisalto"], salasana)
            except Exception:
                await interaction.response.send_message("Salasanan purku epäonnistui. ❌", ephemeral=True)
                return

            self.holvi[uusi_salasana] = {
                "sisalto": salaa(sisalto, uusi_salasana),
                "kayttaja": entry["kayttaja"]
            }
            del self.holvi[salasana]
            tallenna_holvi(self.holvi)

            await laheta_lokiviesti(self.bot, f"<@{interaction.user.id}> vaihtoi holvin salasanan uuteen: `{uusi_salasana}`. 🔑")

            try:
                await interaction.user.send(f"Salasanasi holviin on vaihdettu onnistuneesti.\nUusi salasana: `{uusi_salasana}` 🔐")
            except discord.Forbidden:
                await interaction.followup.send("Salasanan vaihto onnistui, mutta DM-viestin lähetys epäonnistui (käyttäjän yksityisyysasetukset). ⚠️", ephemeral=True)
            else:
                await interaction.followup.send("Salasanan vaihto onnistui. Vahvistus lähetetty yksityisviestinä. ✅", ephemeral=True)
            return

        try:
            sisalto = pura(entry["sisalto"], salasana)
        except Exception:
            await interaction.response.send_message("Salasanan purku epäonnistui. ❌", ephemeral=True)
            return

        self.kirjautuneet.add(interaction.user.id)
        await interaction.response.send_message(f"Holvin sisältö: {sisalto} 📂", ephemeral=True)

    @app_commands.command(name="holvi_lista", description="Näytä kaikki omat holvit.")
    @app_commands.checks.has_role("24G")
    async def holvi_lista(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/holvi_lista")
        await kirjaa_ga_event(self.bot, interaction.user.id, "holvi_lista_komento")

        kayttajan_holvit = [key for key, val in self.holvi.items() if val["kayttaja"] == interaction.user.id]

        if not kayttajan_holvit:
            await interaction.response.send_message("Sinulla ei ole yhtään holvia. Luo uusi ``/holvi_tallenna`` 📭", ephemeral=True)
            return

        lista = "\n".join(f"🔐 `{key}`" for key in kayttajan_holvit)
        await interaction.response.send_message(f"📋 Holvisi:\n{lista} ", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Vault(bot)
    await bot.add_cog(cog)