import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import List
import os
import pytz
import asyncio

from dotenv import load_dotenv
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin, autocomplete_bannatut_käyttäjät
from bot.utils.error_handler import CommandErrorHandler

load_dotenv()
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

class HuoltoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Anna huollon tiedot", style=discord.ButtonStyle.primary)
    async def anna_tiedot(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = discord.ui.Modal(title="Huoltotiedot")
        kesto_input = discord.ui.TextInput(label="Huollon kesto", placeholder="Esim. 10s, 5m", custom_id="kesto")
        lisatiedot_input = discord.ui.TextInput(label="Lisätiedot", style=discord.TextStyle.paragraph, custom_id="lisatiedot")
        modal.add_item(kesto_input)
        modal.add_item(lisatiedot_input)

        async def modal_submit(modal_interaction: discord.Interaction):
            try:
                kesto = modal_interaction.data["components"][0]["components"][0]["value"]
                lisatiedot = modal_interaction.data["components"][1]["components"][0]["value"]
                seconds = int(kesto[:-1])
                unit = kesto[-1]
                delay = seconds if unit == "s" else seconds * 60 if unit == "m" else seconds * 3600 if unit == "h" else None
                if not delay:
                    await modal_interaction.response.send_message("Virheellinen aikamuoto!", ephemeral=True)
                    return
                huolto_kanava = discord.utils.get(modal_interaction.guild.text_channels, name="🛜bot-status") or await modal_interaction.guild.create_text_channel(name="bot-status")
                await huolto_kanava.send(f"Botti huoltotilassa {kesto}. Lisätiedot: {lisatiedot}")
                await modal_interaction.response.send_message(f"Huoltotiedot lähetetty kanavalle {huolto_kanava.mention}.", ephemeral=True)
            except Exception:
                await modal_interaction.response.send_message("Tapahtui virhe. Tarkista syötteet.", ephemeral=True)

        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)

aktiiviset_paivat = dict()

ajastin_aktiiviset = {}

import os

