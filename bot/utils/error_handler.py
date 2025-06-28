from discord import Interaction
from discord.app_commands import AppCommandError, MissingRole
from datetime import timedelta
import discord

async def handle_command_error(bot, interaction: Interaction, error: AppCommandError):
    user_id = interaction.user.id

    if isinstance(error, MissingRole):
        if not hasattr(bot, "command_attempts"):
            bot.command_attempts = {}
        bot.command_attempts[user_id] = bot.command_attempts.get(user_id, 0) + 1

        if bot.command_attempts[user_id] > 2:
            await interaction.response.send_message(
                "Olet yrittänyt käyttää komentoa ilman oikeuksia yli 3 kertaa. Saat 30 minuutin jäähyn.",
                ephemeral=True
            )
            await interaction.user.edit(
                timed_out_until=discord.utils.utcnow() + timedelta(minutes=30),
                reason="Botin sääntöjen rikkominen"
            )
            bot.command_attempts[user_id] = 0
        else:
            await interaction.response.send_message(
                "Tämä komento on vain rooleille Mestari ja/tai Moderaattori.",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            f"Tapahtui virhe: {error}", ephemeral=True
        )
