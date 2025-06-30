import os
import asyncio
import requests
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

def _cog(bot: commands.Bot) -> Optional[commands.Cog]:
    return bot.get_cog("AnalyticsLogging")

async def kirjaa_ga_event(bot: commands.Bot, user_id: int, event_name: str) -> None:
    if (cog := _cog(bot)):
        await AnalyticsLogging.kirjaa_ga_event(user_id, event_name)

async def kirjaa_komento_lokiin(
    bot: commands.Bot,
    interaction: discord.Interaction,
    command_name: str,
) -> None:
    if (cog := _cog(bot)):
        await AnalyticsLogging.kirjaa_komento_lokiin(interaction, command_name)

async def autocomplete_bannatut_käyttäjät(
    bot: commands.Bot,
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    if (cog := _cog(bot)):
        return await AnalyticsLogging.autocomplete_bannatut_käyttäjät(interaction, current)
    return []

class AnalyticsLogging(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ga_measurement_id = os.getenv("GA_MEASUREMENT_ID")
        self.ga_api_secret   = os.getenv("GA_API_SECRET")
        self.log_channel_id  = int(os.getenv("LOG_CHANNEL_ID", "0"))

    async def kirjaa_ga_event(self, user_id: int, event_name: str) -> None:
        if not (self.ga_measurement_id and self.ga_api_secret):
            return

        endpoint = (
            "https://www.google-analytics.com/mp/collect"
            f"?measurement_id={self.ga_measurement_id}&api_secret={self.ga_api_secret}"
        )
        payload = {
            "client_id": str(user_id),
            "events": [{"name": event_name, "params": {"engagement_time_msec": "100"}}],
        }

        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(None, requests.post, endpoint, payload)
            if resp.status_code != 204:
                print("GA‑event failed:", resp.text)
        except Exception as exc:
            print("GA error:", exc)

    async def kirjaa_komento_lokiin(
        self, interaction: discord.Interaction, command_name: str
    ) -> None:
        if not self.log_channel_id:
            return
        channel = self.bot.get_channel(self.log_channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        try:
            await channel.send(
                f"📝 Komento: `{command_name}`\n👤 Käyttäjä: {interaction.user} ({interaction.user.id})"
            )
        except Exception as exc:
            print("Logging error:", exc)

    async def autocomplete_bannatut_käyttäjät(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        try:
            async for ban in interaction.guild.bans(limit=50):
                user, reason = ban.user, ban.reason or "Ei syytä annettu"
                label = f"{user.name}#{user.discriminator}" if user.discriminator else user.name
                if current.lower() in label.lower():
                    txt = f"{label} – {reason[:50]}"
                    choices.append(app_commands.Choice(name=txt, value=label))
                if len(choices) >= 25:
                    break
        except Exception as exc:
            print("Autocomplete error:", exc)
        return choices

async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsLogging(bot))
