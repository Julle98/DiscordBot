import discord
from discord.ext import commands, tasks
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SOURCE_DIR = os.getenv("XP_JSON_PATH")
SOURCE_DIRS_SINGLE = os.getenv("JSON_DIR")
SOURCE_DIRS_MULTI = os.getenv("JSON_DIRS")
BACKUP_DIR = os.getenv("BACKUP_JSON_PATH")
CONSOLE_LOG = int(os.getenv("CONSOLE_LOG", 0))

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    def get_all_source_dirs(self):
        dirs = []

        if SOURCE_DIR and Path(SOURCE_DIR).exists():
            dirs.append(Path(SOURCE_DIR))

        if SOURCE_DIRS_SINGLE and Path(SOURCE_DIRS_SINGLE).exists():
            dirs.append(Path(SOURCE_DIRS_SINGLE))

        if SOURCE_DIRS_MULTI:
            for d in SOURCE_DIRS_MULTI.split(","):
                path = Path(d.strip())
                if path.exists():
                    dirs.append(path)

        return dirs

    def format_path(self, path: Path):
        parts = path.parts
        try:
            index = parts.index("DiscordBot-main")
            return Path(*parts[index:])
        except ValueError:
            return path

    def backup_json_files(self):
        backup = Path(BACKUP_DIR)
        if not backup.exists():
            return ["❌ Varmuuskopiohakemistoa ei löytynyt."]

        messages = []
        for source in self.get_all_source_dirs():
            for file in source.glob("*.json"):
                backup_file = backup / file.name
                display_path = self.format_path(file)
                if not backup_file.exists() or file.stat().st_mtime > backup_file.stat().st_mtime:
                    shutil.copy2(file, backup_file)
                    messages.append(f"📁 Kopioitu: `{file.name}` ({display_path.parent})")
                else:
                    messages.append(f"⏩ Ohitettu: `{file.name}` ({display_path.parent})")

        if not messages:
            messages.append("ℹ️ Ei JSON-tiedostoja varmuuskopioitavaksi.")
        return messages

    async def send_backup_report(self, messages: list, title: str):
        if CONSOLE_LOG:
            channel = self.bot.get_channel(CONSOLE_LOG)
            if channel:
                embed = discord.Embed(
                    title=title,
                    description="\n".join(messages),
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text="BackupCog")
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.backup_loop.is_running():
            self.backup_loop.start()
        messages = self.backup_json_files()
        await self.send_backup_report(messages, "🚀 Botti käynnistetty – varmuuskopiointi suoritettu")

    @tasks.loop(minutes=360)
    async def backup_loop(self):
        try:
            messages = self.backup_json_files()
            await self.send_backup_report(messages, "🔄 JSON-varmuuskopiointi suoritettu")
        except Exception as e:
            print(f"❌ Varmuuskopiointi epäonnistui: {e}")

    @backup_loop.before_loop
    async def before_backup_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BackupCog(bot))