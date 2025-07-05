from bot.utils.ai.llm import generate_reply
import asyncio

async def suorita_kysymys(kysymys: str) -> str:
    return await asyncio.to_thread(generate_reply, kysymys)
