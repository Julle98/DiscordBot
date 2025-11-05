import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin, autocomplete_bannatut_käyttäjät
from bot.utils.error_handler import CommandErrorHandler
import psutil
import platform
import datetime
import os

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_monitors(self):
        from utils.moderation_tasks import (
            tarkista_ostojen_kuukausi,
            tarkista_paivat
        )
        if not tarkista_ostojen_kuukausi.is_running():
            tarkista_ostojen_kuukausi.start()
        if not tarkista_paivat.is_running():
            tarkista_paivat.start()

    @app_commands.command(name="ping", description="Näytä botin viive.")
    async def ping(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ping")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ping_komento")
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Botin viive on {latency} ms.")

    @app_commands.command(name="status", description="Näytä botin tilastot ja kuormitus.")
    async def status(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/status")
        await kirjaa_ga_event(self.bot, interaction.user.id, "status_komento")

        latency = round(self.bot.latency * 1000)

        process = psutil.Process()
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_info = process.memory_info()
        memory_usage_mb = memory_info.rss / 1024 / 1024

        uptime_seconds = (datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())).total_seconds()
        uptime_str = str(datetime.timedelta(seconds=int(uptime_seconds)))

        komento_lkm = 0
        log_channel_id = int(os.environ.get("LOG_CHANNEL_ID", 0))
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            now = datetime.datetime.utcnow()
            one_hour_ago = now - datetime.timedelta(hours=1)
            async for msg in log_channel.history(limit=200, after=one_hour_ago):
                if msg.content.startswith("📝 Komento:"):
                    komento_lkm += 1

        komento_ikoni = "🔥" if komento_lkm > 20 else "📉"

        if cpu_percent > 80:
            embed_color = discord.Color.red()
        elif cpu_percent > 50:
            embed_color = discord.Color.orange()
        else:
            embed_color = discord.Color.green()

        embed = discord.Embed(title="🤖 Botin tila", color=embed_color)
        embed.add_field(name="📶 Viive", value=f"{latency} ms", inline=False)
        embed.add_field(name="🧠 CPU-kuorma", value=f"{cpu_percent} %", inline=False)
        embed.add_field(name="💾 Muistinkäyttö", value=f"{memory_usage_mb:.2f} MB", inline=False)
        embed.add_field(name="⏱️ Päälläoloaika", value=uptime_str, inline=False)
        embed.add_field(
            name="📊 Komentoja viimeisen tunnin aikana",
            value=f"{komento_ikoni} {komento_lkm} kpl",
            inline=False
        )
        embed.set_footer(text=f"{platform.system()} {platform.release()}")

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)