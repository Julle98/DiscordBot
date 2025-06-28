import time
import os
from collections import defaultdict
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
import asyncio
from bot.utils.bot_setup import bot

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
    
@bot.event
async def on_guild_role_delete(role):
    await check_deletion(role.guild, 'roles')

@bot.event
async def on_guild_channel_delete(channel):
    await check_deletion(channel.guild, 'channels')            

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