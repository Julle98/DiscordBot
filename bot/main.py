import os, asyncio, logging, discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime
from datetime import datetime, timedelta
from collections import defaultdict
from collections import defaultdict, deque
import time
from bot.utils.bot_setup import bot
from bot.utils.env_loader import load_env_and_validate
from bot.utils.moderation_tasks import start_moderation_loops
from bot.utils.antinuke import start_antinuke_loops
from bot.utils.store_utils import start_store_loops
from bot.utils.tasks_utils import start_tasks_loops
from bot.utils.antinuke import check_deletions
from bot.utils.xp_utils import anna_xp_komennosta
from bot.utils.ruokailuvuorot_utils import paivita_ruokailuvuorot
from bot.utils.time_utils import get_current_time_in_helsinki
from bot.utils.settings_utils import get_user_settings
from bot.cogs.ruoka import RuokaÄänestysView

load_env_and_validate()
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", 0))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))   

VALINNAISET_KOMENNOT = {
    "kauppa": lambda interaction: hasattr(interaction, "namespace") and (
        getattr(interaction.namespace, "tuote", None) is not None or
        getattr(interaction.namespace, "kuponki", None) is not None
    ),
    "laskin": lambda interaction: hasattr(interaction, "namespace") and (
        getattr(interaction.namespace, "selitys", None) is not None
    ),
    "tiedot": lambda interaction: hasattr(interaction, "namespace") and (
        getattr(interaction.namespace, "käyttäjä", None) is not None
    )
}

komento_loki = defaultdict(lambda: deque(maxlen=10))
JAAHY_KESTO = 15 * 60  
TAUKO_KOMENNOT = {"kauppa", "tehtävät", "tiedot"}
SPAM_EXEMPT_ROLE_IDS = [1339853855315197972, 1368228763770294375, 1339846508199022613, 1368538894034800660]

komento_ajastukset: dict[int, dict[str, datetime]] = defaultdict(dict)

COGS = [
    "bot.cogs.utils",
    "bot.cogs.tasks",
    "bot.cogs.stats",
    "bot.cogs.levels",
    "bot.cogs.store",
    "bot.cogs.dmviesti",
    "bot.cogs.ruoka",
    "bot.cogs.polls",
    "bot.cogs.vip",
    "bot.cogs.xp_voice",
    "bot.cogs.backup_cog",
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
    "bot.cogs.nightrestriction",
    "bot.cogs.vault",
    "bot.cogs.calender",
    "bot.cogs.weather",
    "bot.cogs.settings",
    "bot.cogs.slowmode",
    "bot.cogs.games.arvaa_luku",
    "bot.cogs.games.arvaa_sana",
    "bot.cogs.games.game_scores",
    "bot.cogs.games.miinaharava",
    "bot.cogs.games.ristinolla"
]

