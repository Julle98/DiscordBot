import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from bot.utils.error_handler import CommandErrorHandler
from typing import Optional
from discord import Embed, Colour
import pytz
import datetime
from datetime import datetime
import os

class HuoltoModal(discord.ui.Modal, title="Huoltotiedot"):
    kesto = discord.ui.TextInput(
        label="Huollon kesto",
        placeholder="Esim. 10s, 5m",
        custom_id="kesto"
    )
    lisatiedot = discord.ui.TextInput(
        label="Lisätiedot",
        style=discord.TextStyle.paragraph,
        custom_id="lisatiedot"
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            kesto = self.kesto.value
            lisatiedot = self.lisatiedot.value
            seconds = int(kesto[:-1])
            unit = kesto[-1]
            delay = seconds if unit == "s" else seconds * 60 if unit == "m" else seconds * 3600 if unit == "h" else None
            if not delay:
                await interaction.response.send_message("Virheellinen aikamuoto!", ephemeral=True)
                return

            huolto_kanava = discord.utils.get(interaction.guild.text_channels, name="🛜bot-status") \
                or await interaction.guild.create_text_channel(name="🛜bot-status")

            bot_name = interaction.client.user.name
            bot_avatar_url = interaction.client.user.avatar.url if interaction.client.user.avatar else None
            bot_version = os.getenv("BOT_VERSION", "tuntematon")
            aika = datetime.now(pytz.timezone('Europe/Helsinki')).strftime('%d-%m-%Y %H:%M:%S')

            embed = discord.Embed(
                title=f"🟠 {bot_name} huoltotilassa",
                description=f"Botti on huollossa arviolta {kesto}.",
                color=discord.Color.orange()
            )
            if bot_avatar_url:
                embed.set_thumbnail(url=bot_avatar_url)
            embed.add_field(name="🕒 Huollon aloitusaika", value=aika, inline=False)
            embed.add_field(name="📋 Lisätiedot", value=lisatiedot or "Ei lisätietoja", inline=False)
            embed.add_field(
                name="🛠️ Ongelmatilanteet",
                value="Käytä komentoa `/help` tai kirjoita <#1339858713804013598> kanavalle.",
                inline=False
            )
            embed.set_footer(text=f"Versio: {bot_version}")

            await huolto_kanava.send(embed=embed)
            await interaction.response.send_message(
                f"Huoltotiedot lähetetty kanavalle {huolto_kanava.mention}.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"Tapahtui virhe: {e}", ephemeral=True)

class HuoltoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Anna huollon tiedot", style=discord.ButtonStyle.primary)
    async def anna_tiedot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HuoltoModal())

ajastin_aktiiviset = {}

class Moderation_status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def ilmoita_statuskanavalle(self, interaction: discord.Interaction, tila: str, kuvaus: str, vari: Colour):
        status_kanava = discord.utils.get(interaction.guild.text_channels, name="🛜bot-status")
        if not status_kanava:
            status_kanava = await interaction.guild.create_text_channel(name="🛜bot-status")

        async for msg in status_kanava.history(limit=100):
            await msg.delete()

        timezone = pytz.timezone('Europe/Helsinki')
        aika = datetime.now(timezone).strftime('%d-%m-%Y %H:%M:%S')
        bot_name = self.bot.user.name
        bot_avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None
        bot_version = os.getenv("BOT_VERSION", "tuntematon")

        otsikko_map = {
            "sammutus": f"🔴 {bot_name} on sammutettu",
            "huolto": f"🟠 {bot_name} huoltotilassa",
            "uudelleenkäynnistys": f"🟡 {bot_name} käynnistyy uudelleen"
        }

        embed = Embed(
            title=otsikko_map.get(tila, "ℹ️ Botin tila"),
            description=kuvaus,
            color=vari
        )

        if bot_avatar_url:
            embed.set_thumbnail(url=bot_avatar_url)
        embed.add_field(name="🕒 Aika", value=aika, inline=False)
        embed.add_field(
            name="🛠️ Ongelmatilanteet",
            value="Käytä komentoa `/help` tai kirjoita <#1339858713804013598> kanavalle.",
            inline=False
        )
        embed.set_footer(text=f"Versio: {bot_version}")

        await status_kanava.send(embed=embed)

    @app_commands.command(name="huolto", description="Aseta botti huoltotilaan.")
    @app_commands.checks.has_role("Mestari")
    async def huolto(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/huolto")
        await kirjaa_ga_event(self.bot, interaction.user.id, "huolto_komento")
        await interaction.response.send_message(
            "Paina alla olevaa painiketta antaaksesi huollon tiedot:",
            view=HuoltoView(), ephemeral=True
        )

    @app_commands.command(name="sammutus", description="Ilmoita botin sammutuksesta.")
    @app_commands.describe(syy="Valinnainen syy sammutukselle")
    @app_commands.checks.has_role("Mestari")
    async def sammutus(self, interaction: discord.Interaction, syy: Optional[str] = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/sammutus")
        await kirjaa_ga_event(self.bot, interaction.user.id, "sammutus_komento")

        kuvaus = "Botti on asetettu sammuneeksi ja ei ole tällä hetkellä käytettävissä."
        if syy:
            kuvaus += f"\n**Syy:** {syy}"

        await self.ilmoita_statuskanavalle(interaction, "sammutus", kuvaus, Colour.red())
        await interaction.response.send_message("Sammutustieto lähetetty statuskanavalle.", ephemeral=True)

    @app_commands.command(name="uudelleenkäynnistys", description="Ilmoita botin uudelleenkäynnistyksestä.")
    @app_commands.describe(syy="Valinnainen syy uudelleenkäynnistykselle")
    @app_commands.checks.has_role("Mestari")
    async def uudelleenkaynnistys(self, interaction: discord.Interaction, syy: Optional[str] = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/uudelleenkäynnistys")
        await kirjaa_ga_event(self.bot, interaction.user.id, "uudelleenkäynnistys_komento")

        kuvaus = "Botti on asetettu uudelleenkäynnistystilaan."
        if syy:
            kuvaus += f"\n**Syy:** {syy}"

        await self.ilmoita_statuskanavalle(interaction, "uudelleenkäynnistys", kuvaus, Colour.gold())
        await interaction.response.send_message("Uudelleenkäynnistystieto lähetetty statuskanavalle.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_status(bot)
    await bot.add_cog(cog)