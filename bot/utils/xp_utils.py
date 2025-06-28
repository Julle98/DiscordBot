import discord
import os
import json
import asyncio
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

STREAKS_FILE = Path("data/tasks/streaks.json")

viestihistoria = defaultdict(list)
dm_viestit = defaultdict(list)
dm_estot = {}

def parse_xp_content(content):
    try:
        _, xp, level = content.split(":")
        return int(xp), int(level)
    except:
        return 0, 0

def make_xp_content(user_id, xp, level):
    return f"{user_id}:{xp}:{level}"

def calculate_level(xp):
    level = 0
    while xp >= (level + 1) ** 2 * 100:
        level += 1
    return level

async def get_user_xp_message(channel: discord.TextChannel, user_id: int):
    async for message in channel.history(limit=1000):
        if message.author.bot and message.content.startswith(f"{user_id}:"):
            return message
    return None

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

async def tarkista_salaisuus(message, viesti):
    salaisuudet = {
        "hei": "Moi!",
        "moi": "Heippa!",
        "mitä kuuluu": "Hyvin, kiitos!",
        "mikä on nimesi": "Olen Sannamaija, mukava tavata!",
        "kiitos": "Eipä kestä!",
        "hiljaa": "Oleppas ite hiljaa.",
    }
    for avain, vastaus in salaisuudet.items():
        if avain in viesti:
            await message.channel.send(vastaus)
            return True
    return False

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

    if uid not in streaks:
        streaks[uid] = {"pvm": nyt.isoformat(), "streak": 1}
    else:
        viime = datetime.fromisoformat(streaks[uid]["pvm"]).date()
        ero = (nyt - viime).days
        if ero == 1:
            streaks[uid]["streak"] += 1
        elif ero > 1:
            streaks[uid]["streak"] = 1
        streaks[uid]["pvm"] = nyt.isoformat()

    save_streaks(streaks)

async def tarkista_tasonousu(bot, message, old_level, new_level):
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

async def käsittele_viesti_xp(bot, message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        await käsittele_dm_viesti(bot, message)
        return

    nyt = datetime.now(timezone.utc)
    uid = message.author.id
    viesti = message.content.lower()

    viestihistoria[uid].append(nyt)
    viestihistoria[uid] = [t for t in viestihistoria[uid] if nyt - t < timedelta(seconds=3)]

    if len(viestihistoria[uid]) > 2:
        try:
            await message.author.timeout(timedelta(minutes=15), reason="Spam yritys")
            await message.author.send("Sinut asetettiin 15 minuutin jäähylle: **Spam yritys**.")
        except:
            pass

        try:
            async for msg in message.channel.history(limit=10):
                if msg.author == message.author and (nyt - msg.created_at.replace(tzinfo=timezone.utc)) < timedelta(seconds=3):
                    await msg.delete()
        except:
            pass

        modlog = bot.get_channel(MODLOG_CHANNEL_ID)
        if modlog:
            await modlog.send(
                f"🔇 **Jäähy asetettu (automaattinen)**\n"
                f"👤 Käyttäjä: {message.author.mention}\n"
                f"⏱ Kesto: 15 minuuttia\n"
                f"📝 Syy: Spam yritys\n"
                f"👮 Asetti: Sannamaija"
            )

        viestihistoria[uid].clear()
        return

    if XP_CHANNEL_ID == 0:
        return

    xp_channel = message.guild.get_channel(XP_CHANNEL_ID)
    if not xp_channel:
        return

    msg = await get_user_xp_message(xp_channel, uid)
    xp, level = parse_xp_content(msg.content if msg else f"{uid}:0:0")

    xp_gain = 10
    if any(role.id in DOUBLE_XP_ROLES for role in message.author.roles):
        xp_gain *= 2

    xp += xp_gain
    new_level = calculate_level(xp)

    if new_level > level:
        await tarkista_tasonousu(bot, message, level, new_level)

    content = make_xp_content(uid, xp, new_level)
    if msg:
        await msg.edit(content=content)
    else:
        await xp_channel.send(content)

    await paivita_streak(uid)

    vastattu = False
    viesti = message.content.lower()

    if message.reference:
        try:
            alkuperäinen = await message.channel.fetch_message(message.reference.message_id)
            if alkuperäinen.author == bot.user:
                vastattu = await tarkista_salaisuus(message, viesti)
        except:
            pass

    if not vastattu:
        await tarkista_salaisuus(message, viesti)

    await bot.process_commands(message)