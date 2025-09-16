from bot.utils.bot_setup import bot
from bot.utils.xp_utils import calculate_level, save_xp_data, load_xp_data

import json, random, discord, os, asyncio
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone, time as dtime
from pathlib import Path
import json

def start_tasks_loops():
    if not rotate_daily_tasks.is_running():
        rotate_daily_tasks.start()
    if not rotate_weekly_tasks.is_running():
        rotate_weekly_tasks.start()
    if not rotate_monthly_tasks.is_running():
        rotate_monthly_tasks.start()

load_dotenv()

XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))
TASK_DATA_CHANNEL_ID = int(os.getenv("TASK_DATA_CHANNEL_ID", 0))
VOICE_EVENT_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))
TASK_CHANNEL_ID = int(os.getenv("TASK_CHANNEL_ID", 0))
TASK_LOG_CHANNEL_ID = int(os.getenv("TASK_LOG_CHANNEL_ID", 0))
MEME_CHANNEL_ID = int(os.getenv("MEME_CHANNEL_ID", 0))
TASK_REWARD_XP = 50
TASK_REWARD_ROLE_ID = 1379050552905695282

active_listeners = {}

DAILY_TASKS = [
    "Lähetä viesti tiettyyn aikaan",
    "Käy yleinen kanavalla lähettämässä viesti",
    "Mainitse toinen käyttäjä",
    "Osallistu puhekanavaan",
    "Reagoi viestiin emojilla",
    "Lähetä tiedosto",
    "Lähetä meemi",
    "Striimaa peliäsi",
    "Lisää tarra viestiin",
    "Kerro viikonpäivä",
    "Lähetä viesti, jossa on kysymys",
    "Mainitse kanava viestissä",
    "Lähetä Tenor-linkki",
    "Lähetä Giphy-linkki",
    "Lähetä viesti, jossa on linkki",
    "Vastaa toisen käyttäjän viestiin"
]

WEEKLY_TASKS = [
    "Käytä bottikomentoja",
    "Lähetä kuva tai liite",
    "Äänestä reaktioilla",
    "Lähetä viesti viikonloppuna",
    "Tee kysely",
    "Osta jotain kaupasta",
    "Lähetä viesti arkipäivänä",
    "Kysy jotain toiselta käyttäjältä",
    "Lisää reaktio toisen viestiin, jota ei ole vielä reagoitu",
    "Lähetä viesti, jossa on yli 10 sanaa"
]

MONTHLY_TASKS = [
    "Aloita keskustelu",
    "Kerää reaktioita",
    "Jaa kuva, josta syntyy vitsi tai reaktio"
]

from pathlib import Path
import json

JSON_DIR = Path(os.getenv("JSON_DIR"))
TASKS_PATH = JSON_DIR / "tasks.json"

def parse_task_message(content: str):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None

def load_tasks():
    if TASKS_PATH.exists():
        with open(TASKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tasks(data):
    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)  
    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def load_user_tasks():
    channel = bot.get_channel(TASK_DATA_CHANNEL_ID)
    if not channel:
        return {}
    history = [m async for m in channel.history(limit=200)]
    result = {}
    for m in history:
        msg = parse_task_message(m.content)
        if msg and msg.get("type") == "user_task":
            uid = msg["user_id"]
            task = msg["task"]
            timestamp = msg.get("timestamp")
            result.setdefault(uid, []).append({
                "task": task,
                "timestamp": timestamp
            })
    return result

async def save_user_task(user_id, task):
    channel = bot.get_channel(TASK_DATA_CHANNEL_ID)
    if channel:
        await channel.send(json.dumps({
            "type": "user_task",
            "user_id": user_id,
            "task": task,
            "timestamp": datetime.now().isoformat()
        }, indent=2))
            
async def add_xp(bot, user: discord.Member, amount: int):
    user_id = str(user.id)
    xp_channel = bot.get_channel(XP_CHANNEL_ID)
    if not xp_channel:
        return

    xp_data = load_xp_data()
    user_info = xp_data.get(user_id, {"xp": 0, "level": 0})

    user_info["xp"] += amount
    new_level = calculate_level(user_info["xp"])

    if new_level > user_info["level"]:
        await xp_channel.send(f"{user.mention} saavutti tason {new_level}! 🎉")

    user_info["level"] = new_level
    xp_data[user_id] = user_info
    save_xp_data(xp_data)


