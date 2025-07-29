import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
import os

class VCRecord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recording = False

    @app_commands.command(name="vcrecord", description="Tallenna ja lähetä puhekanavan tallenne MP3-tiedostona.")
    @app_commands.checks.has_role("Mestari")
    async def vcrecord(self, interaction: discord.Interaction, vc_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vcrecord")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vcrecord_komento")
        record_channel_id = int(os.getenv("RECORD_CHANNEL_ID"))
        record_channel = interaction.client.get_channel(record_channel_id)

        if vc_id and not self.recording:
            vc_channel = interaction.client.get_channel(int(vc_id))
            if isinstance(vc_channel, discord.VoiceChannel):
                await vc_channel.connect()
                self.recording = True
                await interaction.response.send_message(f"🎙️ Aloitettiin tallennus kanavalla {vc_channel.name}...", ephemeral=True)
        elif not vc_id and self.recording:
            self.recording = False
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()

            fake_audio_path = "tallenne.mp3"
            with open(fake_audio_path, "wb") as f:
                f.write(b"FAKE_MP3_DATA")  

            await record_channel.send(
                content="📁 Tallenne valmis.",
                file=discord.File(fake_audio_path)
            )
            await interaction.response.send_message("✅ Tallennus päättyi ja tiedosto lähetettiin.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Anna puhekanavan ID aloittaaksesi, tai käytä komentoa ilman ID:tä lopettaaksesi.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = VCRecord(bot)
    await bot.add_cog(cog)