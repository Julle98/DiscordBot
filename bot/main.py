import os, asyncio, logging, discord
from discord.ext import commands
from dotenv import load_dotenv
import random
from bot.utils.bot_setup import bot
from bot.utils.env_loader import load_env_and_validate
from bot.utils.moderation_tasks import start_moderation_loops
from bot.utils.store_utils import start_store_loops
from bot.utils.tasks_utils import start_tasks_loops
from bot.utils.status_updater import update_status
from bot.cogs.levels import tarkista_puhekanavat
from bot.utils.antinuke import check_deletions
from utils.ai.image_gen import generate_image

load_env_and_validate()
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0))   

COGS = [
    "bot.cogs.utils",
    "bot.cogs.tasks",
    "bot.cogs.stats",
    "bot.cogs.levels",
    "bot.cogs.store",
    "bot.cogs.moderation",
    "bot.cogs.misc",
    "bot.cogs.ai",
    "bot.cogs.xp_system",
    "bot.utils.welcomecog",
    "bot.utils.xptracker",
    "bot.utils.antinuke",
    "bot.utils.error_handler",
    "bot.utils.logger",
    "bot.utils.monitoring",
    "bot.utils.status_updater",
    "bot.cogs.quiz",
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
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "image":
        prompt = " ".join(sys.argv[2:]) or "a fantasy landscape with mountains and a river"
        print(f"🎨 Generoidaan kuva kehotteella: {prompt}")
        generate_image(prompt)
        print("✅ Kuva tallennettu tiedostoon output.png")
    else:
        asyncio.run(_main())
