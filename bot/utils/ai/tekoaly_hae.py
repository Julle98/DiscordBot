from bot.utils.ai.web_search import simple_web_search
import asyncio

async def suorita_haku(kysymys: str) -> str:
    return await asyncio.to_thread(simple_web_search, kysymys)
