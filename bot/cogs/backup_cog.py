import discord
from discord.ext import commands, tasks
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SOURCE_DIR = os.getenv("XP_JSON_PATH")
BACKUP_DIR = os.getenv("BACKUP_JSON_PATH")
CONSOLE_LOG = int(os.getenv("CONSOLE_LOG", 0))

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        self.backup_loop.cancel()

    def backup_json_files(self):
        source = Path(SOURCE_DIR)
        backup = Path(BACKUP_DIR)

        if not source.exists() or not backup.exists():
            return ["❌ Polkuja ei löytynyt varmuuskopiointiin."]

        messages = []
        for file in source.glob("*.json"):
            backup_file = backup / file.name

            if not backup_file.exists() or file.stat().st_mtime > backup_file.stat().st_mtime:
                shutil.copy2(file, backup_file)
                messages.append(f"📁 Kopioitu: `{file.name}`")
            else:
                messages.append(f"⏩ Ohitettu (ei muutoksia): `{file.name}`")
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