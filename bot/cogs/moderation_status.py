import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from bot.utils.error_handler import CommandErrorHandler
import pytz
import datetime

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

ajastin_aktiiviset = {}

class Moderation_status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
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
    
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_status(bot)
    await bot.add_cog(cog)