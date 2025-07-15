import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.tiedot_utils import muodosta_embed_käyttäjälle, DataValintaView

class TiedotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tiedot", description="Näytä oma tai toisen käyttäjän bottidata.")
    @app_commands.describe(käyttäjä="(vain Mestari) Näytä toisen käyttäjän tiedot.")
    async def tiedot(self, interaction: discord.Interaction, käyttäjä: discord.User = None):
        await interaction.response.defer(ephemeral=True)

        if käyttäjä and not any(r.name == "Mestari" for r in interaction.user.roles):
            await interaction.followup.send("⚠️ Sinulla ei ole oikeuksia tarkastella muiden tietoja.", ephemeral=True)
            return

        target = käyttäjä or interaction.user
        embed = await muodosta_embed_käyttäjälle(target)
        view = DataValintaView(target)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TiedotCog(bot))
