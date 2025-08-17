import discord
import os
import json
import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))
SLOWMODE_CHANNEL_ID = int(os.getenv("SLOWMODE_CHANNEL_ID", 0))
IGNORED_VOICE_CHANNEL_ID = int(os.getenv("IGNORED_VOICE_CHANNEL_ID", 0))

LEVEL_ROLES = {
    1: 1370704701250601030,
    5: 1370704731567161385,
    10: 1370704765809332254,
    15: 1370704818875928628,
    25: 1370704865138839564,
    50: 1370704889398825041,
}

LEVEL_MESSAGES = {
    1: "{user} saavutti ensimmäisen tason ja ansaitsi upouuden roolin! 🎉",
    5: "{user} on nyt tasolla 5! Hyvää työtä! 🚀 ",
    10: "{user} etenee kovaa vauhtia! Taso 10 saavutettu! 🔥 ",
    15: "{user} on nyt tasolla 15 - vaikutusvalta kasvaa! 🌟 ",
    25: "{user} saavutti tason 25! Melkein huipulla! 🏆 ",
    50: "{user} on nyt tasolla 50! Uskomaton saavutus! 👑 ",
}

DOUBLE_XP_ROLES = {
    1339853855315197972,
    1368228763770294375,
    1339846508199022613,
    1339846579766694011,
    1370704889398825041,
    1376205558675148800,
    1383739974767349790,
}

XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
XP_FILE = XP_JSON_PATH / "users_xp.json"

viestihistoria = defaultdict(list)
dm_viestit = defaultdict(list)
dm_estot = {}

def parse_xp_content(content):
    try:
        _, xp, level = content.split(":")
        return int(xp), int(level)
    except:
        return 0, 0

