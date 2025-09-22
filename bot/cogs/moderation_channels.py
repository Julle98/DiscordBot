import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from dotenv import load_dotenv
import os
from bot.utils.error_handler import CommandErrorHandler

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

class Moderation_channels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @app_commands.command(name="lukitse", description="Lukitsee kanavan kaikilta.")
    @app_commands.checks.has_role("Mestari")
    async def lukitse(self, interaction: discord.Interaction, kanava: discord.TextChannel):
        await kirjaa_komento_lokiin(self.bot, interaction, "/lukitse")
        await kirjaa_ga_event(self.bot, interaction.user.id, "lukitse_komento")
        await kanava.set_permissions(interaction.guild.default_role, send_messages=False)
        await kanava.set_permissions(interaction.user, send_messages=True)
        await interaction.response.send_message(f"Kanava {kanava.mention} on lukittu onnistuneesti!", ephemeral=True)

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
    cog = Moderation_channels(bot)
    await bot.add_cog(cog)