class ClearModal(discord.ui.Modal, title="Vahvista poisto"):
    def __init__(self, selected_channel: discord.TextChannel):
        super().__init__()
        self.selected_channel = selected_channel

        self.amount = discord.ui.TextInput(
            label="Viestien määrä (1–100, valinnainen)",
            placeholder="Jätä tyhjäksi poistaaksesi kaiken (max 100)",
            required=False
        )
        self.confirmation = discord.ui.TextInput(
            label="Kirjoita KYLLÄ vahvistaaksesi",
            placeholder="KYLLÄ"
        )

        self.add_item(self.amount)
        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.confirmation.value.strip().casefold() != "kyllä":
            await interaction.followup.send("Vahvistus epäonnistui. Kirjoita KYLLÄ isolla tai pienellä.", ephemeral=True)
            return

        try:
            määrä = int(self.amount.value.strip()) if self.amount.value.strip() else None
        except ValueError:
            await interaction.followup.send("Viestimäärän pitää olla numero.", ephemeral=True)
            return

        if määrä is not None and (määrä < 1 or määrä > 100):
            await interaction.followup.send("Viestimäärän pitää olla välillä 1–100.", ephemeral=True)
            return

        try:
            poistettu = await self.selected_channel.purge(limit=määrä)
            määrä_poistettu = len(poistettu)

            await interaction.followup.send(
                f"{määrä_poistettu} viestiä poistettu kanavasta {self.selected_channel.mention}.",
                ephemeral=True
            )

            load_dotenv()
            mod_log_id = os.getenv("MOD_LOG_CHANNEL_ID")
            if mod_log_id:
                log_channel = interaction.guild.get_channel(int(mod_log_id))
                if log_channel:
                    await log_channel.send(
                        f"🧹 **{interaction.user}** poisti {määrä_poistettu} viestiä kanavasta {self.selected_channel.mention}."
                    )

        except discord.Forbidden:
            await interaction.followup.send("Ei oikeuksia poistaa viestejä tältä kanavalta.", ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send("Poisto epäonnistui. Yritä myöhemmin uudelleen.", ephemeral=True)

class KanavaSelect(discord.ui.Select):
    def __init__(self, kanavat, sivu):
        self.sivu = sivu
        alku = sivu * 25
        loppu = alku + 25
        kanavat_sivulla = kanavat[alku:loppu]

        options = [
            discord.SelectOption(label=kanava.name, value=str(kanava.id))
            for kanava in kanavat_sivulla
        ]
        super().__init__(placeholder="Valitse kanava", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_channel = interaction.guild.get_channel(int(self.values[0]))
        if not selected_channel:
            await interaction.response.send_message("Kanavaa ei löytynyt.", ephemeral=True)
            return
        await interaction.response.send_modal(ClearModal(selected_channel))

class ClearView(discord.ui.View):
    def __init__(self, kanavat, sivu=0):
        super().__init__(timeout=60)
        self.kanavat = kanavat
        self.sivu = sivu
        self.max_sivu = (len(kanavat) - 1) // 25

        self.select = KanavaSelect(kanavat, sivu)
        self.add_item(self.select)

        if self.max_sivu > 0:
            self.add_item(self.EdellinenButton())
            self.add_item(self.SeuraavaButton())

        self.add_item(self.PeruutaButton())  

    class EdellinenButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="⬅️ Edellinen", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: ClearView = self.view
            if view.sivu > 0:
                uusi_sivu = view.sivu - 1
                uusi_view = ClearView(view.kanavat, uusi_sivu)
                await interaction.response.edit_message(
                    content=f"Sivu {uusi_sivu + 1} / {view.max_sivu + 1}",
                    view=uusi_view
                )
            else:
                await interaction.response.defer()

    class SeuraavaButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Seuraava ➡️", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: ClearView = self.view
            if view.sivu < view.max_sivu:
                uusi_sivu = view.sivu + 1  # Tämä oli väärin aiemmin
                uusi_view = ClearView(view.kanavat, uusi_sivu)
                await interaction.response.edit_message(
                    content=f"Sivu {uusi_sivu + 1} / {view.max_sivu + 1}",
                    view=uusi_view
                )
            else:
                await interaction.response.defer()

    class PeruutaButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="❌ Peruuta", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(content="Toiminto peruutettu.", view=None)

class IlmoitusModal(discord.ui.Modal, title="Luo ilmoitus"):
    otsikko = discord.ui.TextInput(label="Otsikko", placeholder="Esim. Huoltotauko")
    teksti = discord.ui.TextInput(label="Pääteksti", style=discord.TextStyle.paragraph, placeholder="Kuvaile mitä tapahtuu...")
    lisatiedot = discord.ui.TextInput(label="Lisätiedot", required=False, placeholder="Lisäinfo, linkki jne.")
    kuvalinkki = discord.ui.TextInput(label="(Valinnainen) Kuvalinkki", required=False, placeholder="https://...")

    def __init__(self, target_channel, user):
        super().__init__()
        self.target_channel = target_channel
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        viesti = f"# {self.otsikko.value}\n> {self.teksti.value}"
        if self.lisatiedot.value:
            viesti += f"\n- {self.lisatiedot.value}"

        embed = discord.Embed(description=viesti)

        if self.kuvalinkki.value:
            embed.set_image(url=self.kuvalinkki.value)

        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("Ilmoitus lähetetty onnistuneesti!", ephemeral=True)

aktiiviset_paivat = dict()

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_monitors(self):
        from utils.moderation_tasks import (
            tarkista_ostojen_kuukausi,
            check_deletions,
            tarkista_puhekanavat,
            tarkista_paivat
        )
        if not tarkista_ostojen_kuukausi.is_running():
            tarkista_ostojen_kuukausi.start()
        if not check_deletions.is_running():
            check_deletions.start()
        if not tarkista_puhekanavat.is_running():
            tarkista_puhekanavat.start()
        if not tarkista_paivat.is_running():
            tarkista_paivat.start()

    # MUTE
    @app_commands.command(name="mute", description="Aseta jäähy jäsenelle.")
    @app_commands.describe(jäsen="Jäsen, jolle asetetaan jäähy", kesto="Jäähyn kesto", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def mute(self, interaction: discord.Interaction, jäsen: discord.Member, kesto: str, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/mute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "mute_komento")
        if jäsen == interaction.user:
            await interaction.response.send_message("Et voi asettaa itseäsi jäähylle.", ephemeral=True)
            return
        try:
            seconds = int(kesto[:-1])
            unit = kesto[-1]
            if unit == "s":
                duration = timedelta(seconds=seconds)
            elif unit == "m":
                duration = timedelta(minutes=seconds)
            elif unit == "h":
                duration = timedelta(hours=seconds)
            else:
                await interaction.response.send_message("Virheellinen aikaformaatti. Käytä esim. 10s, 5m, 1h", ephemeral=True)
                return
            await jäsen.timeout(duration, reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} asetettu jäähylle ajaksi {kesto}. Syy: {syy}")
            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                await modlog_channel.send(
                    f"🔇 **Jäähy asetettu**\n👤 {jäsen.mention}\n⏱ {kesto}\n📝 {syy}\n👮 {interaction.user.mention}"
                )
        except Exception as e:
            await interaction.response.send_message(f"Virhe asetettaessa jäähyä: {e}", ephemeral=True)

    # UNMUTE
    @app_commands.command(name="unmute", description="Poista jäähy jäseneltä.")
    @app_commands.describe(jäsen="Jäsen, jolta poistetaan jäähy", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def unmute(self, interaction: discord.Interaction, jäsen: discord.Member, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/unmute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unmute_komento")
        if jäsen.timed_out_until is None:
            await interaction.response.send_message(f"{jäsen.mention} ei ole jäähyllä.", ephemeral=True)
            return
        try:
            await jäsen.timeout(None, reason=f"{syy} (Poisti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} on vapautettu jäähyltä. Syy: {syy}")
        except Exception as e:
            await interaction.response.send_message(f"Virhe poistettaessa jäähyä: {e}", ephemeral=True)

    # WARN
    @app_commands.command(name="warn", description="Anna varoitus käyttäjälle.")
    @app_commands.describe(member="Käyttäjä", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/warn")
        await kirjaa_ga_event(self.bot, interaction.user.id, "warn_komento")
        try:
            await member.send(f"Olet saanut varoituksen: {syy}")
        except discord.Forbidden:
            await interaction.followup.send("YV epäonnistui.", ephemeral=True)
        await interaction.response.send_message(f"{member.mention} sai varoituksen.")
        modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
        if modlog:
            await modlog.send(f"[VAROITUS] {member.mention} | ID: {member.id} | Syy: {syy} | Antaja: {interaction.user.mention}")

    # UNWARN
    @app_commands.command(name="unwarn", description="Poista käyttäjän varoitus.")
    @app_commands.describe(member="Käyttäjä", kaikki="Poista kaikki varoitukset.")
    @app_commands.checks.has_role("Mestari")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, kaikki: bool = False):
        await kirjaa_komento_lokiin(self.bot, interaction, "/unwarn")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unwarn_komento")
        modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
        if not modlog:
            await interaction.response.send_message("Moderaatiokanavaa ei löytynyt.", ephemeral=True)
            return
        poistettu = 0
        async for msg in modlog.history(limit=1000):
            if msg.author == self.bot.user and f"ID: {member.id}" in msg.content:
                await msg.delete()
                poistettu += 1
                if not kaikki:
                    break
        await interaction.response.send_message(
            f"{member.mention} varoituksista poistettiin {poistettu} {'kaikki' if kaikki else 'yksi'}."
        )

    # VAROITUKSET
    @app_commands.command(name="varoitukset", description="Näytä käyttäjän varoitukset.")
    @app_commands.describe(member="Käyttäjä")
    @app_commands.checks.has_role("Mestari")
    async def varoitukset(self, interaction: discord.Interaction, member: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/varoitukset")
        await kirjaa_ga_event(self.bot, interaction.user.id, "varoitukset_komento")
        modlog = self.bot.get_channel(MODLOG_CHANNEL_ID)
        if not modlog:
            await interaction.response.send_message("Moderaatiokanavaa ei löytynyt.", ephemeral=True)
            return
        lista = []
        async for msg in modlog.history(limit=1000):
            if f"ID: {member.id}" in msg.content:
                lista.append(msg.content)
        if not lista:
            await interaction.response.send_message("Ei varoituksia.", ephemeral=True)
            return
        vastaus = "\n".join([f"{i+1}. {v.split(' | Syy: ')[-1].split(' |')[0]}" for i, v in enumerate(lista)])
        await interaction.response.send_message(f"{member.mention} on saanut {len(lista)} varoitusta:\n{vastaus}", ephemeral=True)

    # KICK
    @app_commands.command(name="kick", description="Poista käyttäjä palvelimelta.")
    @app_commands.describe(member="Käyttäjä", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/kick")
        await kirjaa_ga_event(self.bot, interaction.user.id, "kick_komento")
        try:
            await member.send(f"Sinut on potkittu. Syy: {syy}")
        except discord.Forbidden:
            pass
        try:
            await member.kick(reason=syy)
            await interaction.response.send_message(f"{member.mention} on potkittu.")
        except Exception as e:
            await interaction.response.send_message(f"Potku epäonnistui: {e}", ephemeral=True)

    # BAN
    @app_commands.command(name="ban", description="Bannaa käyttäjä.")
    @app_commands.describe(member="Käyttäjä", syy="Syy")
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ban")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ban_komento")
        try:
            await member.send(f"Bannattu. Syy: {syy}")
        except discord.Forbidden:
            pass
        try:
            await member.ban(reason=syy)
            await interaction.response.send_message(f"{member.mention} on bannattu.")
        except Exception as e:
            await interaction.response.send_message(f"Bannaus epäonnistui: {e}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Ei oikeuksia bannata tätä käyttäjää.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe bannatessa käyttäjää: {str(e)}", ephemeral=True)

    # UNBAN
    @app_commands.command(name="unban", description="Poista käyttäjän porttikielto.")
    @app_commands.describe(käyttäjänimi="Käyttäjänimi muodossa nimi#0001", syy="Syy unbannille.")
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.autocomplete(käyttäjänimi=autocomplete_bannatut_käyttäjät)
    async def unban(self, interaction: discord.Interaction, käyttäjänimi: str, syy: str = "Ei syytä annettu"):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/unban")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unban_komento")

        try:
            banned_users = [entry async for entry in interaction.guild.bans()]
        except Exception as e:
            await interaction.followup.send(f"Virhe haettaessa banneja: {e}", ephemeral=True)
            return

        nimi, _, discrim = käyttäjänimi.partition("#")

        if "#" in käyttäjänimi and not discrim.isdigit():
            await interaction.followup.send("Virheellinen käyttäjänimi. Käytä muotoa nimi#1234.", ephemeral=True)
            return

        for ban_entry in banned_users:
            user = ban_entry.user
            match = (user.name, user.discriminator) == (nimi, discrim) if discrim else user.name == käyttäjänimi

            if match:
                try:
                    await user.send(f"Porttikielto palvelimelta {interaction.guild.name} on poistettu. Syy: {syy}")
                except discord.Forbidden:
                    pass

                await interaction.guild.unban(user, reason=syy)
                await interaction.followup.send(f"{user.name}#{user.discriminator} unbannattu. Syy: {syy}")
                return

        await interaction.followup.send("Käyttäjää ei löytynyt bannatuista.", ephemeral=True)

    # HUOLTO
    @app_commands.command(name="huolto", description="Aseta botti huoltotilaan.")
    @app_commands.checks.has_role("Mestari")
    async def huolto(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/huolto")
        await kirjaa_ga_event(self.bot, interaction.user.id, "huolto_komento")
        await interaction.response.send_message(
            "Paina alla olevaa painiketta antaaksesi huollon tiedot:",
            view=HuoltoView(), ephemeral=True
        )

    # SET ROLE
    @app_commands.command(name="set_role", description="Lisää roolin käyttäjälle.")
    @app_commands.checks.has_role("Mestari")
    async def set_role(self, interaction: discord.Interaction, käyttäjä: discord.Member, rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/set_role")
        await kirjaa_ga_event(self.bot, interaction.user.id, "set_role_komento")
        await käyttäjä.add_roles(rooli)
        await interaction.response.send_message(
            f"Rooli **{rooli.name}** lisätty käyttäjälle {käyttäjä.mention}.✅", ephemeral=True
        )

    # REMOVE ROLE
    @app_commands.command(name="remove_role", description="Poistaa roolin käyttäjältä.")
    @app_commands.checks.has_role("Mestari")
    async def remove_role(self, interaction: discord.Interaction, käyttäjä: discord.Member, rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/remove_role")
        await kirjaa_ga_event(self.bot, interaction.user.id, "remove_role_komento")
        await käyttäjä.remove_roles(rooli)
        await interaction.response.send_message(
            f"Rooli **{rooli.name}** poistettu käyttäjältä {käyttäjä.mention}. 🗑️", ephemeral=True
        )

    # TOIMINTA
    @app_commands.command(name="toiminta", description="Näytä aktiivisin kanava per jäsen")
    @app_commands.describe(jäsen="Valitse jäsen")
    @app_commands.checks.has_role("Mestari")
    async def toiminta(self, interaction: discord.Interaction, jäsen: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/toiminta")
        await kirjaa_ga_event(self.bot, interaction.user.id, "toiminta_komento")
        await interaction.response.defer(ephemeral=True)

        viestimäärät = {}
        kanavat = [c for c in interaction.guild.text_channels if c.permissions_for(jäsen).read_messages]

        for kanava in kanavat:
            try:
                count = sum(1 async for msg in kanava.history(limit=1000) if msg.author == jäsen)
                if count > 0:
                    viestimäärät[kanava] = count
            except discord.Forbidden:
                continue

        if not viestimäärät:
            await interaction.followup.send("Ei viestejä löytynyt.")
            return

        aktiivisin = max(viestimäärät, key=viestimäärät.get)
        määrä = viestimäärät[aktiivisin]
        await interaction.followup.send(
            f"**{jäsen.display_name}** on lähettänyt eniten viestejä kanavalle {aktiivisin.mention} ({määrä} viestiä)."
        )

    # VIESTIT
    @app_commands.command(name="viestit", description="Näytä palvelimen koko viestimäärät")
    @app_commands.checks.has_role("Mestari")
    async def viestit(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/viestit")
        await kirjaa_ga_event(self.bot, interaction.user.id, "viestit_komento")
        await interaction.response.defer(ephemeral=True)
        viestimäärät = defaultdict(int)
        kanavat = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.guild.me).read_messages]

        for kanava in kanavat:
            try:
                async for msg in kanava.history(limit=200):
                    if not msg.author.bot:
                        viestimäärät[msg.author] += 1
            except discord.Forbidden:
                continue

        if not viestimäärät:
            await interaction.followup.send("Ei löytynyt viestejä.")
            return

        top = sorted(viestimäärät.items(), key=lambda x: x[1], reverse=True)[:5]
        vastaus = "\n".join(f"{i+1}. {k.display_name} – {m} viestiä" for i, (k, m) in enumerate(top))
        await interaction.followup.send("**Top 5 aktiivisinta käyttäjää:**\n" + vastaus)

    # SAMMUTUS
    @app_commands.command(name="sammutus", description="Sammuta botti.")
    @app_commands.checks.has_role("Mestari")
    async def sammutus(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/sammutus")
        await kirjaa_ga_event(self.bot, interaction.user.id, "sammutus_komento")

        status_kanava = discord.utils.get(interaction.guild.text_channels, name="🛜bot-status")
        if not status_kanava:
            status_kanava = await interaction.guild.create_text_channel(name="bot-status")

        async for message in status_kanava.history(limit=100):
            await message.delete()

        timezone = pytz.timezone('Europe/Helsinki')
        sammutusaika = datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')
        await status_kanava.send(f"Botti sammutettu {sammutusaika}.")
        await interaction.response.send_message("Botti sammuu...", ephemeral=True)

        for user_id, task in ajastin_aktiiviset.items():
            if not task.done():
                task.cancel()
        ajastin_aktiiviset.clear()

        await self.bot.close()

    # VAIHDA NIMIMERKKI
    @app_commands.command(name="vaihda_nimimerkki", description="Vaihda jäsenen nimimerkki palvelimella.")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.checks.has_role("Mestari")
    async def vaihda_nimimerkki(self, interaction: discord.Interaction, jasen: discord.Member, uusi_nimimerkki: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vaihda_nimimerkki")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vaihda_nimimerkki_komento")
        try:
            await jasen.edit(nick=uusi_nimimerkki)
            await interaction.response.send_message(f"{jasen.mention} nimimerkki vaihdettu: {uusi_nimimerkki}")
        except discord.Forbidden:
            await interaction.response.send_message("En voi vaihtaa tämän jäsenen nimimerkkiä.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe: {e}", ephemeral=True)

    # UUDELLEENKÄYNNISTYS
    @app_commands.command(name="uudelleenkäynnistys", description="Käynnistä botti uudelleen.")
    @app_commands.checks.has_role("Mestari")
    async def uudelleenkaynnistys(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/uudelleenkäynnistys")
        await kirjaa_ga_event(self.bot, interaction.user.id, "uudelleenkäynnistys_komento")

        status_kanava = discord.utils.get(interaction.guild.text_channels, name="🛜bot-status") or await interaction.guild.create_text_channel(name="bot-status")
        async for msg in status_kanava.history(limit=100):
            await msg.delete()

        await status_kanava.send("Botti käynnistyy uudelleen...")
        await interaction.response.send_message("Botti käynnistetään uudelleen...", ephemeral=True)
        await self.bot.close()

    # ILMOITUS
    @app_commands.command(name="ilmoitus", description="Luo ilmoitus botin nimissä ja lähetä se valittuun kanavaan.")
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(kanava="Kanava, johon ilmoitus lähetetään")
    async def ilmoitus(self, interaction: discord.Interaction, kanava: discord.TextChannel):
        await interaction.response.send_modal(IlmoitusModal(target_channel=kanava, user=interaction.user))
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/ilmoitus")
            await kirjaa_ga_event(self.bot, interaction.user.id, "ilmoitus_komento")
        except Exception as e:
            print(f"Task creation failed: {e}")

    # CLEAR
    @app_commands.command(name="clear", description="Poista viestejä valitusta kanavasta.")
    @app_commands.checks.has_role("Mestari")
    async def clear(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/clear")
        await kirjaa_ga_event(self.bot, interaction.user.id, "clear_komento")

        kanavat = [
            c for c in interaction.guild.text_channels
            if c.permissions_for(interaction.user).manage_messages
        ]

        if not kanavat:
            await interaction.response.send_message(
                "Ei oikeuksia viestien poistoon missään kanavassa.",
                ephemeral=True
            )
            return

        max_sivu = (len(kanavat) - 1) // 25
        nykyinen_sivu = 0

        await interaction.response.send_message(
            content=f"Sivu {nykyinen_sivu + 1} / {max_sivu + 1}\nValitse kanava ja vahvista:",
            view=ClearView(kanavat, nykyinen_sivu),
            ephemeral=True
        )

    # LUKITSE
    @app_commands.command(name="lukitse", description="Lukitsee kanavan kaikilta.")
    @app_commands.checks.has_role("Mestari")
    async def lukitse(self, interaction: discord.Interaction, kanava: discord.TextChannel):
        await kirjaa_komento_lokiin(self.bot, interaction, "/lukitse")
        await kirjaa_ga_event(self.bot, interaction.user.id, "lukitse_komento")
        await kanava.set_permissions(interaction.guild.default_role, send_messages=False)
        await kanava.set_permissions(interaction.user, send_messages=True)
        await interaction.response.send_message(f"Kanava {kanava.mention} on lukittu onnistuneesti!", ephemeral=True)

    # PING
    @app_commands.command(name="ping", description="Näytä botin viive.")
    async def ping(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ping")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ping_komento")
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Botin viive on {latency} ms.")

    # AKTIIVISIMMAT
    @app_commands.command(name="aktiivisimmat", description="Näytä aktiivisimmat käyttäjät tai aloita viestiseuranta.")
    @app_commands.checks.has_role("Mestari")
    @app_commands.describe(
        paiva="Muoto YYYY-MM-DD. Tyhjä = nykyhetki",
        tarkista="Näytä onko seuranta käynnissä"
    )
    async def aktiivisimmat(self, interaction: discord.Interaction, paiva: str = None, tarkista: bool = False):
        await kirjaa_komento_lokiin(self.bot, interaction, "/aktiivisimmat")
        await kirjaa_ga_event(self.bot, interaction.user.id, "aktiivisimmat_komento")
        if paiva or tarkista:
            if "Mestari" not in [role.name for role in interaction.user.roles]:
                await interaction.response.send_message("Tämä toiminto vaatii Mestari-roolin.", ephemeral=True)
                return
        else:
            if "24G" not in [role.name for role in interaction.user.roles]:
                await interaction.response.send_message("Tämä toiminto vaatii 24G-roolin.", ephemeral=True)
                return

        await interaction.response.defer(ephemeral=True)

        if tarkista:
            for paiva_key, data in aktiiviset_paivat.items():
                if data["guild_id"] == interaction.guild.id:
                    await interaction.followup.send(f"Viestiseuranta on tällä palvelimella päällä (aloitettu {paiva_key}).")
                    return
            await interaction.followup.send("Viestiseuranta on pois päältä.")
            return

        if paiva:
            try:
                pvm = datetime.strptime(paiva, "%Y-%m-%d").date()
            except ValueError:
                await interaction.followup.send("Virheellinen päivämäärämuoto. Käytä muotoa YYYY-MM-DD.")
                return

            aktiiviset_paivat[pvm] = {
                "guild_id": interaction.guild.id,
                "viestimäärät": defaultdict(int)
            }
            await interaction.followup.send(f"Aloitettiin viestiseuranta päivälle {paiva}.")
            return

        # Näytä 24h ajalta
        alku = datetime.now(timezone.utc) - timedelta(days=1)
        viestimäärät = defaultdict(int)
        kanavat = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.guild.me).read_messages]

        for kanava in kanavat:
            try:
                async for msg in kanava.history(after=alku, limit=None):
                    if not msg.author.bot:
                        viestimäärät[msg.author] += 1
            except discord.Forbidden:
                continue

        if not viestimäärät:
            await interaction.followup.send("Ei löytynyt viestejä viimeisen 24h ajalta.")
            return

        top = sorted(viestimäärät.items(), key=lambda x: x[1], reverse=True)[:5]
        teksti = "\n".join(f"{i+1}. {k.display_name} – {m} viestiä" for i, (k, m) in enumerate(top))
        await interaction.followup.send("**Top 5 aktiivisinta käyttäjää (24h):**\n" + teksti)

    # REAGOI
    @app_commands.command(name="reagoi", description="Reagoi viestiin, joka sisältää tietyn tekstin.")
    @app_commands.describe(hakusana="Osa viestistä", emoji="Emoji, jolla reagoidaan")
    @app_commands.checks.has_role("Mestari")
    async def reagoi(self, interaction: discord.Interaction, hakusana: str, emoji: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/reagoi")
        await kirjaa_ga_event(self.bot, interaction.user.id, "reagoi_komento")
        try:
            messages = [msg async for msg in interaction.channel.history(limit=100)]
            target = next((msg for msg in messages if hakusana.lower() in msg.content.lower()), None)
            if target:
                await target.add_reaction(emoji)
                await interaction.response.send_message(
                    f"Reagoin viestiin: \"{target.content}\" {emoji}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Ei löytynyt viestiä, joka sisältää annetun hakusanan.", ephemeral=True
                )
        except discord.HTTPException:
            await interaction.response.send_message("Emoji ei kelpaa tai tapahtui virhe.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)