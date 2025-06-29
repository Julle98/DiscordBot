import os, requests, asyncio, discord
from discord import app_commands

async def kirjaa_ga_event(user_id: int, event_name: str):
    mid = os.getenv("GA_MEASUREMENT_ID")
    secret = os.getenv("GA_API_SECRET")
    if not (mid and secret):
        print("GA‑asetukset puuttuvat.")
        return

    endpoint = (
        f"https://www.google-analytics.com/mp/collect?"
        f"measurement_id={mid}&api_secret={secret}"
    )
    payload = {
        "client_id": str(user_id),
        "events": [{"name": event_name, "params": {"engagement_time_msec": "100"}}],
    }

    loop = asyncio.get_running_loop()
    try:
        resp = await loop.run_in_executor(None, requests.post, endpoint, payload)
        if resp.status_code != 204:
            print("GA‑tapahtuman lähetys epäonnistui:", resp.text)
    except Exception as e:
        print("GA‑virhe:", e)

async def kirjaa_komento_lokiin(bot: discord.Client, interaction: discord.Interaction, cmd: str):
    log_id = int(os.getenv("LOG_CHANNEL_ID", 0))
    if not log_id:
        return
    chan = bot.get_channel(log_id)
    if chan:
        user = interaction.user
        await chan.send(
            f"📝 Komento: `{cmd}`\n"
            f"👤 Käyttäjä: {user} ({user.id})"
        )

async def autocomplete_bannatut_käyttäjät(
    interaction: discord.Interaction, current: str
):
    choices = []
    try:
        async for ban in interaction.guild.bans(limit=50):
            usr, reason = ban.user, ban.reason or "Ei syytä annettu"
            label = f"{usr.name}#{usr.discriminator}" if usr.discriminator else usr.name
            if current.lower() in label.lower():
                name = f"{label} – {reason[:50]}"
                choices.append(app_commands.Choice(name=name, value=label))
            if len(choices) >= 25:
                break
    except Exception as e:
        print("Autocomplete error:", e)
    return choices
