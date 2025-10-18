import sys
import os
import asyncio
import discord
from discord.ext import commands
from bot.main import load_cogs
from bot.utils.bot_setup import bot

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))

async def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN ei ole asetettu ympäristömuuttujana.")

    async with bot:
        await load_cogs() 
        for attempt in range(3):
            try:
                await bot.start(token)
                break
            except discord.errors.DiscordServerError as e:
                print(f"❌ Yritys {attempt + 1}: Discordin palvelinvirhe: {e}")
                await asyncio.sleep(10)
            except discord.LoginFailure as e:
                print(f"❌ Kirjautuminen epäonnistui: {e}")
                break
            except Exception as e:
                print(f"❌ Tuntematon virhe: {e}")
                break
            finally:
                if not bot.is_closed():
                    await bot.close()
                    print("🔒 Botti suljettu siististi.")

if __name__ == "__main__":
    asyncio.run(main())