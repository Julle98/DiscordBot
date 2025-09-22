import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from dotenv import load_dotenv
import os
import asyncio
from bot.utils.error_handler import CommandErrorHandler
import datetime
from datetime import timedelta, timezone
from collections import defaultdict

aktiiviset_paivat = dict()

ajastin_aktiiviset = {}

import os

class ClearModal(discord.ui.Modal, title="Vahvista poisto"):
    def __init__(self, selected_channel: discord.TextChannel):
        super().__init__()
        self.selected_channel = selected_channel

        self.member_id = discord.ui.TextInput(
            label="Jäsenen ID (valinnainen)",
            placeholder="Syötä käyttäjän ID, jos haluat poistaa vain hänen viestejä",
            required=False
        )
        self.amount = discord.ui.TextInput(
            label="Viestien määrä (1–100, valinnainen)",
            placeholder="Jätä tyhjäksi poistaaksesi kaiken (max 100)",
            required=False
        )
        self.confirmation = discord.ui.TextInput(
            label="Kirjoita KYLLÄ vahvistaaksesi",
            placeholder="KYLLÄ"
        )

        self.add_item(self.member_id)
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

        member_id = self.member_id.value.strip()
        member = None
        if member_id:
            try:
                member = await interaction.guild.fetch_member(int(member_id))
            except (discord.NotFound, discord.HTTPException, ValueError):
                await interaction.followup.send("Virheellinen jäsenen ID.", ephemeral=True)
                return

        def check(msg):
            return (not member or msg.author.id == member.id)

        try:
            poistettu = await self.selected_channel.purge(limit=määrä, check=check)
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
                        f"🧹 **{interaction.user}** poisti {määrä_poistettu} viestiä kanavasta {self.selected_channel.mention}"
                        + (f" käyttäjältä {member.mention}." if member else ".")
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
                uusi_sivu = view.sivu + 1
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

aktiiviset_paivat = dict()

class Moderation_messages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="toiminta", description="Näytä aktiivisin kanava per jäsen")
    @app_commands.describe(jäsen="Valitse jäsen")
    @app_commands.checks.has_role("Mestari")
    async def toiminta(self, interaction: discord.Interaction, jäsen: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/toiminta")
        await kirjaa_ga_event(self.bot, interaction.user.id, "toiminta_komento")
        await interaction.response.defer(ephemeral=True)

        viestimäärät = {}

        kanavat = [
            c for c in interaction.guild.text_channels
            if c.permissions_for(jäsen).read_messages and c.permissions_for(interaction.guild.me).read_message_history
        ]

        async def hae_viestit(kanava: discord.TextChannel, jäsen: discord.Member, limit=100):
            count = 0
            async for msg in kanava.history(limit=limit):
                if msg.author == jäsen:
                    count += 1
            return count

        for kanava in kanavat:
            try:
                count = await asyncio.wait_for(hae_viestit(kanava, jäsen), timeout=5)
                if count > 0:
                    viestimäärät[kanava] = count
            except (discord.Forbidden, asyncio.TimeoutError):
                continue

        if not viestimäärät:
            await interaction.followup.send(
                f"**{jäsen.display_name}** ei ole lähettänyt viestejä viimeaikoina näkyvissä kanavissa.",
                ephemeral=True
            )
            return

        aktiivisin = max(viestimäärät, key=viestimäärät.get)
        määrä = viestimäärät[aktiivisin]
        await interaction.followup.send(
            f"📊 **{jäsen.display_name}** on ollut aktiivisin kanavassa {aktiivisin.mention} "
            f"({määrä} viestiä viimeisimmistä 100:sta per kanava).",
            ephemeral=True
        )

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

    @app_commands.command(name="aktiivisimmat", description="Näytä aktiivisimmat käyttäjät tai aloita viestiseuranta.")
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

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_messages(bot)
    await bot.add_cog(cog)