def give_role(user: discord.Member, role_id: int):
    role = user.guild.get_role(role_id)
    if role:
        asyncio.create_task(user.add_roles(role))

def select_random_task(tasks, last_task):
    choices = [t for t in tasks if t != last_task]
    return random.choice(choices) if choices else random.choice(tasks)

JSON_DIR = Path(os.getenv("JSON_DIR"))
STREAKS_PATH = JSON_DIR / "streaks.json"

def normalize_streaks(streaks):
    for uid, user_data in streaks.items():
        for key in ["daily", "weekly", "monthly"]:
            user_data.setdefault(key, {
                "last_completed": None,
                "streak": 0,
                "rewards": []
            })
    return streaks

def load_streaks():
    if STREAKS_PATH.exists():
        with open(STREAKS_PATH, "r", encoding="utf-8") as f:
            streaks = json.load(f)
            return normalize_streaks(streaks)
    return {}

def save_streaks(data):
    STREAKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STREAKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def onko_tehtava_suoritettu_ajankohtaisesti(tehtava, suoritukset):
    nyt = datetime.now()
    for suoritus in suoritukset:
        if suoritus["task"] != tehtava:
            continue
        try:
            aika = datetime.fromisoformat(suoritus["timestamp"])
            if tehtava in DAILY_TASKS and aika.date() == nyt.date():
                return True
            if tehtava in WEEKLY_TASKS and aika.isocalendar()[1] == nyt.isocalendar()[1]:
                return True
            if tehtava in MONTHLY_TASKS and aika.month == nyt.month and aika.year == nyt.year:
                return True
        except:
            continue
    return False

def onko_tehtava_liian_aikaisin(tehtava, suoritukset, minuutteja=2):
    nyt = datetime.now()
    for suoritus in suoritukset:
        if suoritus["task"] == tehtava:
            try:
                aika = datetime.fromisoformat(suoritus["timestamp"])
                if (nyt - aika) < timedelta(minutes=minuutteja):
                    return True
            except:
                continue
    return False

async def update_streak(user: discord.Member, task_type: str):
    now = datetime.now().date()
    uid = str(user.id)
    streaks = load_streaks()

    user_data = streaks.setdefault(uid, {
        "daily": {},
        "weekly": {},
        "monthly": {}
    })

    data = user_data.setdefault(task_type, {
        "last_completed": None,
        "streak": 0,
        "max_streak": 0,
        "rewards": []
    })

    last_date = datetime.strptime(data["last_completed"], "%Y-%m-%d").date() if data["last_completed"] else None
    streak = data["streak"]
    was_reset = False
    already_completed = last_date == now

    if task_type == "daily":
        if last_date == now - timedelta(days=1):
            streak += 1
        elif not already_completed:
            streak = 1
            was_reset = True

    elif task_type == "weekly":
        if last_date and 7 <= (now - last_date).days <= 13:
            streak += 1
        elif not already_completed:
            streak = 1
            was_reset = True

    elif task_type == "monthly":
        if last_date and 28 <= (now - last_date).days <= 45:
            streak += 1
        elif not already_completed:
            streak = 1
            was_reset = True

    data["last_completed"] = now.isoformat()
    data["streak"] = streak
    if streak > data.get("max_streak", 0):
        data["max_streak"] = streak

    save_streaks(streaks)

    task_channel = user.guild.get_channel(TASK_CHANNEL_ID)
    task_log_channel = bot.get_channel(TASK_LOG_CHANNEL_ID)
    if was_reset and task_log_channel:
        await task_log_channel.send(
            f"{user.mention}, streakisi nollautui ja alkoi alusta tehtävällä **{task_type}**! Uusi putki käynnissä! 🔄"
        )

    rewards = data["rewards"]

    if task_type == "daily":
        if streak == 7 and "7_day" not in rewards:
            await add_xp(bot, user, 200)
            give_role(user, 1380234239357882450)
            rewards.append("7_day")
            await task_channel.send(f"{user.mention} saavutti **7 päivän** päivittäistehtäväputken! +200 XP ja erikoisrooli! 🎉")

        elif streak == 30 and "30_day" not in rewards:
            await add_xp(bot, user, 900)
            give_role(user, 1380234364826419220)
            rewards.append("30_day")
            await task_channel.send(f"{user.mention} saavutti **30 päivän** päivittäistehtäväputken! +900 XP ja erikoisrooli! 🔥")

    elif task_type == "weekly":
        if streak == 4 and "4_week" not in rewards:
            await add_xp(bot, user, 250)
            give_role(user, 1380234433533055057)
            rewards.append("4_week")
            await task_channel.send(f"{user.mention} suoritti **4 viikkoa putkeen** viikkotehtäviä! +250 XP ja erikoisrooli! 🎉")

        elif streak == 12 and "12_month" not in rewards:
            await add_xp(bot, user, 3000)
            give_role(user, 1380234668032659509)
            rewards.append("12_month")
            await task_channel.send(f"{user.mention} suoritti **12 kuukautta putkeen** viikkotehtäviä! +3000 XP ja erikoisrooli! 🔥")

    elif task_type == "monthly":
        if streak == 3 and "3_month" not in rewards:
            await add_xp(bot, user, 500)
            give_role(user, 1386679979634327663)
            rewards.append("3_month")
            await task_channel.send(f"{user.mention} suoritti **3 kuukautta putkeen** kuukausitehtäviä! +500 XP ja erikoisrooli! 🏅")

        elif streak == 6 and "6_month" not in rewards:
            await add_xp(bot, user, 1200)
            give_role(user, 1386680073486204999)
            rewards.append("6_month")
            await task_channel.send(f"{user.mention} suoritti **6 kuukautta putkeen** kuukausitehtäviä! +1200 XP ja erikoisrooli! 🏆")

    return was_reset
       
