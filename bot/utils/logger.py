import os
import asyncio
import requests
import discord
from discord import app_commands
from discord.ext import commands

class AnalyticsLogging(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ga_measurement_id: str | None = os.getenv("GA_MEASUREMENT_ID")
        self.ga_api_secret: str | None = os.getenv("GA_API_SECRET")
        self.log_channel_id: int = int(os.getenv("LOG_CHANNEL_ID", "0"))

    async def log_ga_event(self, user_id: int, event_name: str) -> None:
        """Send a custom event to Google Analytics 4 via Measurement Protocol.

        Parameters
        ----------
        user_id: int
            Discord user ID, used as GA client_id.
        event_name: str
            Name of the event, e.g. "command_used".
        """
        if not (self.ga_measurement_id and self.ga_api_secret):
            return

        endpoint = (
            "https://www.google-analytics.com/mp/collect?"
            f"measurement_id={self.ga_measurement_id}&api_secret={self.ga_api_secret}"
        )
        payload = {
            "client_id": str(user_id),
            "events": [
                {
                    "name": event_name,
                    "params": {
                        "engagement_time_msec": "100",
                    },
                }
            ],
        }

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None, requests.post, endpoint, payload
            )
            if response.status_code != 204:
                print("GA‑event failed:", response.text)
        except Exception as exc:
            print("GA error:", exc)

    async def log_command(
        self,
        interaction: discord.Interaction,
        command_name: str,
    ) -> None:
        """Write a short log message about a used application command."""
        if not self.log_channel_id:
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        user = interaction.user
        try:
            await channel.send(
                f"📝 Komento: `{command_name}`\n" f"👤 Käyttäjä: {user} ({user.id})"
            )
        except Exception as exc:
            print("Logging error:", exc)

    async def banned_users_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices: list[app_commands.Choice[str]] = []
        try:
            async for ban_entry in interaction.guild.bans(limit=50):
                user, reason = ban_entry.user, ban_entry.reason or "Ei syytä annettu"
                label = (
                    f"{user.name}#{user.discriminator}"
                    if user.discriminator
                    else user.name
                )
                if current.lower() in label.lower():
                    choice_name = f"{label} – {reason[:50]}"
                    choices.append(app_commands.Choice(name=choice_name, value=label))
                if len(choices) >= 25:
                    break
        except Exception as exc:
            print("Autocomplete error:", exc)

        return choices

async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsLogging(bot))
