import discord
from discord.ext import commands
from discord import app_commands
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class Scores(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_scores", description="Näytä pelien voitot ja XP")
    async def scores(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_scores")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_scores_komento")
        user_stats, user_xp = games_utils.get_user_stats(interaction.user.id)
        global_stats = games_utils.get_global_stats()

        embed = discord.Embed(
            title="🎮 Peliscores & XP",
            color=discord.Color.green()
        )

        pelit = "\n".join(
            f"{game}: {count} voittoa"
            for game, count in user_stats.items()
            if game != "total_wins"
        ) or "Ei vielä voittoja"

        embed.add_field(
            name=f"👤 {interaction.user.name}",
            value=f"Total voitot: {user_stats.get('total_wins', 0)}\n"
                  f"XP: {user_xp}\n{pelit}",
            inline=False
        )

        desc = ""
        for idx, (uid, xp) in enumerate(global_stats, start=1):
            user = self.bot.get_user(uid)
            name = user.name if user else f"User {uid}"
            desc += f"**{idx}. {name}** — {xp} XP\n"

        embed.add_field(name="🌍 Top 10 (XP)", value=desc or "Ei pisteitä vielä", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Scores(bot))