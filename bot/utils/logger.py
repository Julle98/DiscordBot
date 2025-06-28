import discord
import requests
import os
from discord import app_commands
from typing import List

def kirjaa_ga_event(user_id, event_name):
    measurement_id = os.getenv("GA_MEASUREMENT_ID")
    api_secret = os.getenv("GA_API_SECRET")
    
    if not measurement_id or not api_secret:
        print("Google Analytics asetukset puuttuvat.")
        return

    endpoint = f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}"

    payload = {
        "client_id": str(user_id),
        "events": [
            {
                "name": event_name,
                "params": {
                    "engagement_time_msec": "100",
                    "user_id": str(user_id)  
                }
            }
        ]
    }

    try:
        response = requests.post(endpoint, json=payload)
        if response.status_code != 204:
            print("GA-tapahtuman lähetys epäonnistui:", response.text)
    except Exception as e:
        print("GA-virhe:", e)
        return

async def kirjaa_komento_lokiin(bot, interaction: discord.Interaction, komento: str):
    log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        käyttäjä = interaction.user
        await log_channel.send(
            f"📝 Komento: `{komento}`\n👤 Käyttäjä: {käyttäjä.name}#{käyttäjä.discriminator} ({käyttäjä.id})"
        )

async def autocomplete_bannatut_käyttäjät(interaction: discord.Interaction, current: str):
    try:
        banned_users = []
        async for entry in interaction.guild.bans():
            banned_users.append(entry)
            if len(banned_users) >= 50:
                break

        choices = []
        for ban_entry in banned_users:
            user = ban_entry.user
            reason = ban_entry.reason or "Ei syytä annettu"
            label = f"{user.name}#{user.discriminator}" if user.discriminator else user.name

            if current.lower() in label.lower():
                display_name = f"{label} – {reason[:50]}"
                choices.append(app_commands.Choice(name=display_name, value=label))

            if len(choices) >= 25:
                break

        return choices

    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []