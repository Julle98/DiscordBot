from bot.utils.store_utils import (
    hae_tai_paivita_tarjous,
    hae_tarjous_vain,
    nayta_kauppa_embed,
    tarkista_kuponki
)
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
from typing import Optional

class KauppaDropdown(discord.ui.Select):
    def __init__(self, tuotteet: list, tarjoukset: list, bot: commands.Bot):
        options = [
            discord.SelectOption(
                label=t["nimi"],
                description=t["kuvaus"],
                emoji=t.get("emoji", "🛍️")
            )
            for t in tuotteet + tarjoukset
        ]

        options.append(
            discord.SelectOption(
                label="🎟️ Käytä kuponki",
                description="Syötä alennuskoodi ja tuote johon haluat käyttää sen",
                emoji="🎟️"
            )
        )

        super().__init__(placeholder="Valitse tuote...", min_values=1, max_values=1, options=options)
        self.bot = bot
        self.tuotteet = tuotteet
        self.tarjoukset = tarjoukset

    async def callback(self, interaction: discord.Interaction):
        valittu = self.values[0]

        if valittu == "Käytä kuponki":
            await interaction.response.send_modal(KuponkiModal())
            return

        embed = discord.Embed(
            title="Varmistus",
            description=f"Haluatko varmasti ostaa tuotteen **{valittu}**?",
            color=discord.Color.orange()
        )
        view = VarmistusView(valittu, self.bot, self.tarjoukset)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class VarmistusView(discord.ui.View):
    def __init__(self, tuote: str, bot: commands.Bot, tarjoukset: list):
        super().__init__(timeout=60)
        self.tuote = tuote
        self.bot = bot
        self.tarjoukset = tarjoukset

    @discord.ui.button(label="✅ Hyväksy", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.utils.store_utils import osta_command
        await osta_command(self.bot, interaction, self.tuote, self.tarjoukset)
        await interaction.response.edit_message(content=f"Tuote **{self.tuote}** ostettu!", embed=None, view=None)

    @discord.ui.button(label="❌ Peruuta", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Osto peruutettu.", embed=None, view=None)

class KuponkiModal(discord.ui.Modal, title="Syötä kuponki"):
    def __init__(self):
        super().__init__()
        self.koodi = discord.ui.TextInput(label="Kuponki", placeholder="ABC123")
        self.tuote = discord.ui.TextInput(label="Tuotteen nimi", placeholder="VIP-rooli")
        self.add_item(self.koodi)
        self.add_item(self.tuote)

    async def on_submit(self, interaction: discord.Interaction):
        alennus = tarkista_kuponki(self.koodi.value, self.tuote.value, str(interaction.user.id), interaction)
        if alennus > 0:
            await interaction.response.send_message(f"Kuponki hyväksytty! Saat {alennus}% alennusta.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Kuponki ei kelpaa.", ephemeral=True)

class KauppaView(discord.ui.View):
    def __init__(self, bot: commands.Bot, tuotteet: list, tarjoukset: list):
        super().__init__(timeout=None)
        self.add_item(KauppaDropdown(tuotteet, tarjoukset, bot))

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kauppa", description="Näytä kaupan tuotteet")
    @app_commands.describe(
        ohje="Näytä kaupan ohjeet, näyttää vain ohjeet ei kaupanvalikoimaa (valinnainen)"
    )
    @app_commands.checks.has_role("24G")
    async def kauppa(self, interaction: discord.Interaction, ohje: Optional[bool] = False):
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/kauppa")
            await kirjaa_ga_event(self.bot, interaction.user.id, "kauppa_komento")

            if ohje:
                embed = discord.Embed(
                    title="📘 Sannamaija Shopin ohjeet",
                    description="Näin kaupan ostaminen toimii ja mitä kannattaa huomioida:",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="🛒 Ostaminen",
                    value="Valitse tuote dropdownista ja vahvista ostos hyväksyntänapeilla.",
                    inline=False
                )
                embed.add_field(
                    name="🎟️ Kuponkien käyttö",
                    value="Kupongin voi syöttää valitsemalla dropdownista vaihtoehdon '🎟️ Käytä kuponki'.",
                    inline=False
                )
                embed.add_field(
                    name="⁉️ Lisähuomiot",
                    value="• XP ei vähene ostoksia tekemällä.\n• Voit ostaa saman tuotteen kerran kuukaudessa.\n• Tarjoustuotteet vaihtuvat erikoisjaksojen mukaan.",
                    inline=False
                )
                embed.set_footer(text="Tarkastele usein valikoimaa! ☺️")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            tarjoukset = await asyncio.to_thread(hae_tarjous_vain)

            from pathlib import Path
            import json
            tuotteet_polku = Path(os.getenv("JSON_DIRS")) / "valikoima.json"
            try:
                with open(tuotteet_polku, "r", encoding="utf-8") as f:
                    tuotteet = json.load(f)
            except Exception:
                tuotteet = []

            embed = nayta_kauppa_embed(interaction, tarjoukset, tuotteet)

            view = KauppaView(self.bot, tuotteet, tarjoukset)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            try:
                await interaction.response.send_message(f"Tapahtui virhe: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"Tapahtui virhe: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    await bot.add_cog(Store(bot))