import discord
from discord.ext import commands
from discord import app_commands
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class Scores(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_scores", description="Näytä omat ja globaalit peliscores sekä XP")
    async def scores(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_scores")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_scores_komento")
        user_stats, user_xp = games_utils.get_user_stats(interaction.user.id)

        pelit = "\n".join(
            f"{game}: {count} voittoa"
            for game, count in user_stats.items()
            if game not in ["total_wins", "total_xp"]
        ) or "Ei vielä voittoja"

        global_ranking = games_utils.get_global_stats()
        ranking_text = ""
        for idx, (uid, xp) in enumerate(global_ranking, start=1):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            ranking_text += f"**{idx}. {name}** – {xp} XP\n"

        embed = discord.Embed(
            title="🎮 Peliscores",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"Omat statsit ({interaction.user.name})",
            value=f"Voitot: {user_stats.get('total_wins', 0)}\n"
                f"XP: {user_stats.get('total_xp', 0)}\n"
                f"Pelejä yhteensä: {user_stats.get('total_games', '–')}\n\n{pelit}",
            inline=False
        )
        embed.add_field(
            name="🌍 Globaali top 10",
            value=ranking_text or "Ei vielä tietoja",
            inline=False
        )

        embed.set_footer(text="Pelitilastot päivittyvät automaattisesti")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Scores(bot))
