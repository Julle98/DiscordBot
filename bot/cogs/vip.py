import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
import asyncio
import random
from discord.ui import Modal
import re
import asyncio
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler

class MielipideModal(Modal):
    def __init__(self):
        super().__init__(title="Anna mielipide")
        self.kohde = discord.ui.TextInput(
            label="Mielipiteen kohde",
            placeholder="Kirjoita kohde, josta haluat mielipiteen",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.kohde)

    async def on_submit(self, interaction: discord.Interaction):
        kohde = self.kohde.value
        vastaukset = [
            ("W", 50),
            ("L", 42),
            ("Ehdottomasti", 3),
            ("En usko", 2),
            ("Vaikea sanoa", 1),
            ("Mahdollisesti", 1),
            ("Ei todellakaan", 1)
        ]

        valinta = random.choices(
            population=[v[0] for v in vastaukset],
            weights=[v[1] for v in vastaukset],
            k=1
        )[0]

        await interaction.response.send_message(
            f"Mielipiteeni kohteesta **{kohde}** on **{valinta}**"
        )

async def ajastin_odotus(interaction: discord.Interaction, sekunnit: int):
    try:
        await asyncio.sleep(sekunnit)
        await interaction.user.send(f"Hei {interaction.user.mention}, aikasi on kulunut!")
    except asyncio.CancelledError:
        try:
            await interaction.user.send("Ajastimesi keskeytettiin, koska botti sammutettiin.")
        except discord.Forbidden:
            pass

class Vip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="sano", description="Sano Sannamaijalle sanottavaa.")
    @app_commands.checks.has_role("24G")
    async def sano(self, interaction: discord.Interaction, viesti: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/sano")
        await kirjaa_ga_event(self.bot, interaction.user.id, "sano_komento")
        kielletyt_sanat = ["nigger", "nigga", "nig", "ni", "nigg", "nigge", "nekru", "nekrut", "ammun", "tapan", "tappaa", "tapan sinut", "peppu", "perse", "pillu", "kikkeli", "penis"]

        if any(re.search(rf"\b{kielletty}\b", viesti, re.IGNORECASE) for kielletty in kielletyt_sanat):
            await interaction.response.send_message("Viestisi sisältää kiellettyjä sanoja, eikä sitä lähetetty.", ephemeral=True)
        else:
            try:
                await interaction.response.send_message(viesti)
            except discord.Forbidden:
                await interaction.response.send_message("Minulla ei ole oikeuksia lähettää viestejä tähän kanavaan.", ephemeral=True)
            except discord.HTTPException:
                await interaction.response.send_message("Viestin lähetys epäonnistui.", ephemeral=True)
    
    @app_commands.command(name="mielipide", description="Kysy mielipide Sannamaijalta.")
    @app_commands.checks.has_role("24G")
    async def mielipide(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/mielipide")
        await kirjaa_ga_event(self.bot, interaction.user.id, "mielipide_komento")
        await interaction.response.send_modal(MielipideModal())

    ajastin_aktiiviset = {}

    @app_commands.command(name="ajastin", description="Aseta ajastin ja saat ilmoituksen Sannamaijalta.")
    @app_commands.describe(aika="Aika muodossa esim. 2m30s, 1m, 45s")
    @app_commands.checks.has_role("24G")
    async def ajastin(self, interaction: discord.Interaction, aika: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ajastin")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ajastin_komento")
        aika = aika.lower().replace(" ", "")
        pattern = r'(?:(\d+)m)?(?:(\d+)s)?'
        match = re.fullmatch(pattern, aika)

        if not match:
            await interaction.response.send_message("Anna aika muodossa esim. `2m30s`, `15m`, `45s`.", ephemeral=True)
            return

        minuutit = int(match.group(1)) if match.group(1) else 0
        sekunnit = int(match.group(2)) if match.group(2) else 0
        kokonais = minuutit * 60 + sekunnit

        if kokonais == 0:
            await interaction.response.send_message("Ajan täytyy olla yli 0 sekuntia!", ephemeral=True)
            return

        await interaction.response.send_message(f"Ajastin asetettu **{kokonais} sekunnille**!")
        task = asyncio.create_task(ajastin_odotus(interaction, kokonais))
        self.ajastin_aktiiviset[interaction.user.id] = task

    @app_commands.command(name="muistuta", description="Aseta muistutus itsellesi.")
    @app_commands.describe(aika="Esim. 2m30s", viesti="Mitä haluat muistaa?")
    @app_commands.checks.has_role("24G")
    async def muistuta(self, interaction: discord.Interaction, aika: str, viesti: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/muistuta")
        await kirjaa_ga_event(self.bot, interaction.user.id, "muistuta_komento")
        pattern = r'(?:(\d+)m)?(?:(\d+)s)?'
        match = re.fullmatch(pattern, aika.lower().replace(" ", ""))
        if not match:
            await interaction.response.send_message("Anna aika muodossa esim. `2m30s`, `15m`, `45s`.", ephemeral=True)
            return

        minuutit = int(match.group(1)) if match.group(1) else 0
        sekunnit = int(match.group(2)) if match.group(2) else 0
        kokonais = minuutit * 60 + sekunnit

        if kokonais == 0:
            await interaction.response.send_message("Ajan täytyy olla yli 0 sekuntia!", ephemeral=True)
            return

        await interaction.response.send_message(f"Muistutus asetettu **{kokonais} sekunnin** päähän!", ephemeral=True)

        async def muistutus():
            await asyncio.sleep(kokonais)
            try:
                await interaction.user.send(f"🔔 Muistutus: {viesti}")
            except discord.Forbidden:
                pass

        asyncio.create_task(muistutus())

    @app_commands.command(name="ennustus", description="Saat mystisen ennustuksen.")
    @app_commands.checks.has_role("24G")
    async def ennustus(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ennustus")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ennustus_komento")
        ennustukset = [
            "Tähtien mukaan sinua odottaa yllätys.",
            "Varjoista nousee uusi mahdollisuus.",
            "Älä luota ensimmäiseen vaikutelmaan.",
            "Kohtalo kääntyy puolellesi pian.",
            "Hiljaisuudessa piilee vastaus.",
            "Joku läheinen kaipaa huomiotasi.",
            "Tulevaisuus on sumuinen, mutta toivoa on."
        ]
        valinta = random.choice(ennustukset)
        await interaction.response.send_message(f"🔮 Ennustus: *{valinta}*")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Vip(bot)
    await bot.add_cog(cog)