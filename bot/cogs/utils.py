from discord.ext import commands
from discord import app_commands
import discord
import os
import random
import asyncio
import pytz
from datetime import datetime
from discord import Interaction
from discord.ui import Modal, View
import re
import uuid
from typing import Optional, Literal
from bot.utils.error_handler import CommandErrorHandler
import json

from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.xp_utils import make_xp_content

HELP_DATA_FILE = os.getenv("HELP_DATA_FILE")

def tallenna_pyyntö(pyyntö_id, käyttäjä_id, aihe, kuvaus, timestamp):
    data = {}
    if os.path.exists(HELP_DATA_FILE):
        with open(HELP_DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

    data[pyyntö_id] = {
        "käyttäjä_id": käyttäjä_id,
        "aihe": aihe,
        "kuvaus": kuvaus,
        "timestamp": timestamp
    }

    with open(HELP_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class HelpResponseModal(discord.ui.Modal, title="Kirjoita palaute käyttäjälle"):
    def __init__(self, toiminto, alkuperainen_embed, alkuperainen_viesti, vastaanottaja):
        super().__init__()
        self.toiminto = toiminto  
        self.embed = alkuperainen_embed
        self.viesti = alkuperainen_viesti
        self.vastaanottaja = vastaanottaja

        self.palaute = discord.ui.TextInput(
            label="Kirjoita palautteesi",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.xp_maara = discord.ui.TextInput(
            label="XP-palkinto (valinnainen)",
            placeholder="Esim. 10",
            required=False
        )

        self.add_item(self.palaute)
        self.add_item(self.xp_maara)

    async def on_submit(self, interaction: discord.Interaction):
        alkuperäinen_id = self.embed.title.split("ID:")[-1].strip() if "ID:" in self.embed.title else "tuntematon"

        xp_arvo = self.xp_maara.value.strip()
        xp_määrä = int(xp_arvo) if xp_arvo.isdigit() else 0
        xp_viesti = None

        if xp_määrä > 0:
            xp_viesti = make_xp_content(self.vastaanottaja.id, xp_määrä)

        try:
            xp_maininta = f"\n\n🎉 Sinulle on myönnetty {xp_määrä} XP-pistettä!" if xp_määrä > 0 else ""
            await self.vastaanottaja.send(
                f"**Vastaus pyyntöösi ({self.toiminto}) – ID: `{alkuperäinen_id}`**\n{self.palaute.value}{xp_maininta}",
                embed=self.embed
            )
        except discord.Forbidden:
            await interaction.response.send_message("Käyttäjälle ei voitu lähettää viestiä (DM estetty).", ephemeral=True)
            await self.viesti.edit(view=None)
            return

        uusi_embed = self.embed.copy()
        emoji = "📬" if self.toiminto == "vastattu" else "✅"
        vari = discord.Color.blurple() if self.toiminto == "vastattu" else discord.Color.green()
        alku_footer = self.embed.footer.text or ""

        footer_teksti = f"{alku_footer} • {self.toiminto.capitalize()}"
        if self.toiminto == "vastattu" and xp_määrä > 0:
            footer_teksti += f" • +{xp_määrä} XP"

        uusi_embed.title = f"{emoji} {self.embed.title}"
        uusi_embed.color = vari
        uusi_embed.set_footer(
            text=footer_teksti,
            icon_url=self.embed.footer.icon_url
        )

        await self.viesti.edit(embed=uusi_embed, view=None)
        await interaction.response.send_message(
            f"Pyyntö on {self.toiminto}. (ID: `{alkuperäinen_id}`)" + (f" 🎉 +{xp_määrä} XP myönnetty käyttäjälle!" if xp_määrä > 0 else ""),
            ephemeral=True
        )

class HelpButtons(discord.ui.View):
    def __init__(self, user, embed):
        super().__init__(timeout=None)
        self.user = user
        self.embed = embed

    @discord.ui.button(label="📥 Avaa ja vastaa", style=discord.ButtonStyle.primary)
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            HelpResponseModal("vastattu", self.embed, interaction.message, self.user)
        )

    @discord.ui.button(label="❌ Sulje", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            HelpResponseModal("suljettu", self.embed, interaction.message, self.user)
        )

class HelpModal(discord.ui.Modal, title="Lähetä lisätietoa"):
    def __init__(self, valinta, target_channel):
        super().__init__()
        self.valinta = valinta
        self.target_channel = target_channel

        self.kuvaus = discord.ui.TextInput(
            label="Kuvaile ongelmaasi/tarpeesi",
            style=discord.TextStyle.paragraph
        )
        self.kuva_linkki = discord.ui.TextInput(
            label="(Valinnainen) Kuvalinkki",
            required=False,
            placeholder="https://... (jos haluat)"
        )
        self.pyyntö_id = discord.ui.TextInput(
            label="(Valinnainen) Pyynnön ID",
            required=False,
            placeholder="Jos viittaat aiempaan pyyntöön"
        )

        self.add_item(self.kuvaus)
        self.add_item(self.kuva_linkki)
        self.add_item(self.pyyntö_id)

    async def on_submit(self, interaction: discord.Interaction):
        uusi_id = str(uuid.uuid4())[:8]
        käytetty_id = self.pyyntö_id.value.strip() if self.pyyntö_id.value.strip() else uusi_id

        embed = discord.Embed(
            title=f"Uusi pyyntö /help-komennolla • ID: {käytetty_id}",
            color=discord.Color.blue(),
        )

        embed.add_field(name="Valinta", value=self.valinta.label, inline=False)
        embed.add_field(name="Kuvaus", value=self.kuvaus.value, inline=False)

        if self.kuva_linkki.value:
            embed.set_image(url=self.kuva_linkki.value)

        embed.set_footer(
            text=f"{interaction.user} ({interaction.user.id})",
            icon_url=interaction.user.display_avatar.url
        )

        tallenna_pyyntö(
            pyyntö_id=käytetty_id,
            käyttäjä_id=interaction.user.id,
            aihe=self.valinta.label,
            kuvaus=self.kuvaus.value,
            timestamp=datetime.utcnow().isoformat()
        )

        self.user = interaction.user
        await self.target_channel.send(embed=embed, view=HelpButtons(self.user, embed))

        await interaction.response.send_message(
            f"Pyyntösi on lähetetty! Kiitos!\nTunnisteesi: `{käytetty_id}` – käytä tätä, jos haluat viitata pyyntöön myöhemmin.",
            ephemeral=True
        )

class HelpDropdown(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=60)
        self.channel = channel

        self.options = [
            discord.SelectOption(label="⚒️ Ongelma", value="ongelma", description="Tekninen ongelma tai bugi."),
            discord.SelectOption(label="❓ Report", value="report", description="Ilmoitus jostain asiattomasta."),
            discord.SelectOption(label="📢 Valitus", value="valitus", description="Virallinen valitus tai palaute."),
            discord.SelectOption(label="💁 Jokin muu", value="muu", description="Yleinen kysymys, idea tai ehdotus."),
            
        ]

        self.select = discord.ui.Select(placeholder="Valitse aihealue", options=self.options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        valinta = next(opt for opt in self.options if opt.value == self.select.values[0])
        await interaction.response.send_modal(HelpModal(valinta=valinta, target_channel=self.channel))

class GiveawayView(discord.ui.View):
    def __init__(self, palkinto, rooli, kesto, alkuviesti, luoja, kieltorooli=None):
        super().__init__(timeout=None)
        self.palkinto = palkinto
        self.rooli = rooli
        self.kieltorooli = kieltorooli  
        self.kesto = kesto
        self.osallistujat = set()
        self.viesti = alkuviesti
        self.luoja = luoja
        self.loppunut = False
        self.voittaja = None

    @discord.ui.button(label="🎉 Osallistu", style=discord.ButtonStyle.green)
    async def osallistumisnappi(self, interaction: Interaction, button: discord.ui.Button):
        if self.loppunut:
            await interaction.response.send_message("Arvonta on jo päättynyt.", ephemeral=True)
            return

        if self.kieltorooli and self.kieltorooli in interaction.user.roles:
            await interaction.response.send_message("Sinulla on rooli, joka estää osallistumisen tähän arvontaan.", ephemeral=True)
            return

        if self.rooli not in interaction.user.roles:
            await interaction.response.send_message("Sinulla ei ole oikeaa roolia osallistuaksesi.", ephemeral=True)
            return

        if interaction.user in self.osallistujat:
            await interaction.response.send_message("Olet jo osallistunut!", ephemeral=True)
            return

        self.osallistujat.add(interaction.user)
        await interaction.response.send_message("Olet mukana arvonnassa!", ephemeral=True)

        mod_log_channel_id = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
        mod_log_channel = interaction.client.get_channel(mod_log_channel_id)

        if mod_log_channel:
            logiviesti = (
                f"📥 **Arvontaan osallistuminen**\n"
                f"👤 Käyttäjä: {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"🎁 Palkinto: {self.palkinto}\n"
                f"🎯 Rooli: {self.rooli.mention}\n"
                f"👮 Arvonnan luoja: {self.luoja.mention}"
            )
            await mod_log_channel.send(logiviesti)

    @discord.ui.button(label="⛔ Lopeta arvonta", style=discord.ButtonStyle.red)
    async def lopetusnappi(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.luoja:
            await interaction.response.send_message("Vain arvonnan luoja voi lopettaa sen.", ephemeral=True)
            return
        await self.lopeta_arvonta(interaction.channel)

    async def lopeta_arvonta(self, kanava):
        if self.loppunut:
            return
        self.loppunut = True
        self.stop()

        mod_log_channel_id = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
        mod_log_channel = kanava.guild.get_channel(mod_log_channel_id)

        if self.osallistujat:
            self.voittaja = random.choice(list(self.osallistujat))
            await kanava.send(
                f"🎉 Onnea {self.voittaja.mention}, voitit **{self.palkinto}**!",
                view=RerollView(self)
            )

            if mod_log_channel:
                logiviesti = (
                    f"🏆 **Arvonnan voittaja**\n"
                    f"🎁 Palkinto: {self.palkinto}\n"
                    f"👤 Voittaja: {self.voittaja.mention} (`{self.voittaja.id}`)\n"
                    f"👮 Arvonnan luoja: {self.luoja.mention}\n"
                    f"📊 Osallistujia yhteensä: {len(self.osallistujat)}"
                )
                await mod_log_channel.send(logiviesti)

        else:
            await kanava.send(
                "⛔ Arvonta on päättynyt, mutta kukaan ei osallistunut tai osallistujilla ei ollut oikeaa roolia."
            )

            if mod_log_channel:
                logiviesti = (
                    f"🚫 **Arvonta päättyi ilman osallistujia**\n"
                    f"🎁 Palkinto: {self.palkinto}\n"
                    f"👮 Arvonnan luoja: {self.luoja.mention}\n"
                    f"📊 Osallistujia: 0"
                )
                await mod_log_channel.send(logiviesti)

class RerollView(discord.ui.View):
    def __init__(self, giveaway_view: GiveawayView):
        super().__init__(timeout=None)
        self.giveaway_view = giveaway_view

    @discord.ui.button(label="🎲 Arvo uusi voittaja", style=discord.ButtonStyle.blurple)
    async def reroll_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.giveaway_view.luoja:
            await interaction.response.send_message("Vain arvonnan luoja voi arpoa uuden voittajan.", ephemeral=True)
            return
        osallistujat = list(self.giveaway_view.osallistujat - {self.giveaway_view.voittaja})
        if not osallistujat:
            await interaction.response.send_message("Ei ole muita osallistujia, joista arpoa uusi voittaja.", ephemeral=True)
            return
        uusi_voittaja = random.choice(osallistujat)
        self.giveaway_view.voittaja = uusi_voittaja
        await interaction.channel.send(f"🎉 Uusi voittaja on {uusi_voittaja.mention}! Onnea **{self.giveaway_view.palkinto}**:sta!")

KOMENTOJEN_ROOLIT = {
    "aika": "24G",
    "moikka": "24G",
    "esittely": "24G",
    "nofal": "24G",
    "kutsumalinkki": "24G",
    "ruokailuvuorot": "24G",
    "ruoka": "24G",
    "sano": "24G",
    "mielipide": ["VIP", "Mestari"],
    "laskin": "24G",
    "ajastin": ["VIP", "Mestari"],
    "kulppi": "24G",
    "seuraava_lomapäiva": "24G",
    "meme": "24G",
    "help": "24G",
    "giveaway": "Mestari",
    "sammutus": "Mestari",
    "vaihda_tilaviesti": "Mestari",
    "vaihda_nimimerkki": "Mestari",
    "uudelleenkaynnistys": "Mestari",
    "ilmoitus": "Mestari",
    "clear": "Mestari",
    "lukitse": "Mestari",
    "ping": "24G",
    "tag": ["taso 15", "Taso 25", "Taso 50", "Mestari"],
    "vaihda_tag": ["taso 15", "Taso 25", "Taso 50", "Mestari"],
    "remove_tag": ["taso 15", "Taso 25", "Taso 50", "Mestari"],
    "stats": ["Taso 50", "Mestari"],
    "taso": "24G",
    "lisää_xp": "Mestari",
    "vähennä_xp": "Mestari",
    "mute": ["Moderaattori", "Mestari"],
    "unmute": ["Moderaattori", "Mestari"],
    "warn": ["Moderaattori", "Mestari"],
    "unwarn": ["Moderaattori", "Mestari"],
    "varoitukset": ["Moderaattori", "Mestari"],
    "kick": "Mestari",
    "ban": "Mestari",
    "unban": "Mestari",
    "huolto": "Mestari",
    "set_role": "Mestari",
    "remove_role": "Mestari",
    "vitsi": "24G",
    "reagoi": "Mestari",
    "tehtävät": "24G",
    "kauppa": "24G",
    "lähetädm": "Mestari",
    "tiedot": "24G",
    "komennot": "24G",
    "muistuta": ["VIP", "Mestari"],
    "holvi_tallenna": ["VIP", "Mestari"],
    "holvi_hae": ["VIP", "Mestari"],
    "ennustus": ["VIP", "Mestari"],
}

KOMENTOJEN_KUVAUKSET = {
    "aika": "Näyttää nykyisen ajan ja muiden alueiden kellonajat",
    "moikka": "Tervehtii käyttäjää",
    "esittely": "Näyttää botin esittelyn",
    "nofal": "Nofal-komento",
    "kutsumalinkki": "Antaa kutsulinkin serverille ja tekee uusia kutsuja",
    "ruokailuvuorot": "Näyttää ruokailuvuorot",
    "ruoka": "Kertoo päivän ruoan, 7 päivän ruoan ja ensi viikon ruokalistan",
    "sano": "Botti sanoo jotain puolestasi",
    "mielipide": "Antaa satunnaisen mielipiteen sinun kysymyksestäsi",
    "laskin": "Laskee annetun laskutoimituksen ja näyttää myös välivaiheet",
    "ajastin": "Käynnistää haluamasi ajan ajastimen",
    "kulppi": "Kertoo Kulpin ajan annetusta ajasta",
    "seuraava_lomapäiva": "Näyttää seuraavan lomapäivän",
    "meme": "Lähettää satunnaisen meemin",
    "help": "Mahdollista ilmoittaa asiasta, kysyä apua tai antaa palautetta",
    "giveaway": "Luo tai hallinnoi arvontoja",
    "sammutus": "Sammuttaa botin",
    "vaihda_tilaviesti": "Vaihtaa botin tilaviestin",
    "vaihda_nimimerkki": "Vaihtaa käyttäjän nimimerkin",
    "uudelleenkaynnistys": "Käynnistää botin uudelleen",
    "ilmoitus": "Lähettää ilmoituksen haluamalle kanavalle",
    "clear": "Poistaa viestejä",
    "lukitse": "Lukitsee kanavan kaikilta käyttäjiltä",
    "ping": "Testaa vasteajan",
    "tag": "Luo uuden tagin",
    "vaihda_tag": "Muokkaa olemassa olevaa tagia",
    "remove_tag": "Poistaa tagin",
    "stats": "Näyttää bottistatistiikkaa",
    "taso": "Näyttää käyttäjän tason ja XP:n",
    "lisää_xp": "Lisää XP:tä käyttäjälle",
    "vähennä_xp": "Vähentää XP:tä käyttäjältä",
    "mute": "Mykistää käyttäjän",
    "unmute": "Poistaa mykistyksen",
    "warn": "Antaa varoituksen",
    "unwarn": "Poistaa varoituksen",
    "varoitukset": "Näyttää käyttäjän varoitukset",
    "kick": "Poistaa käyttäjän palvelimelta",
    "ban": "Bannaa käyttäjän",
    "unban": "Poistaa bannin käyttäjältä",
    "huolto": "Kytkee botin huoltotilan päälle",
    "set_role": "Antaa käyttäjälle roolin",
    "remove_role": "Poistaa käyttäjältä roolin",
    "vitsi": "Kertoo satunnaisen vitsin",
    "lähetädm": "Lähettää viestin suoraan käyttäjälle (DM)",
    "tiedot": "Näyttää jäsenestä tallennetut botin tiedot",
    "reagoi": "Reagoi viestiin, joka sisältää tietyn tekstin",
    "tehtävät": "Näytä ja suorita päivittäisiä-, viikottaisia- tai kuukauttaisia tehtäviä",
    "komennot": "Näyttää kaikki käytettävissä olevat komennot ja niiden selitykset",
    "kauppa": "Näytä kaupan tuotteet tai osta tuote",
    "muistuta": "Aseta muistutus itsellesi.",
    "holvi_hae": "Hae sisältö holvista salasanalla.",
    "holvi_tallenna": "Tallenna sisältö holviin salasanalla.",
    "ennustus": "Saat mystisen ennustuksen Sannamaijalta.",
}

def luo_embedit(user_roles):
    embedit = []
    nykyinen_embed = discord.Embed(title="Käytettävissä olevat komennot", color=discord.Color.blue())
    kenttä_laskuri = 0

    for komento, roolivaatimus in KOMENTOJEN_ROOLIT.items():
        vaatimukset = roolivaatimus if isinstance(roolivaatimus, list) else [roolivaatimus]
        if roolivaatimus is None or any(rooli in user_roles for rooli in vaatimukset):
            kuvaus = KOMENTOJEN_KUVAUKSET.get(komento, "Ei kuvausta.")
            nykyinen_embed.add_field(name=f"/{komento}", value=kuvaus, inline=False)
            kenttä_laskuri += 1

            if kenttä_laskuri == 25:
                embedit.append(nykyinen_embed)
                nykyinen_embed = discord.Embed(title="Käytettävissä olevat komennot (jatkuu)", color=discord.Color.blue())
                kenttä_laskuri = 0

    if kenttä_laskuri > 0:
        embedit.append(nykyinen_embed)

    return embedit

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_services(self):
        from utils.status_updater import update_status
        import asyncio
        asyncio.create_task(update_status())


    @app_commands.command(name="help", description="Kysy apua tai ilmoita asiasta.")
    @app_commands.checks.has_role("24G")
    async def help(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/help")
        await kirjaa_ga_event(self.bot, interaction.user.id, "help_komento")

        load_dotenv()
        HELP_CHANNEL_ID = int(os.getenv("HELP_CHANNEL_ID"))
        target_channel = interaction.guild.get_channel(HELP_CHANNEL_ID)
        if not target_channel:
            await interaction.response.send_message("Kanavaa 'modi-lokit' ei löytynyt.", ephemeral=True)
            return

        await interaction.response.send_message(
            "**Kuinka voisin olla tänään avuksi?**\nValitse alta aihe, niin voit kirjoittaa tarkemmin.",
            view=HelpDropdown(channel=target_channel),
            ephemeral=True
        )

    @app_commands.command(name="giveaway", description="Luo arvonta palkinnosta.")
    @app_commands.describe(
        palkinto="Mitä arvotaan?",
        kesto="Kesto minuutteina",
        rooli="Rooli jolla saa osallistua",
        kieltorooli="Rooli jolla ei saa osallistua"
    )
    @app_commands.checks.has_role("Mestari")
    async def giveaway(
        self,
        interaction: discord.Interaction,
        palkinto: str,
        kesto: int,
        rooli: discord.Role,
        kieltorooli: discord.Role
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/giveaway")
        await kirjaa_ga_event(self.bot, interaction.user.id, "giveaway_komento")

        view = GiveawayView(palkinto, rooli, kesto, kieltorooli, interaction.user)
        await interaction.response.send_message(
            f"🎉 **Arvonta aloitettu!** 🎉\n"
            f"**Palkinto:** {palkinto}\n"
            f"**Osallistumisoikeus:** {rooli.mention}\n"
            f"**Ei voi osallistua jos kuuluu rooliin:** {kieltorooli.mention}\n"
            f"**Kesto:** {kesto} minuuttia\n\n"
            f"Paina **🎉 Osallistu** -painiketta osallistuaksesi!",
            view=view
        )

        view.viesti = await interaction.original_response()
        await asyncio.sleep(kesto * 60)
        await view.lopeta_arvonta(interaction.channel)

    @app_commands.command(name="heitä", description="Heitä kolikkoa tai arvo numero.")
    @app_commands.describe(
        tyyppi="Valitse heiton tyyppi: numero, väli tai kolikko",
        min="Pienin arvo (käytetään 'numero' ja 'väli' -tyypeissä)",
        max="Suurin arvo (käytetään 'numero' ja 'väli' -tyypeissä)",
        vaihtoehto1="Ensimmäinen vaihtoehto kolikon heittoon (esim. 'Kruunu')",
        vaihtoehto2="Toinen vaihtoehto kolikon heittoon (esim. 'Klaava')"
    )
    async def heitä(
        self,
        interaction: discord.Interaction,
        tyyppi: Literal["numero", "väli", "kolikko"],
        min: Optional[int] = None,
        max: Optional[int] = None,
        vaihtoehto1: Optional[str] = None,
        vaihtoehto2: Optional[str] = None
    ):
        await kirjaa_ga_event(self.bot, interaction.user.id, "heitä_komento")
        await kirjaa_komento_lokiin(self.bot, interaction, "/heitä")

        if tyyppi in ["numero", "väli"]:
            if min is None or max is None:
                await interaction.response.send_message("Anna sekä minimi- että maksimiarvo.", ephemeral=True)
                return
            if min > max:
                await interaction.response.send_message("Minimi ei voi olla suurempi kuin maksimi.", ephemeral=True)
                return

            tulos = random.randint(min, max)
            await interaction.response.send_message(f"🎲 Heitettiin numero: **{tulos}** (väliltä {min}–{max})")

        elif tyyppi == "kolikko":
            valinnat = [vaihtoehto1 or "Kruunu", vaihtoehto2 or "Klaava"]
            tulos = random.choice(valinnat)
            await interaction.response.send_message(
                f"🪙 Kolikko heitettiin: **{tulos}**\nVaihtoehdot olivat: `{valinnat[0]}` ja `{valinnat[1]}`"
            )

        else:
            await interaction.response.send_message("Tuntematon heittotyyppi.", ephemeral=True)

    @app_commands.command(name="tag", description="Lisää tagin käyttäjän serverinimen perään.")
    @app_commands.describe(tag="Haluttu tagi, 3-6 kirjainta pitkä.")
    @app_commands.checks.has_role("24G")
    async def tag(self, interaction: discord.Interaction, tag: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/tag")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tag_komento")
        tag = re.sub(r'[^a-zA-Z0-9]', '', tag.strip())
        kielletyt_sanat = ["niger", "nekru", "nigga", "nig", "homo", "gay", "homot", "pillu", "penis", "perse"]

        if len(tag) < 3 or len(tag) > 6:
            await interaction.response.send_message("Tagin täytyy olla 3-6 kirjainta pitkä.", ephemeral=True)
            return

        if tag.lower() in kielletyt_sanat:
            await interaction.response.send_message("Tagia ei voida käyttää, koska se sisältää kielletyn sanan.", ephemeral=True)
            return

        current = interaction.user.nick or interaction.user.name
        uusi = f"{current} ({tag})"

        try:
            await interaction.user.edit(nick=uusi)
            await interaction.response.send_message(f"Tag **({tag})** lisättiin onnistuneesti serverinimeesi!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Ei oikeuksia muokata serverinimeäsi.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Virhe nimimerkkiä muokatessa. Yritä uudelleen.", ephemeral=True)

    @app_commands.command(name="vaihda_tag", description="Vaihda käyttäjän serverinimen tag uuteen.")
    @app_commands.describe(tag="Uusi tagi (3-6 kirjainta).")
    @app_commands.checks.has_role("24G")
    async def vaihda_tag(self, interaction: discord.Interaction, tag: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vaihda_tag")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vaihda_tag_komento")
        tag = tag.strip()
        kielletyt_sanat = ["niger", "nekru", "nigga", "nig"]

        if len(tag) < 3 or len(tag) > 6:
            await interaction.response.send_message("Tagin täytyy olla 3-6 kirjainta pitkä.", ephemeral=True)
            return

        if tag.lower() in kielletyt_sanat:
            await interaction.response.send_message("Tagia ei voida käyttää, koska se sisältää kielletyn sanan.", ephemeral=True)
            return

        current = interaction.user.nick or interaction.user.name
        uusi_nimi = re.sub(r"\s*\(.*?\)", "", current).strip()
        uusi_nimi = f"{uusi_nimi} ({tag})"

        try:
            await interaction.user.edit(nick=uusi_nimi)
            await interaction.response.send_message(f"Tag on vaihdettu. Uusi serverinimesi: **{uusi_nimi}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Ei oikeuksia muokata serverinimeäsi.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Virhe nimimerkkiä muokatessa. Yritä uudelleen.", ephemeral=True)

    @app_commands.command(name="remove_tag", description="Poistaa tagin käyttäjän serverinimestä.")
    @app_commands.checks.has_role("24G")
    async def remove_tag(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/remove_tag")
        await kirjaa_ga_event(self.bot, interaction.user.id, "remove_tag_komento")

        current = interaction.user.nick or interaction.user.name

        if "(" in current and ")" in current:
            uusi_nimi = re.sub(r"\s*\(.*?\)", "", current).strip()

            try:
                await interaction.user.edit(nick=uusi_nimi)
                await interaction.response.send_message(f"Tagi on poistettu. Uusi serverinimesi: **{uusi_nimi}**", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Ei oikeuksia muokata serverinimeäsi.", ephemeral=True)
            except discord.HTTPException:
                await interaction.response.send_message("Virhe nimimerkkiä muokatessa. Yritä uudelleen.", ephemeral=True)
        else:
            await interaction.response.send_message("Serverinimesi ei sisällä tagia, joten mitään ei tarvitse poistaa.", ephemeral=True)

    @app_commands.command(name="komennot", description="Näyttää kaikki käytettävissä olevat komennot ja niiden selitykset.")
    @app_commands.checks.has_role("24G")
    async def komennot(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            if interaction.guild is None:
                await interaction.followup.send("Tämä komento toimii vain palvelimella.", ephemeral=True)
                return

            await kirjaa_komento_lokiin(self.bot, interaction, "/komennot")
            await kirjaa_ga_event(self.bot, interaction.user.id, "komennot_komento")

            member = interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.get_member(interaction.user.id)
            if member is None:
                await interaction.followup.send("Virhe: Käyttäjätietoja ei voitu hakea.", ephemeral=True)
                return

            user_roles = [role.name for role in member.roles]
            viesti = "**Käytettävissä olevat komennot:**\n"

            for komento, roolivaatimus in KOMENTOJEN_ROOLIT.items():
                vaatimukset = roolivaatimus if isinstance(roolivaatimus, list) else [roolivaatimus]
                if roolivaatimus is None or any(rooli in user_roles for rooli in vaatimukset):
                    kuvaus = KOMENTOJEN_KUVAUKSET.get(komento, "Ei kuvausta.")
                    viesti += f"**/{komento}** – {kuvaus}\n"

            if viesti.strip() == "**Käytettävissä olevat komennot:**":
                viesti = "Sinulla ei ole oikeuksia yhteenkään komentoon."

            print(f"Viesti lähetetään: {viesti}")
            embedit = luo_embedit(user_roles)

            if not embedit:
                await interaction.followup.send("Sinulla ei ole oikeuksia yhteenkään komentoon.", ephemeral=True)
            else:
                for embed in embedit:
                    await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Virhe komennon suorittamisessa: {e}")
            await interaction.followup.send(f"Virhe komennon suorittamisessa: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Utils(bot)
    await bot.add_cog(cog)