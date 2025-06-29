from discord import Interaction
from discord.app_commands import AppCommandError, MissingRole
from datetime import timedelta
import discord
import logging
from discord.ext import commands

class CommandErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_attempts: dict[int, int] = {}

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        user_id = interaction.user.id

        if isinstance(error, discord.app_commands.MissingRole):
            self.command_attempts[user_id] = self.command_attempts.get(user_id, 0) + 1

            if self.command_attempts[user_id] > 2:
                await interaction.response.send_message(
                    "Olet yrittänyt käyttää komentoa ilman oikeuksia yli 3 kertaa. Saat 30 min jäähyn.",
                    ephemeral=True,
                )
                await interaction.user.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(minutes=30),
                    reason="Botin sääntöjen rikkominen",
                )
                self.command_attempts[user_id] = 0
            else:
                await interaction.response.send_message(
                    "Tämä komento on vain rooleille Mestari ja/tai Moderaattori.",
                    ephemeral=True,
                )
        else:
            await interaction.response.send_message(
                f"Tapahtui virhe: {error}", ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(CommandErrorHandler(bot))
