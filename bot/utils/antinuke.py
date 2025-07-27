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
import uuid
from bot.utils.xp_utils import anna_xp_komennosta
from discord.ui import Button, View
from discord import Embed
import os
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

xp_approval_requests = {}  

XP_ALERT_THRESHOLD = 150  
MODLOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

XP_REQUEST_TIMEOUT = timedelta(minutes=10)

def has_mestari_role(member):
    return any(role.name == "Mestari" for role in member.roles)

async def alert_xp_request(bot, user_id, xp_amount, interaction):
    if xp_amount < XP_ALERT_THRESHOLD:
        return True

    req_id = str(uuid.uuid4())[:8]
    xp_approval_requests[req_id] = {
        "user_id": user_id,
        "xp_amount": xp_amount,
        "requester": interaction.user.id,
        "timestamp": datetime.utcnow()
    }

    modlog_channel = bot.get_channel(MODLOG_CHANNEL_ID)
    is_decrease = xp_amount < 0
    abs_xp = abs(xp_amount)
    target = interaction.guild.get_member(user_id)

    embed = Embed(
        title="🚨 XP-hälytys: suuri " + ("vähennys!" if is_decrease else "lisäys!"),
        description=(
            f"👤 Kohde: {target.mention if target else user_id}\n"
            f"{'📉 XP määrä: -' + str(abs_xp) if is_decrease else '📈 XP määrä: ' + str(abs_xp)}\n"
            f"🙋‍♂️ Pyytäjä: {interaction.user.mention}\n\n"
            f"✅ Hyväksy tai ❌ peruuta alla olevista painikkeista."
        ),
        color=discord.Color.red() if is_decrease else discord.Color.orange()
    )

    await modlog_channel.send(embed=embed, view=XPApprovalView(req_id, user_id, xp_amount))
    return False

class XPFileChangeHandler(FileSystemEventHandler):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.last_known_data = read_xp_data()

    def on_modified(self, event):
        if event.src_path != os.getenv("XP_JSON_PATH"):
            return
        
        current_data = read_xp_data()
        for user_id, current_xp in current_data.items():
            previous_xp = self.last_known_data.get(user_id, 0)
            delta = current_xp - previous_xp

            if abs(delta) >= XP_ALERT_THRESHOLD:
                class MockInteraction:
                    user = type("User", (), {"mention": "*automaattinen*", "id": 0})
                    guild = self.bot.guilds[0] if self.bot.guilds else None

                asyncio.create_task(alert_xp_request(self.bot, user_id, delta, MockInteraction()))

            self.last_known_data[user_id] = current_xp

def read_xp_data():
    json_path = os.getenv("XP_JSON_PATH")
    if not json_path or not os.path.exists(json_path):
        print(f"XP JSON tiedostoa ei löytynyt polusta: {json_path}")
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(user_id): int(xp) for user_id, xp in data.items()}
    except Exception as e:
        print(f"Virhe luettaessa XP JSON-tiedostoa: {e}")
        return {}

async def xp_monitor_loop(bot):
    await bot.wait_until_ready()
    last_known_data = {}  

    while not bot.is_closed():
        try:
            current_data = read_xp_data()  

            for user_id, current_xp in current_data.items():
                previous_xp = last_known_data.get(user_id, 0)
                delta = current_xp - previous_xp

                if abs(delta) >= XP_ALERT_THRESHOLD:
                    await alert_xp_request(bot, user_id, delta, interaction=None)

                last_known_data[user_id] = current_xp

        except Exception as e:
            print(f"Virhe XP-monitoroinnissa: {e}")

        await asyncio.sleep(60)  

class XPApprovalView(View):
    def __init__(self, req_id, user_id, xp_amount):
        super().__init__(timeout=XP_REQUEST_TIMEOUT.total_seconds())
        self.req_id = req_id
        self.user_id = user_id
        self.xp_amount = xp_amount

    @discord.ui.button(label="Hyväksy XP", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not has_mestari_role(interaction.user):
            await interaction.response.send_message("🚫 Vain Mestari-rooli voi hyväksyä XP:n.", ephemeral=True)
            return

        data = xp_approval_requests.pop(self.req_id, None)
        if not data or datetime.utcnow() - data["timestamp"] > XP_REQUEST_TIMEOUT:
            await interaction.response.send_message("⏳ Pyyntö on vanhentunut tai ei kelvollinen.", ephemeral=True)
            return

        dummy_interaction = type("DummyInteraction", (), {
            "user": interaction.guild.get_member(self.user_id),
            "channel": interaction.channel,
            "guild": interaction.guild
        })()
        await anna_xp_komennosta(interaction.client, dummy_interaction, self.xp_amount)
        await interaction.response.send_message(f"✅ {self.xp_amount} XP lisätty käyttäjälle <@{self.user_id}>.")

    @discord.ui.button(label="Peruuta", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not has_mestari_role(interaction.user):
            await interaction.response.send_message("🚫 Vain Mestari-rooli voi peruuttaa XP:n.", ephemeral=True)
            return

        if self.req_id in xp_approval_requests:
            xp_approval_requests.pop(self.req_id)
            await interaction.response.send_message(f"❌ XP-pyyntö {self.req_id} peruttu.")
        else:
            await interaction.response.send_message("❌ Pyyntöä ei löytynyt.", ephemeral=True)

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