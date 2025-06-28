import random
import asyncio
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
from collections import deque
from bot.utils.bot_setup import bot

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