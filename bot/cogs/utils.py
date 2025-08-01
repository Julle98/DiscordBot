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
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.antinuke import cooldown

from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

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
        self.add_item(self.palaute)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.vastaanottaja.send(
                f"**Vastaus pyyntöösi ({self.toiminto}):**\n{self.palaute.value}",
                embed=self.embed
            )
        except discord.Forbidden:
            await interaction.response.send_message("Käyttäjälle ei voitu lähettää viestiä (DM estetty).", ephemeral=True)
            await self.viesti.edit(view=None)
            return

        uusi_embed = self.embed.copy()
        alku_footer = self.embed.footer.text or ""
        emoji = "📬" if self.toiminto == "vastattu" else "✅"
        vari = discord.Color.blurple() if self.toiminto == "vastattu" else discord.Color.green()

        uusi_embed.title = f"{emoji} {self.embed.title}"
        uusi_embed.color = vari
        uusi_embed.set_footer(
            text=f"{alku_footer} • {self.toiminto.capitalize()}",
            icon_url=self.embed.footer.icon_url
        )

        await self.viesti.edit(embed=uusi_embed, view=None)
        await interaction.response.send_message(f"Pyyntö on {self.toiminto}.", ephemeral=True)

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

        self.add_item(self.kuvaus)
        self.add_item(self.kuva_linkki)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Uusi pyyntö /help-komennolla",
            color=discord.Color.blue(),
        )

        value_text = f"{self.valinta.label}"
        embed.add_field(name="Valinta", value=value_text, inline=False)
        embed.add_field(name="Kuvaus", value=self.kuvaus.value, inline=False)

        if self.kuva_linkki.value:
            embed.set_image(url=self.kuva_linkki.value)

        embed.set_footer(
            text=f"{interaction.user} ({interaction.user.id})",
            icon_url=interaction.user.display_avatar.url
        )

        self.user = interaction.user  
        await self.target_channel.send(embed=embed, view=HelpButtons(self.user, embed))

        await interaction.response.send_message("Pyyntösi on lähetetty! Kiitos!", ephemeral=True)

class HelpDropdown(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=60)
        self.channel = channel

        self.options = [
            discord.SelectOption(label="⚒️ Ongelma", value="ongelma", description="Tekninen ongelma tai bugi."),
            discord.SelectOption(label="❓ Report", value="report", description="Ilmoitus jostain asiattomasta."),
            discord.SelectOption(label="💁 Jokin muu", value="muu", description="Yleinen kysymys, idea tai ehdotus."),
        ]

        self.select = discord.ui.Select(placeholder="Valitse aihealue", options=self.options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        valinta = next(opt for opt in self.options if opt.value == self.select.values[0])
        await interaction.response.send_modal(HelpModal(valinta=valinta, target_channel=self.channel))

class GiveawayView(discord.ui.View):
    def __init__(self, palkinto, rooli, kesto, alkuviesti, luoja):
        super().__init__(timeout=None)
        self.palkinto = palkinto
        self.rooli = rooli
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
        if self.rooli not in interaction.user.roles:
            await interaction.response.send_message("Sinulla ei ole oikeaa roolia osallistuaksesi.", ephemeral=True)
            return
        self.osallistujat.add(interaction.user)
        await interaction.response.send_message("Olet mukana arvonnassa!", ephemeral=True)

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
        if self.osallistujat:
            self.voittaja = random.choice(list(self.osallistujat))
            await kanava.send(
                f"🎉 Onnea {self.voittaja.mention}, voitit **{self.palkinto}**!",
                view=RerollView(self)
            )
        else:
            await kanava.send("Kukaan ei osallistunut arvontaan tai osallistujilla ei ollut oikeaa roolia.")

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
    "tag": ["Taso 25", "Taso 50", "Mestari"],
    "vaihda_tag": ["Taso 25", "Taso 50", "Mestari"],
    "remove_tag": ["Taso 25", "Taso 50", "Mestari"],
    "stats": ["Taso 15", "Taso 25", "Taso 50", "Mestari"],
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
    "lähetädm": "24G",
    "tiedot": "24G",
    "komennot": "24G"
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
}

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
        rooli="Rooli jolla saa osallistua"
    )
    @app_commands.checks.has_role("Mestari")
    async def giveaway(self, interaction: discord.Interaction, palkinto: str, kesto: int, rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/giveaway")
        await kirjaa_ga_event(self.bot, interaction.user.id, "giveaway_komento")

        view = GiveawayView(palkinto, rooli, kesto, None, interaction.user)
        await interaction.response.send_message(
            f"🎉 **Arvonta aloitettu!** 🎉\n"
            f"**Palkinto:** {palkinto}\n"
            f"**Osallistumisoikeus:** {rooli.mention}\n"
            f"**Kesto:** {kesto} minuuttia\n\n"
            f"Paina **🎉 Osallistu** -painiketta osallistuaksesi!",
            view=view
        )

        view.viesti = await interaction.original_response()
        await asyncio.sleep(kesto * 60)
        await view.lopeta_arvonta(interaction.channel)

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
            await interaction.followup.send(viesti, ephemeral=True)

        except Exception as e:
            print(f"Virhe komennon suorittamisessa: {e}")
            await interaction.followup.send(f"Virhe komennon suorittamisessa: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Utils(bot)
    await bot.add_cog(cog)
