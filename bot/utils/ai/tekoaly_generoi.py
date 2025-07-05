from bot.utils.ai.image_gen import generate_image
import asyncio
import discord

async def suorita_kuvagenerointi(kuvaus: str) -> discord.File:
    await asyncio.to_thread(generate_image, kuvaus)
    return discord.File("output.png")
