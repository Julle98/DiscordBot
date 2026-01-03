import os, json, asyncio
from typing import Optional

STATUS_JSON_PATH = os.getenv("STATUS_JSON_PATH")
_lock = asyncio.Lock()

async def load_status_ids() -> dict:
    async with _lock:
        if not os.path.exists(STATUS_JSON_PATH):
            return {}
        try:
            with open(STATUS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

async def save_status_ids(data: dict) -> None:
    async with _lock:
        with open(STATUS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

async def get_status_message_id(guild_id: int) -> Optional[int]:
    data = await load_status_ids()
    return data.get(str(guild_id))

async def set_status_message_id(guild_id: int, message_id: int) -> None:
    data = await load_status_ids()
    data[str(guild_id)] = message_id
    await save_status_ids(data)

async def clear_status_message_id(guild_id: int) -> None:
    data = await load_status_ids()
    data.pop(str(guild_id), None)
    await save_status_ids(data)
