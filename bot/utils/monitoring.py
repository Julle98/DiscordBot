import os
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging
from collections import deque
from bot.utils.bot_setup import bot

load_dotenv()
SLOWMODE_CHANNEL_ID = int(os.getenv("SLOWMODE_CHANNEL_ID", 0))

async def tarkkaile_kanavan_aktiivisuutta():
    await bot.wait_until_ready()
    kanava = bot.get_channel(SLOWMODE_CHANNEL_ID)
    if not kanava:
        print("Hidastuskanavaa ei löytynyt.")
        return

    while not bot.is_closed():
        nyt = datetime.now(timezone.utc)
        aktiiviset_viestit = 0

        try:
            async for msg in kanava.history(limit=100, after=nyt - timedelta(seconds=30)):
                if not msg.author.bot:
                    aktiiviset_viestit += 1
        except Exception as e:
            print(f"Virhe viestien haussa: {e}")
            await asyncio.sleep(30)
            continue

        try:
            if aktiiviset_viestit >= 15 and kanava.slowmode_delay == 0:
                await kanava.edit(slowmode_delay=5)
                print("Hidastustila asetettu 5 sekuntiin.")
            elif aktiiviset_viestit < 3 and kanava.slowmode_delay > 0:
                await kanava.edit(slowmode_delay=0)
                print("Hidastustila poistettu.")
        except Exception as e:
            print(f"Virhe hidastustilan muokkauksessa: {e}")

        await asyncio.sleep(30)