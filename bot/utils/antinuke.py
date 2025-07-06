import time
import os
from collections import defaultdict
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
import asyncio
from bot.utils.bot_setup import bot
from functools import wraps
import time
from datetime import datetime, timedelta

def start_moderation_loops():
    asyncio.create_task(check_deletion())

load_dotenv()
NUKE_CHANNEL_ID = int(os.getenv("NUKE_CHANNEL_ID", 0))

EXEMPT_USER_IDS = [600623884198215681]

deletion_counts = defaultdict(lambda: {'roles': 0, 'channels': 0, 'timestamp': time.time()})

DELETE_THRESHOLD = 3
TIME_WINDOW = 3          
        
@tasks.loop(seconds=1)
async def check_deletions():
    current_time = time.time()
    for user_id, data in list(deletion_counts.items()):
        if current_time - data['timestamp'] > TIME_WINDOW:
            deletion_counts.pop(user_id)                    

async def check_deletion(guild, deletion_type):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete if deletion_type == 'roles' else discord.AuditLogAction.channel_delete):
        user = entry.user
        user_id = user.id
        current_time = time.time()

        if user_id in EXEMPT_USER_IDS:
            return

        if user_id in deletion_counts:
            deletion_counts[user_id][deletion_type] += 1
            deletion_counts[user_id]['timestamp'] = current_time
        else:
            deletion_counts[user_id] = {deletion_type: 1, 'timestamp': current_time}

        if deletion_counts[user_id][deletion_type] > DELETE_THRESHOLD:
            try:
                await guild.kick(user, reason=f"Poisti enemmän kuin {DELETE_THRESHOLD} {deletion_type} ajassa {TIME_WINDOW} sekunttia.")
                log_channel = guild.get_channel(NUKE_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"🚨 Käyttäjä {user.mention} potkittiin, koska hän poisti yli {DELETE_THRESHOLD} {deletion_type} {TIME_WINDOW} sekunnin sisällä.")
            except Exception as e:
                print(f"Virhe potkiessa käyttäjää: {e}")
            finally:
                deletion_counts.pop(user_id)

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}

def cooldown(komento_nimi: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            nyt = datetime.now()
            user_id = interaction.user.id
            viimeinen = komento_ajastukset[user_id].get(komento_nimi)

            member = interaction.guild.get_member(user_id)
            nopea_roolit = ["Mestari", "Admin", "Moderaattori"]
            nopea = any(r.name in nopea_roolit for r in member.roles) if member else False
            raja = timedelta(seconds=5 if nopea else 10)

            if viimeinen and nyt - viimeinen < raja:
                erotus = int((raja - (nyt - viimeinen)).total_seconds())
                await interaction.response.send_message(
                    f"Odota {erotus} sekuntia ennen kuin käytät komentoa uudelleen.",
                    ephemeral=True
                )
                return

            komento_ajastukset[user_id][komento_nimi] = nyt
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

from discord.ext import commands
from datetime import datetime, timezone, timedelta

class DeletionWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await check_deletion(role.guild, 'roles')

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await check_deletion(channel.guild, 'channels')
    
async def setup(bot):
    await bot.add_cog(DeletionWatcher(bot))