def load_xp_data():
    if XP_FILE.exists() and XP_FILE.is_file():
        with open(XP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_xp_data(data):
    XP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(XP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def make_xp_content(user_id, xp, _level=None):
    data = load_xp_data()
    user_info = data.get(str(user_id), {"xp": 0, "level": 0})
    user_info["xp"] += xp
    user_info["level"] = calculate_level(user_info["xp"]) if _level is None else _level
    data[str(user_id)] = user_info
    save_xp_data(data)
    return f"{user_id}:{user_info['xp']}:{user_info['level']}"

def calculate_level(xp):
    level = 0
    while xp >= (level + 1) ** 2 * 100:
        level += 1
    return level

async def get_user_xp_message(channel, user_id: int):
    xp_data = load_xp_data()
    user_info = xp_data.get(str(user_id), {"xp": 0, "level": 0})
    return type("DummyXPMessage", (), {
        "content": f"{user_id}:{user_info['xp']}:{user_info['level']}"
    })()

async def käsittele_dm_viesti(bot, message):
    uid = message.author.id
    nyt = datetime.now(timezone.utc)

    if uid in dm_estot and nyt < dm_estot[uid]:
        return

    dm_viestit[uid].append(nyt)
    dm_viestit[uid] = [t for t in dm_viestit[uid] if nyt - t < timedelta(minutes=1)]

    if len(dm_viestit[uid]) > 2:
        dm_estot[uid] = nyt + timedelta(minutes=5)
        try:
            await message.channel.send("Lähetit liikaa viestejä. DM estetty 5 minuutiksi.")
        except:
            pass
        return

    try:
        await message.channel.send("Botti toimii vain palvelimilla – kokeile siellä! 🙂")
    except:
        pass

XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
STREAKS_FILE = XP_JSON_PATH / "users_streak.json"

def load_streaks():
    if STREAKS_FILE.exists():
        with open(STREAKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_streaks(data):
    STREAKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STREAKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def paivita_streak(user_id: int):
    streaks = load_streaks()
    uid = str(user_id)
    nyt = datetime.now().date()

    if uid not in streaks or "pvm" not in streaks[uid]:
        streaks[uid] = {
            "pvm": nyt.isoformat(),
            "streak": 1,
            "pisin": 1  
        }
    else:
        viime = datetime.fromisoformat(streaks[uid]["pvm"]).date()
        ero = (nyt - viime).days
        if ero == 1:
            streaks[uid]["streak"] += 1
        elif ero > 1:
            streaks[uid]["streak"] = 1
        streaks[uid]["pvm"] = nyt.isoformat()

        nykyinen = streaks[uid]["streak"]
        pisin = streaks[uid].get("pisin", nykyinen)
        if nykyinen > pisin:
            streaks[uid]["pisin"] = nykyinen

    save_streaks(streaks)

viestitetyt_tasonousut = {}

async def tarkista_tasonousu(bot, message, old_level, new_level):
    uid = message.author.id

    if viestitetyt_tasonousut.get(uid) == new_level:
        return  

    if new_level > old_level:
        if new_level in LEVEL_MESSAGES:
            await message.channel.send(LEVEL_MESSAGES[new_level].format(user=message.author.mention))
        else:
            await message.channel.send(f"{message.author.mention} nousi tasolle {new_level}! 🎉")

        guild = message.guild
        for lvl, role_id in LEVEL_ROLES.items():
            role = guild.get_role(role_id)
            if role and role in message.author.roles and lvl > new_level:
                await message.author.remove_roles(role)

        if new_level in LEVEL_ROLES:
            uusi_rooli = guild.get_role(LEVEL_ROLES[new_level])
            if uusi_rooli:
                await message.author.add_roles(uusi_rooli)

        viestitetyt_tasonousut[uid] = new_level

async def tarkkaile_kanavan_aktiivisuutta():
    await asyncio.sleep(5)
    from utils.bot_setup import bot
    await bot.wait_until_ready()

    kanava = bot.get_channel(SLOWMODE_CHANNEL_ID)
    if not kanava:
        print("Hidastuskanavaa ei löytynyt.")
        return

    while not bot.is_closed():
        nyt = datetime.now(timezone.utc)
        aktiiviset = 0

        try:
            async for msg in kanava.history(limit=100, after=nyt - timedelta(seconds=30)):
                if not msg.author.bot:
                    aktiiviset += 1
        except:
            await asyncio.sleep(30)
            continue

        try:
            if aktiiviset >= 15 and kanava.slowmode_delay == 0:
                await kanava.edit(slowmode_delay=5)
            elif aktiiviset < 3 and kanava.slowmode_delay > 0:
                await kanava.edit(slowmode_delay=0)
        except:
            pass

        await asyncio.sleep(30)

async def anna_xp_komennosta(bot, interaction: discord.Interaction, xp_määrä: int = 10):
    uid = str(interaction.user.id)
    xp_data = load_xp_data()
    user_info = xp_data.get(uid, {"xp": 0, "level": 0})

    if any(role.id in DOUBLE_XP_ROLES for role in interaction.user.roles):
        xp_määrä *= 2

    user_info["xp"] += xp_määrä
    new_level = calculate_level(user_info["xp"])

    if new_level > user_info["level"]:
        dummy_message = type("DummyMessage", (), {
            "author": interaction.user,
            "channel": interaction.channel,
            "guild": interaction.guild
        })()
        await tarkista_tasonousu(bot, dummy_message, user_info["level"], new_level)

    user_info["level"] = new_level
    xp_data[uid] = user_info
    save_xp_data(xp_data)

    await paivita_streak(int(uid))

spam_counts = defaultdict(lambda: {"count": 0, "timestamp": time.time()})
SPAM_THRESHOLD = 2
SPAM_WINDOW = 3
SPAM_TIMEOUT = 15  

async def käsittele_viesti_xp(bot, message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        await käsittele_dm_viesti(bot, message)
        return

    uid = str(message.author.id)
    now = time.time()

    if uid in spam_counts:
        spam_counts[uid]["count"] += 1
        spam_counts[uid]["timestamp"] = now
    else:
        spam_counts[uid] = {"count": 1, "timestamp": now}

    if spam_counts[uid]["count"] > SPAM_THRESHOLD:
        try:
            await message.author.timeout(timedelta(minutes=SPAM_TIMEOUT), reason="Spam yritys")
            await message.author.send(f"Sinut asetettiin {SPAM_TIMEOUT} minuutin jäähylle: **Spam yritys**.")
        except:
            pass

        try:
            async for msg in message.channel.history(limit=50):
                if msg.author == message.author:
                    await msg.delete()
        except:
            pass

        modlog = bot.get_channel(MODLOG_CHANNEL_ID)
        if modlog:
            await modlog.send(
                f"🔇 **Jäähy asetettu (automaattinen)**\n"
                f"👤 Käyttäjä: {message.author.mention}\n"
                f"⏱ Kesto: {SPAM_TIMEOUT} minuuttia\n"
                f"📝 Syy: Spam yritys\n"
                f"👮 Asetti: Sannamaija"
            )

        spam_counts.pop(uid)
        return

    xp_data = load_xp_data()
    user_info = xp_data.get(uid, {"xp": 0, "level": 0})

    xp_gain = 10
    if any(role.id in DOUBLE_XP_ROLES for role in message.author.roles):
        xp_gain *= 2

    user_info["xp"] += xp_gain
    new_level = calculate_level(user_info["xp"])

    if new_level > user_info["level"]:
        await tarkista_tasonousu(bot, message, user_info["level"], new_level)

    user_info["level"] = new_level
    xp_data[uid] = user_info
    save_xp_data(xp_data)

    await paivita_streak(int(uid))