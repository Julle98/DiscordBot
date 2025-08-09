import os, asyncio, logging, discord
from discord.ext import commands
from dotenv import load_dotenv
import random
from bot.utils.bot_setup import bot
from bot.utils.env_loader import load_env_and_validate
from bot.utils.moderation_tasks import start_moderation_loops
from bot.utils.store_utils import start_store_loops
from bot.utils.tasks_utils import start_tasks_loops
from bot.utils.antinuke import check_deletions
from bot.utils.xp_utils import anna_xp_komennosta
from bot.utils.ruokailuvuorot_utils import paivita_ruokailuvuorot_json

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
    "bot.cogs.dmviesti",
    "bot.cogs.ruoka",
    "bot.cogs.polls",
    "bot.cogs.xp_voice",
    "bot.cogs.moderation",
    "bot.cogs.moderation_channels",
    "bot.cogs.moderation_kickban",
    "bot.cogs.moderation_messages",
    "bot.cogs.moderation_mute",
    "bot.cogs.moderation_roles",
    "bot.cogs.moderation_status",
    "bot.cogs.moderation_warning",
    "bot.cogs.misc",
    "bot.cogs.xp_system",
    "bot.utils.welcomecog",
    "bot.utils.antinuke",
    "bot.utils.error_handler",
    "bot.utils.logger",
    "bot.utils.monitoring",
    "bot.utils.status_updater",
    "bot.cogs.quiz",
    "bot.cogs.deletion",
    "bot.cogs.events",
    "bot.cogs.tiedot",
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
    start_moderation_loops()
    start_store_loops()
    start_tasks_loops()
    paivita_ruokailuvuorot_json()

    try:
        xp_path = os.getenv("XP_JSON_PATH")
        if xp_path and os.path.exists(xp_path):
            from bot.utils.antinuke import XPFileChangeHandler
            from watchdog.observers import Observer

            event_handler = XPFileChangeHandler(bot)
            observer = Observer()
            observer.schedule(event_handler, path=os.path.dirname(xp_path), recursive=False)
            observer.start()

            print(f"XP JSON tiedoston monitorointi käynnistetty: {xp_path}")
        else:
            print("XP_JSON_PATH ei määritelty tai tiedostoa ei löytynyt.")
    except Exception as exc:
        print(f"XP-monitorin käynnistys epäonnistui: {exc}")

    try:
        if TEST_GUILD_ID:
            synced = await bot.tree.sync(guild=discord.Object(TEST_GUILD_ID))
        else:
            synced = await bot.tree.sync()
        print("Slash komennot synkronoitu. Synkronoidut komennot:", len(synced))
    except Exception as exc:
        print(f"Auto sync epäonnistui: {exc}")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command):
    try:
        await anna_xp_komennosta(bot, interaction)
    except Exception as e:
        print(f"XP:n antaminen epäonnistui: {e}")

async def _main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
        asyncio.run(_main())