@tasks.loop(time=dtime(0, 0))
async def rotate_daily_tasks():
    data = load_tasks()
    selected = select_random_task(DAILY_TASKS, data.get("last_daily"))
    data["daily_tasks"] = [selected]
    data["last_daily"] = selected
    save_tasks(data)

from discord.ext import tasks
from datetime import datetime, timezone
from datetime import datetime, timezone, time as dtime

@tasks.loop(time=dtime(0, 0))
async def rotate_weekly_tasks():
    now = datetime.now(timezone.utc)
    if now.weekday() != 0:  # 1 = tiistai
        return
    data = load_tasks()
    selected = select_random_task(WEEKLY_TASKS, data.get("last_weekly"))
    data["weekly_tasks"] = [selected]
    data["last_weekly"] = selected
    save_tasks(data)

@tasks.loop(time=dtime(0, 0))
async def rotate_monthly_tasks():
    now = datetime.now(timezone.utc)
    if now.day != 1:
        return
    data = load_tasks()
    selected = select_random_task(MONTHLY_TASKS, data.get("last_monthly"))
    data["monthly_tasks"] = [selected]
    data["last_monthly"] = selected
    save_tasks(data)
        
class TaskListener(discord.ui.View):
    def __init__(self, user: discord.Member, channel: discord.TextChannel, task_name: str):
        super().__init__(timeout=3600*24)
        self.user = user
        self.channel = channel
        self.task_name = task_name
        self.completed = False

    async def start(self):
        self.bot = self._get_bot()
        self.bot.add_listener(self.on_message, "on_message")
        self.bot.add_listener(self.on_reaction_add, "on_reaction_add")
        self.bot.add_listener(self.on_voice_state_update, "on_voice_state_update")
        self.bot.add_listener(self.on_interaction, "on_interaction")

        await asyncio.sleep(60 * 30)
        if not self.completed:
            await self.cancel()

    def _get_bot(self):
        return bot

    def get_task_type(self):
        if self.task_name in DAILY_TASKS:
            return "daily"
        elif self.task_name in WEEKLY_TASKS:
            return "weekly"
        elif self.task_name in MONTHLY_TASKS:
            return "monthly"
        return None

    async def on_message(self, message: discord.Message):
        if self.completed or message.author.id != self.user.id:
            return

        weekday = datetime.now().weekday()
        utc_plus_2 = timezone(timedelta(hours=2))
        now = datetime.now(utc_plus_2).time()

        if self.task_name == "Lähetä viesti tiettyyn aikaan":
            if dtime(10, 0) <= now <= dtime(17, 0) and message.channel.id == TASK_CHANNEL_ID:
                await self.finish_task()

        elif self.task_name == "Käy yleinen kanavalla lähettämässä viesti":
            if message.channel.id == TASK_CHANNEL_ID and (
                message.content or message.attachments or message.embeds or message.stickers
            ):
                await self.finish_task()

        elif self.task_name == "Mainitse toinen käyttäjä":
            if message.mentions and message.channel.id == TASK_CHANNEL_ID:
                await self.finish_task()

        elif self.task_name in ["Lähetä kuva tai liite", "Lähetä tiedosto"]:
            if (message.attachments or message.embeds) and message.channel.id == TASK_CHANNEL_ID:
                await self.finish_task()

        elif self.task_name == "Lähetä meemi":
            if (message.attachments or message.embeds) and message.channel.id == MEME_CHANNEL_ID:
                await self.finish_task()

        elif self.task_name == "Lähetä viesti viikonloppuna":
            if message.channel.id == TASK_CHANNEL_ID and weekday in [5, 6]:
                await self.finish_task()

        elif self.task_name == "Lähetä viesti arkipäivänä":
            if message.channel.id == TASK_CHANNEL_ID and weekday in range(0, 5):
                await self.finish_task()

        elif self.task_name == "Tee kysely":
            if message.channel.id == TASK_CHANNEL_ID and len(message.reactions) >= 2:
                await self.finish_task()

        elif self.task_name == "Aloita keskustelu":
            def check_response(m):
                return m.reference and m.reference.message_id == message.id and m.author.id != self.user.id
            try:
                response = await self.bot.wait_for("message", timeout=300, check=check_response)
                if response:
                    await self.finish_task()
            except asyncio.TimeoutError:
                pass

        elif self.task_name == "Kerää reaktioita":
            def check_reaction(reaction, user):
                return reaction.message.id == message.id and user.id != self.user.id
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=300, check=check_reaction)
                if reaction:
                    await self.finish_task()
            except asyncio.TimeoutError:
                pass
        
        elif self.task_name == "Lisää tarra viestiin":
            if message.channel.id == TASK_CHANNEL_ID and message.stickers:
                await self.finish_task()

        elif self.task_name == "Lähetä viesti, jossa on kysymys":
            if message.channel.id == TASK_CHANNEL_ID and "?" in message.content:
                await self.finish_task()

        elif self.task_name == "Kerro viikonpäivä":
            weekdays = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]
            if message.channel.id == TASK_CHANNEL_ID and any(day in message.content.lower() for day in weekdays):
                await self.finish_task()

        elif self.task_name == "Kysy jotain toiselta käyttäjältä":
            if (
                message.channel.id == TASK_CHANNEL_ID
                and "?" in message.content
                and message.mentions
                and message.author.id == self.user.id
            ):
                await self.finish_task()

        elif self.task_name == "Jaa kuva, josta syntyy vitsi tai reaktio":
            if message.channel.id == TASK_CHANNEL_ID and (message.attachments or message.embeds):
                def response_or_reaction_check(event):
                    if isinstance(event, discord.Message):
                        return (
                            event.reference
                            and event.reference.message_id == message.id
                            and event.author.id != self.user.id
                        )
                    elif isinstance(event, tuple) and len(event) == 2:
                        reaction, user = event
                        return (
                            reaction.message.id == message.id
                            and user.id != self.user.id
                        )
                    return False

                try:
                    done, pending = await asyncio.wait(
                        [
                            self.bot.wait_for("message", check=response_or_reaction_check),
                            self.bot.wait_for("reaction_add", check=response_or_reaction_check)
                        ],
                        timeout=1800,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

                    if done:
                        await self.finish_task()
                except asyncio.TimeoutError:
                    pass

        elif self.task_name == "Mainitse kanava viestissä":
            if message.channel.id == TASK_CHANNEL_ID and message.channel_mentions:
                await self.finish_task()

        elif self.task_name == "Lähetä viesti, jossa on yli 10 sanaa":
            if message.channel.id == TASK_CHANNEL_ID and len(message.content.split()) > 10:
                await self.finish_task()

        elif self.task_name == "Lähetä Tenor-linkki":
            if message.channel.id == TASK_CHANNEL_ID and "tenor.com/view" in message.content.lower():
                await self.finish_task()

        elif self.task_name == "Lähetä Giphy-linkki":
            if message.channel.id == TASK_CHANNEL_ID and "giphy.com/gifs" in message.content.lower():
                await self.finish_task()

        elif self.task_name == "Lähetä viesti, jossa on linkki":
            if message.channel.id == TASK_CHANNEL_ID and ("http://" in message.content or "https://" in message.content):
                await self.finish_task()

        elif self.task_name == "Vastaa toisen käyttäjän viestiin":
            if message.channel.id == TASK_CHANNEL_ID and message.reference and message.author.id == self.user.id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    if ref_msg.author.id != self.user.id:
                        await self.finish_task()
                except:
                    pass

    async def on_interaction(self, interaction: discord.Interaction):
        if self.completed or interaction.user.id != self.user.id:
            return

        if self.task_name == "Käytä bottikomentoja" and interaction.channel.id == TASK_CHANNEL_ID:
            await self.finish_task()

        elif self.task_name == "Osta jotain kaupasta":
            if (
                interaction.command
                and interaction.command.name == "kauppa"
                and interaction.namespace.tuote
                and interaction.channel.id == TASK_CHANNEL_ID    
            ):
                await self.finish_task()

    async def on_voice_state_update(self, member, before, after):
        if self.completed or member.id != self.user.id:
            return

        voice_channel_id = VOICE_EVENT_CHANNEL_ID

        if self.task_name == "Osallistu puhekanavaan" and after.channel and after.channel.id == voice_channel_id:
            await self.finish_task()

        elif self.task_name == "Striimaa peliäsi" and after.channel and after.self_stream:
            await self.finish_task()

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if self.completed or user.id != self.user.id:
            return

        if reaction.message.channel.id != TASK_CHANNEL_ID:
            return

        if self.task_name in ["Äänestä reaktioilla", "Reagoi viestiin emojilla"]:
            await self.finish_task()
        
        elif self.task_name == "Lisää reaktio toisen viestiin, jota ei ole vielä reagoitu":
            if (
                reaction.message.channel.id == TASK_CHANNEL_ID
                and user.id == self.user.id
                and len(reaction.message.reactions) == 1  
            ):
                await self.finish_task()

    async def finish_task(self):
        if self.completed:
            return
        self.completed = True

        try:
            self.bot.remove_listener(self.on_message, "on_message")
            self.bot.remove_listener(self.on_reaction_add, "on_reaction_add")
            self.bot.remove_listener(self.on_voice_state_update, "on_voice_state_update")
            self.bot.remove_listener(self.on_interaction, "on_interaction")
        except Exception as e:
            print(f"[ERROR] Listenerien poisto epäonnistui: {e}")

        await self.complete_task()

        uid = str(self.user.id)
        if active_listeners.get(uid) == self:
            active_listeners.pop(uid, None)
            print(f"[INFO] Poistettiin käyttäjä {uid} aktiivisista tehtävistä.")

    async def complete_task(self):
        await complete_task(self.user, self.task_name, self.user.guild)

    async def cancel(self, show_timeout_message=True):
        self.completed = True
        try:
            self.bot.remove_listener(self.on_message, "on_message")
            self.bot.remove_listener(self.on_reaction_add, "on_reaction_add")
            self.bot.remove_listener(self.on_voice_state_update, "on_voice_state_update")
            self.bot.remove_listener(self.on_interaction, "on_interaction")
        except Exception as e:
            print(f"[ERROR] Listenerien poisto epäonnistui (cancel): {e}")

        if show_timeout_message:
            await self.channel.send(f"{self.user.mention}, tehtävän **{self.task_name}** aikaraja (30min) ylittyi. ⏱️")

        uid = str(self.user.id)
        if active_listeners.get(uid) == self:
            active_listeners.pop(uid, None)
            
load_dotenv()
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

async def send_timeout_alert(bot, user, task_name, duration="30min"):
    channel = bot.get_channel(ALERT_CHANNEL_ID)
    if channel:
        await channel.send(f"{user.mention}, tehtävän **{task_name}** aikaraja ({duration}) ylittyi. ⏱️")

async def complete_task(user: discord.Member, task_name: str, guild: discord.Guild):
    uid = str(user.id)
    user_tasks = await load_user_tasks()
    user_task_list = user_tasks.get(uid, [])

    if onko_tehtava_suoritettu_ajankohtaisesti(task_name, user_task_list):
        print(f"[INFO] Käyttäjä {user} on jo suorittanut tehtävän '{task_name}'.")
        channel = bot.get_channel(TASK_CHANNEL_ID)
        if channel:
            if task_name in DAILY_TASKS:
                await channel.send(f"{user.mention}, olet jo suorittanut päivittäisen tehtävän **{task_name}** tänään. Yritä uudelleen huomenna! ⏳")
            elif task_name in WEEKLY_TASKS:
                await channel.send(f"{user.mention}, olet jo suorittanut viikkotehtävän **{task_name}** tällä viikolla. Yritä uudelleen ensi viikolla! 📅")
            elif task_name in MONTHLY_TASKS:
                await channel.send(f"{user.mention}, olet jo suorittanut kuukausittaisen tehtävän **{task_name}** tässä kuussa. Yritä uudelleen ensi kuussa! 🗓️")
            else:
                await channel.send(f"{user.mention}, olet jo suorittanut tehtävän **{task_name}**. ✅")
        return

    await save_user_task(uid, task_name)

    if task_name in DAILY_TASKS:
        task_type = "daily"
        xp_amount = 50
    elif task_name in WEEKLY_TASKS:
        task_type = "weekly"
        xp_amount = 100
    elif task_name in MONTHLY_TASKS:
        task_type = "monthly"
        xp_amount = 150
    else:
        task_type = None
        xp_amount = 0

    was_reset = False
    if task_type:
        try:
            was_reset = await update_streak(user, task_type)
        except Exception as e:
            print(f"[ERROR] Streakin päivitys epäonnistui: {e}")

    streaks = load_streaks()
    user_streak_data = streaks.get(uid, {}).get(task_type, {})
    current_streak = user_streak_data.get("streak", 0)
    max_streak = user_streak_data.get("max_streak", 0)

    task_labels = {
        "daily": "päivittäisen",
        "weekly": "viikoittaisen",
        "monthly": "kuukausittaisen"
    }
    task_label = task_labels.get(task_type, "tuntemattoman")

    channel = bot.get_channel(TASK_CHANNEL_ID)
    if channel:
        try:
            if was_reset:
                await channel.send(
                    f"{user.mention} aloitti uuden {task_label} tehtäväputken tehtävällä **{task_name}**! \n"
                    f"+{xp_amount} XP myönnetty ja streak alkoi lukemasta **1**! 🚀"
                )
            else:
                await channel.send(
                    f"{user.mention} suoritti {task_label} tehtävän **{task_name}** ja sai +{xp_amount} XP! ✅\n"
                    f"Streak nousi lukemaan **{current_streak}** ({task_label} tehtävissä). Pisin streak: **{max_streak}** 🔥"
                )
        except Exception as e:
            print(f"[ERROR] Viestin lähetys epäonnistui: {e}")

    log_channel = bot.get_channel(TASK_LOG_CHANNEL_ID)
    if log_channel:
        try:
            await log_channel.send(
                f"📝 {user.mention} suoritti tehtävän: **{task_name}**\n"
                f"XP: +{xp_amount} | Streak: {current_streak}/{max_streak} ({task_label}) ✅"
            )
        except Exception as e:
            print(f"[ERROR] Lokiviestin lähetys epäonnistui: {e}")

    if xp_amount > 0:
        try:
            await add_xp(bot, user, xp_amount)
        except Exception as e:
            print(f"[ERROR] XP:n lisäys epäonnistui: {e}")

    if active_listeners.get(uid):
        active_listeners.pop(uid, None)
        print(f"[INFO] Poistettiin käyttäjä {uid} aktiivisista tehtävistä (complete_task).")
                 
TASK_INSTRUCTIONS = {
    "Lähetä viesti tiettyyn aikaan": "Lähetä viesti <#1339846062281588777> kanavalle klo 10–17 UTC+2 välisenä aikana. Aikaa suoritukseen 30 min.",
    "Käy yleinen kanavalla lähettämässä viesti": "Lähetä viesti <#1339846062281588777> kanavassa. Viestisi voi olla tekstiä, tiedosto, gif ja/tai tarra. Aikaa suoritukseen 30 min.",
    "Mainitse toinen käyttäjä": "Mainitse joku käyttäjä viestissäsi <#1339846062281588777> kanavalla. Aikaa suoritukseen 30 min.",
    "Käytä bottikomentoja": "Käytä mitä tahansa bottikomentoa <#1339846062281588777> kanavalla. Aikaa suoritukseen 30 min.",
    "Lähetä kuva tai liite": "Lähetä kuva tai tiedostoliite <#1339846062281588777> kanavalle. Aikaa suoritukseen 30 min.",
    "Äänestä reaktioilla": "Lisää reaktio johonkin viestiin <#1339846062281588777> kanavalla. Aikaa suoritukseen 30 min.",
    "Osallistu puhekanavaan": "Liity <#1339856090036174908> puhekanavalle. Aikaa suoritukseen 30 min.",
    "Lähetä viesti viikonloppuna": "Viesti tehtävää varten vain viikonloppuna <#1339846062281588777> kanavalle. `Lauantai tai sunnuntai`. Aikaa suoritukseen 30 min.",
    "Reagoi viestiin emojilla": "Reagoi omaan tämän päiväiseen viestiin emojilla <#1339846062281588777> kanavalla. Kirjoita uusi viesti, jos ei ole valmiina. Aikaa suoritukseen 30 min.",
    "Lähetä tiedosto": "Lähetä mikä tahansa tiedosto tai kuva <#1339846062281588777> kanavalle. Aikaa suoritukseen 30 min.",
    "Lähetä meemi": "Lähetä hauska meemi <#1339856017277714474> kanavalle. Aikaa suoritukseen 30 min.",
    "Striimaa peliäsi": "Aloita pelistriimi <#1339856090036174908> kanavalla. Aikaa suoritukseen 30 min.",
    "Tee kysely": "Luo viesti, johon lisäät vähintään kaksi reaktiota <#1339846062281588777> kanavalla. Aikaa suoritukseen 30 min.",
    "Osta jotain kaupasta": "Käytä komentoa `/kauppa [tuotteen nimi]` ostaaksesi tuotteen <#1339846062281588777> kanavalla. Aikaa suoritukseen 30 min.",
    "Lähetä viesti arkipäivänä": "Lähetä viesti <#1339846062281588777> kanavalle maanantaista perjantaihin. Aikaa suoritukseen 30 min.",
    "Aloita keskustelu": "Lähetä viesti <#1339846062281588777> kanavalle ja saa joku vastaamaan siihen vastauksena (reply). Aikaa suoritukseen 30 min.",
    "Kerää reaktioita": "Lähetä viesti <#1339846062281588777> kanavalle ja saa joku muu reagoimaan siihen emojilla. Aikaa suoritukseen 30 min.",
    "Lisää tarra viestiin": "Lähetä viesti <#1339846062281588777> kanavalle ja liitä siihen tarra. Aikaa suoritukseen 30 min.",
    "Kerro viikonpäivä": "Lähetä viesti <#1339846062281588777> kanavalle, joka sisältää viikonpäivän nimen (esim. 'maanantai'). Aikaa suoritukseen 30 min.",
    "Lähetä viesti, jossa on kysymys": "Lähetä kysymys sisältävä viesti <#1339846062281588777> kanavalle. Aikaa suoritukseen 30 min.",
    "Lähetä emoji": "Lähetä viesti, jossa on vähintään yksi emoji <#1339846062281588777> kanavalle. Aikaa suoritukseen 30 min.",
    "Kysy jotain toiselta käyttäjältä": "Lähetä kysymys toiselle käyttäjälle <#1339846062281588777> kanavalla. Mainitse käyttäjä ja käytä kysymysmerkkiä viestissä. Aikaa suoritukseen 30 min.",
    "Lisää reaktio toisen viestiin, jota ei ole vielä reagoitu": "Lisää emoji-reaktio viestiin <#1339846062281588777> kanavalla, jossa ei ollut vielä reaktioita. Aikaa suoritukseen 30 min.",
    "Jaa kuva, josta syntyy vitsi tai reaktio": "Lähetä kuva <#1339846062281588777> kanavalle, johon joku muu vastaa viestillä tai reagoi emojilla. Aikaa suoritukseen 30 min.",
    "Mainitse kanava viestissä": "Lähetä viesti <#1339846062281588777> kanavalle, jossa mainitset toisen kanavan (esim. #yleinen). Aikaa suoritukseen 30 min.",
    "Lähetä viesti, jossa on yli 10 sanaa": "Lähetä viesti <#1339846062281588777> kanavalle, jossa on yli 10 sanaa. Aikaa suoritukseen 30 min.",
    "Lähetä viesti, jossa on GIF": "Lähetä GIF-kuva <#1339846062281588777> kanavalle. Aikaa suoritukseen 30 min.",
    "Lähetä viesti, jossa on linkki": "Lähetä viesti <#1339846062281588777> kanavalle, joka sisältää linkin (http/https). Aikaa suoritukseen 30 min.",
    "Vastaa toisen käyttäjän viestiin": "Vastaa toisen käyttäjän viestiin <#1339846062281588777> kanavalla käyttämällä vastaustoimintoa. Aikaa suoritukseen 30 min.",
    "Lähetä Tenor-linkki": "Lähetä viesti <#1339846062281588777> kanavalle, joka sisältää Tenor-palvelun GIF-linkin (esim. tenor.com/view/...). Aikaa suoritukseen 30 min.",
    "Lähetä Giphy-linkki": "Lähetä viesti <#1339846062281588777> kanavalle, joka sisältää Giphy-palvelun GIF-linkin (esim. giphy.com/gifs/...). Aikaa suoritukseen 30 min.",
}

class TaskControlView(discord.ui.View):
    def __init__(self, user, task_name):
        super().__init__(timeout=1800)
        self.user = user
        self.task_name = task_name

    @discord.ui.button(label="❌ Peru tehtävä", style=discord.ButtonStyle.danger)
    async def cancel_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Et voi perua toisen käyttäjän tehtävää!", ephemeral=True)
            return

        uid = str(self.user.id)
        listener = active_listeners.get(uid)

        if listener:
            await listener.cancel(show_timeout_message=False)  
            active_listeners.pop(uid, None)

        await interaction.response.send_message(f"Tehtävä **{self.task_name}** on peruttu onnistuneesti. ✅", ephemeral=True)

    @discord.ui.button(label="⛔ Ilmoita virheellinen tehtävä", style=discord.ButtonStyle.secondary)
    async def report_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        alert_channel = bot.get_channel(TASK_LOG_CHANNEL_ID)
        if alert_channel:
            await alert_channel.send(f"⛔ {self.user.mention} ilmoitti virheellisestä tehtävästä: **{self.task_name}**")
        await interaction.response.send_message("Ilmoitus lähetetty ylläpidolle onnistuneesti. ✅", ephemeral=True)

class StartTaskView(discord.ui.View):
    def __init__(self, user, task_name, task_type):
        super().__init__(timeout=300)
        self.user = user
        self.task_name = task_name
        self.task_type = task_type

    @discord.ui.button(label="✅ Aloita tehtävä", style=discord.ButtonStyle.success)
    async def start_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Et voi aloittaa toisen käyttäjän tehtävää!", ephemeral=True)
            return

        uid = str(self.user.id)
        if uid in active_listeners:
            await interaction.response.send_message(
                "Sinulla on jo aktiivinen tehtävä käynnissä. Suorita tai peru se ennen uuden aloittamista.",
                ephemeral=True
            )
            return

        user_tasks = await load_user_tasks()
        user_task_list = user_tasks.get(uid, [])

        if onko_tehtava_liian_aikaisin(self.task_name, user_task_list, minuutteja=2):
            await interaction.response.send_message(
                f"⏳ Tehtävän **{self.task_name}** voi aloittaa uudelleen vasta hetken päästä. Odota vähintään 1–2 minuuttia edellisestä suorituksesta.",
                ephemeral=True
            )
            return

        listener = TaskListener(self.user, interaction.channel, self.task_name)

        async def wrapped_start():
            active_listeners[uid] = listener 
            await asyncio.sleep(1)
            await listener.start()

        asyncio.create_task(wrapped_start())

        view = TaskControlView(self.user, self.task_name)

        await interaction.response.send_message(
            f"**{self.task_type} tehtävä aloitettu:** {self.task_name}\n\n"
            "Sinulla on 30 minuuttia aikaa suorittaa tehtävä.\n"
            "Voit peruuttaa tehtävän tai ilmoittaa virheestä käyttämällä alla olevia painikkeita.",
            view=view,
            ephemeral=True
        )