async def load_cogs():
    print("🔄 Ladataan cogeja…")
    for name in COGS:
        try:
            await bot.load_extension(name)
            print(f"  ✅ {name}")
        except Exception as exc:
            print(f"  ❌ {name}: {exc}")

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
    await bot.wait_until_ready()

    if bot.user:
        print(f"{bot.user} käynnissä")
    else:
        print("⚠️ Botti ei ole kirjautunut sisään, bot.user on None")
        return  

    if bot.cogs:
        for cog_name in bot.cogs:
            print(f"✅ Cog valmiina: {cog_name}")
    else:
        print("⚠️ Yhtään cogia ei ole ladattu.")

    try:
        bot_status_kanava = discord.utils.get(bot.get_all_channels(), name="🛜bot-status")
        if bot_status_kanava:
            print("Poistetaan vanhoja botin tilaviestejä...")
            async for message in bot_status_kanava.history(limit=100):
                await message.delete()

            current_time = get_current_time_in_helsinki()
            bot_version = os.getenv("BOT_VERSION", "tuntematon")
            bot_name = bot.user.name
            bot_avatar_url = bot.user.avatar.url if bot.user.avatar else None

            embed = discord.Embed(
                title=f"🤖 {bot_name} on käynnissä",
                description="Botti on nyt toiminnassa ja valmiina auttamaan!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=bot_avatar_url)
            embed.add_field(name="🕒 Käynnistysaika", value=current_time, inline=False)
            embed.add_field(
                name="🛠️ Ongelmatilanteet",
                value="Käytä komentoa `/help` tai kirjoita <#1339858713804013598> kanavalle.",
                inline=False
            )
            embed.set_footer(text=f"Versio: {bot_version}", icon_url=None)

            await bot_status_kanava.send(embed=embed)
            print("Embed-tilaviesti lähetetty.")
        else:
            print("🛜bot-status kanavaa ei löytynyt, tilaviestiä ei lähetetty.")
    except Exception as e:
        print(f"Virhe botin tilaviestin lähetyksessä: {e}")

    check_deletions.start()
    start_moderation_loops()
    start_antinuke_loops()
    start_store_loops()
    start_tasks_loops()
    paivita_ruokailuvuorot()

    try:
        päivä_id = get_current_time_in_helsinki() 
        bot.add_view(RuokaÄänestysView(päivä_id))
        print(f"✅ Persistent view rekisteröity päivälle {päivä_id}")
    except Exception as exc:
        print(f"❌ View-rekisteröinti epäonnistui: {exc}")

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

    if TEST_GUILD_ID:
        try:
            guild = discord.Object(TEST_GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synkronoitu {len(synced)} komentoa testipalvelimelle.")
        except Exception as exc:
            print(f"Synkronointi testipalvelimelle epäonnistui: {exc}")
    else:
        try:
            synced = await bot.tree.sync()
            print(f"Synkronoitu {len(synced)} komentoa globaalisti.")
        except Exception as exc:
            print(f"Synkronointi globaalisti epäonnistui: {exc}")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command):
    try:
        user_id = interaction.user.id
        
        settings = get_user_settings(user_id)

        if not settings["xp_komennot"]:
            return
        
        extras = getattr(interaction, "extras", {})
        if extras.get("cooldown_skip"):
            return

        komento_nimi = command.name
        ehto = VALINNAISET_KOMENNOT.get(komento_nimi)
        if ehto and not ehto(interaction):
            return

        if callable(anna_xp_komennosta):
            await anna_xp_komennosta(bot, interaction)
        else:
            print("Varoitus: anna_xp_komennosta ei ole callable!")

        user = interaction.user
        user_id = user.id
        timestamp = time.time()
        komento_loki[user_id].append((komento_nimi, timestamp))

        recent = [t for k, t in komento_loki[user_id] if timestamp - t <= 10]
        tauko_recent = [t for k, t in komento_loki[user_id] if k in TAUKO_KOMENNOT and timestamp - t <= 30]

        if len(recent) > 3 or len(tauko_recent) > 5:
            komento_loki[user_id].clear()
            exempt = any(role.id in SPAM_EXEMPT_ROLE_IDS for role in getattr(user, "roles", []))

            mute_channel_id = int(os.getenv("MUTE_CHANNEL_ID", 0))
            mute_channel = bot.get_channel(mute_channel_id)

            loki_viesti = (
                "🔇 Jäähy asetettu (automaattinen)\n"
                f"👤 Käyttäjä: {user.mention}\n"
                f"⏱ Kesto: {'15 minuuttia' if not exempt else 'Ei asetettu'}\n"
                "📝 Syy: Komento spam\n"
                "👮 Asetti: Sannamaija"
            )

            if mute_channel:
                await mute_channel.send(loki_viesti)

            if not exempt:
                try:
                    await user.timeout(timedelta(seconds=JAAHY_KESTO), reason="Komento spam")

                    dm_viesti = "Sinut asetettiin 15 min minuutin jäähylle: **Komento spam**."
                    await user.send(dm_viesti)

                    await interaction.delete_original_response()

                except discord.Forbidden:
                    print(f"DM-viestin lähetys epäonnistui: käyttäjä {user} ei hyväksy viestejä.")
                except Exception as timeout_error:
                    print(f"Jäähyn asettaminen epäonnistui: {timeout_error}")

    except Exception as e:
        print(f"XP:n antaminen tai spam-tarkistus epäonnistui: {e}")

async def _main():
    await load_cogs()
    try:
        await bot.start(TOKEN)
    except discord.errors.DiscordServerError as e:
        print(f"Discordin palvelinvirhe: {e}")
    except discord.LoginFailure as e:
        print(f"Kirjautuminen epäonnistui: {e}")
    except Exception as e:
        print(f"Tuntematon virhe: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
        asyncio.run(_main())