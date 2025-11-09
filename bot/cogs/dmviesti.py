import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
import os

class DMViesti(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dmviesti", description="Lähetä yksityisviesti jäsenelle botin nimissä.")
    @app_commands.checks.has_role("Mestari")
    async def dmviesti(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        viesti: str,
        emoji: str = None,
        rooli: discord.Role = None,
        emoji_viesti: bool = False,
        rooli_viesti: bool = False
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/dmviesti")
        await kirjaa_ga_event(self.bot, interaction.user.id, "dmviesti_komento")

        if emoji_viesti and rooli_viesti:
            await interaction.response.send_message(
                "Valitse vain joko `emoji_viesti` tai `rooli_viesti`, ei molempia yhtä aikaa.", ephemeral=True
            )
            return

        try:
            if emoji_viesti and emoji:
                viesti = (
                    f"⌛ Emoji-oikeutesi ({emoji}) on päättynyt.\n"
                    f"🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉"
                )
            elif rooli_viesti and rooli:
                viesti = (
                    f"⌛ Oikeutesi **{rooli.name}** on vanhentunut.\n"
                    f"🛒 Voit nyt ostaa lisää tuotteita komennolla **/kauppa** 🎉"
                )

            await member.send(viesti)
            await interaction.response.send_message(
                f"Viesti lähetetty jäsenelle {member.display_name}.", ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message("En voi lähettää viestiä tälle jäsenelle.", ephemeral=True)
 
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = DMViesti(bot)
    await bot.add_cog(cog)