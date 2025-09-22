import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from dotenv import load_dotenv
import os
from bot.utils.error_handler import CommandErrorHandler

class Moderation_roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_role", description="Lisää roolin käyttäjälle.")
    @app_commands.checks.has_role("Mestari")
    async def set_role(self, interaction: discord.Interaction, käyttäjä: discord.Member, rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/set_role")
        await kirjaa_ga_event(self.bot, interaction.user.id, "set_role_komento")
        await käyttäjä.add_roles(rooli)
        await interaction.response.send_message(
            f"Rooli **{rooli.name}** lisätty käyttäjälle {käyttäjä.mention}.✅", ephemeral=True
        )

    @app_commands.command(name="remove_role", description="Poistaa roolin käyttäjältä.")
    @app_commands.checks.has_role("Mestari")
    async def remove_role(self, interaction: discord.Interaction, käyttäjä: discord.Member, rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/remove_role")
        await kirjaa_ga_event(self.bot, interaction.user.id, "remove_role_komento")
        await käyttäjä.remove_roles(rooli)
        await interaction.response.send_message(
            f"Rooli **{rooli.name}** poistettu käyttäjältä {käyttäjä.mention}. 🗑️", ephemeral=True
        )

    @app_commands.command(name="vaihda_nimimerkki", description="Vaihda jäsenen nimimerkki palvelimella.")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.checks.has_role("Mestari")
    async def vaihda_nimimerkki(self, interaction: discord.Interaction, jasen: discord.Member, uusi_nimimerkki: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vaihda_nimimerkki")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vaihda_nimimerkki_komento")
        try:
            await jasen.edit(nick=uusi_nimimerkki)
            await interaction.response.send_message(f"{jasen.mention} nimimerkki vaihdettu: {uusi_nimimerkki}")
        except discord.Forbidden:
            await interaction.response.send_message("En voi vaihtaa tämän jäsenen nimimerkkiä.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe: {e}", ephemeral=True)

    @app_commands.command(name="vaihda_rooli", description="Vaihda jäseneltä rooli toiseen.")
    @app_commands.checks.has_role("Mestari")
    async def vaihda_rooli(self, interaction: discord.Interaction, käyttäjä: discord.Member, vanha_rooli: discord.Role, uusi_rooli: discord.Role):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vaihda_rooli")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vaihda_rooli_komento")

        if vanha_rooli.id == uusi_rooli.id:
            await interaction.response.send_message("Vanha ja uusi rooli ovat sama. 🤔", ephemeral=True)
            return

        if vanha_rooli not in käyttäjä.roles:
            await interaction.response.send_message(f"Käyttäjällä {käyttäjä.mention} ei ole roolia **{vanha_rooli.name}**.", ephemeral=True)
            return

        try:
            await käyttäjä.remove_roles(vanha_rooli)
            await käyttäjä.add_roles(uusi_rooli)
            await interaction.response.send_message(
                f"Rooli **{vanha_rooli.name}** poistettu ja **{uusi_rooli.name}** lisätty käyttäjälle {käyttäjä.mention}. 🔄",
                ephemeral=True
            )

            mod_log_channel_id = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
            mod_log_channel = self.bot.get_channel(mod_log_channel_id)
            if mod_log_channel:
                await mod_log_channel.send(
                    f"🔄 {interaction.user.mention} vaihtoi roolin käyttäjältä {käyttäjä.mention}: "
                    f"**{vanha_rooli.name}** → **{uusi_rooli.name}**"
                )
        except discord.Forbidden:
            await interaction.response.send_message("Minulla ei ole oikeuksia muuttaa tämän jäsenen rooleja.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe roolia vaihtaessa: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_roles(bot)
    await bot.add_cog(cog)