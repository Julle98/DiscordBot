import os, asyncio, logging, discord
from discord.ext import commands
from dotenv import load_dotenv
import random

from collections import deque
intents = discord.Intents.all()  
from bot.utils.env_loader import load_env_and_validate
from bot.utils.moderation_tasks import start_moderation_loops
from bot.utils.store_utils import start_store_loops
from bot.utils.tasks_utils import start_tasks_loops
from bot.cogs.levels import tarkista_puhekanavat
from bot.utils.antinuke import check_deletions

load_env_and_validate()
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0))   

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_queue = deque()
        self.current_status = "Online"
        self.command_attempts = {}

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.tree.sync()

bot = MyBot(command_prefix="/", intents=intents)

COGS = [
    "bot.cogs.utils",
    "bot.cogs.tasks",
    "bot.cogs.stats",
    "bot.cogs.levels",
    "bot.cogs.store",
    "bot.cogs.moderation",
    "bot.cogs.misc",
    "bot.cogs.ai",            
]

async def load_cogs() -> None:
    print("🔄 Ladataan cogeja…")
    for name in COGS:
        try:
            await bot.load_extension(name)
            print(f"  ✅ {name}")
        except Exception as exc:
            print(f"  ❌ {name}: {exc}")
            logging.exception(f"Virhe ladattaessa {name}")

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context, global_sync: bool = False):
    """Synkronoi slash‑komennot. Käytä `/sync true` julkaistaksesi globaalisti."""
    await ctx.defer()
    try:
        if global_sync or TEST_GUILD_ID == 0:
            cmds = await bot.tree.sync()
        else:
            cmds = await bot.tree.sync(guild=discord.Object(TEST_GUILD_ID))
        await ctx.send(f"Synkronoitiin {len(cmds)} komentoa.")
    except Exception as exc:
        await ctx.send(f"Synkronointi epäonnistui: {exc}")

# Statuslistat
listening_statuses = [
    "Ongelmianne | /komennot",
    "Komentojanne | /komennot",
    "Tehtäviänne | /komennot",
    "Ostoksianne | /komennot"
]

watching_statuses = [
    "Wilma | /komennot",  
    "Keskustelujanne | /komennot",
    "Schauplatz | /komennot",
    "Suorituksia | /komennot"
]

playing_statuses = [
    "Abitti 2 | /komennot",  
    "Tiedoillasi | /komennot",
    "Komennoilla | /komennot",
    "Matikkaeditori | /komennot"
]

last_status = None  

@bot.event
async def update_status():
    global last_status
    while True:
        category = random.choice(["kuuntelee", "katsoo", "pelaa"])

        if category == "kuuntelee":
            status = random.choice(listening_statuses)
            activity = discord.Activity(type=discord.ActivityType.listening, name=status)
        elif category == "katsoo":
            status = random.choice(watching_statuses)
            activity = discord.Activity(type=discord.ActivityType.watching, name=status)
        else:
            status = random.choice(playing_statuses)
            activity = discord.Game(name=status)

        full_status = f"{category} {status}"
        if full_status == last_status:
            continue  

        await bot.change_presence(activity=activity)
        last_status = full_status
        print(f"Status vaihdettu: {full_status}")

        await asyncio.sleep(21600)

@bot.event
async def on_ready():
    print(f"{bot.user} käynnissä")

    for cog_name, cog_obj in bot.cogs.items():
        print(f"✅ Cog valmiina: {cog_name}")

    try:
        bot_status_kanava = discord.utils.get(bot.get_all_channels(), name="🛜bot-status")
        if bot_status_kanava:
            print("Poistetaan vanhoja botin tilaviestiä...")
            async for message in bot_status_kanava.history(limit=100):
                await message.delete()
            from bot.utils.time_utils import get_current_time_in_stockholm
            current_time = get_current_time_in_stockholm()
            await bot_status_kanava.send(f"Botti on nyt toiminnassa, käynnistetty: {current_time}")
            print("Botin tilaviesti lähetetty.")
        else:
            print("🛜bot-status kanavaa ei löytynyt, tilaviestiä ei lähetetty.")
    except Exception as e:
        print(f"Virhe botin tilaviestin lähetyksessä: {e}")

    check_deletions.start()
    tarkista_puhekanavat.start()
    start_moderation_loops()
    start_store_loops()
    start_tasks_loops()

    try:
        if TEST_GUILD_ID:
            synced = await bot.tree.sync(guild=discord.Object(TEST_GUILD_ID))
        else:
            synced = await bot.tree.sync()
        print("Slash komennot synkronoitu. Synkronoidut komennot:", len(synced))
    except Exception as exc:
        print(f"Auto sync epäonnistui: {exc}")

async def _main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(_main())
