import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
import os

class SoittoModal(discord.ui.Modal, title="Syötä soitettava tiedosto"):
    tiedosto = discord.ui.TextInput(label="Tiedoston nimi", placeholder="esim. musiikki.mp3")

    def __init__(self, vc_id, interaction):
        super().__init__()
        self.vc_id = int(vc_id)
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        vc_channel = self.interaction.client.get_channel(self.vc_id)
        if not isinstance(vc_channel, discord.VoiceChannel):
            await interaction.response.send_message("Virheellinen puhekanava-ID.", ephemeral=True)
            return

        try:
            voice = await vc_channel.connect()
        except discord.ClientException:
            voice = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)

        path = f"./soitettavat/{self.tiedosto.value}"
        if voice and path.endswith(".mp3"):
            if os.path.exists(path):
                voice.play(discord.FFmpegPCMAudio(path))
                await interaction.response.send_message(f"Soitetaan: {self.tiedosto.value}", ephemeral=True)
            else:
                await interaction.response.send_message("Tiedostoa ei löytynyt.", ephemeral=True)
        else:
            await interaction.response.send_message("Tiedosto ei ole kelvollinen tai botti ei liity.", ephemeral=True)

class Soitto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="soitto", description="Soita tiedosto puhekanavalla.")
    async def soitto(self, interaction: discord.Interaction, vc_id: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/soitto")
        await kirjaa_ga_event(self.bot, interaction.user.id, "soitto_komento")
        await interaction.response.send_modal(SoittoModal(vc_id, interaction))
    
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Soitto(bot)
    await bot.add_cog(cog)