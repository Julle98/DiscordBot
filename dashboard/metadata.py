import httpx, os

async def push_role_connection(token, msgs, xp, lvl):
    url = f"https://discord.com/api/v10/users/@me/applications/{os.getenv('CLIENT_ID')}/role-connection"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "platform_name": "Sannamaija",
        "metadata": {
            "msgs_sent": msgs,
            "xp_level": xp,
            "user_level": lvl
        }
    }
    async with httpx.AsyncClient() as cx:
        await cx.put(url, headers=headers, json=payload)
