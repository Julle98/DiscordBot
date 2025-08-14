import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin, autocomplete_bannatut_käyttäjät
from dotenv import load_dotenv
import os
from bot.utils.error_handler import CommandErrorHandler

load_dotenv()
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

class Moderation_kickban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Poista käyttäjä palvelimelta.")
    @app_commands.describe(
        member="Käyttäjä",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/kick")
        await kirjaa_ga_event(self.bot, interaction.user.id, "kick_komento")

        poistetut = []
        if viesti_id:
            ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
            for vid in ids:
                try:
                    msg = await interaction.channel.fetch_message(int(vid))
                    if msg.author.id == member.id:
                        await msg.delete()
                        poistetut.append(vid)
                except:
                    continue

        try:
            await member.send(f"Sinut on potkittu palvelimelta {interaction.guild.name}.\nSyy: {syy}")
        except discord.Forbidden:
            pass

        try:
            await member.kick(reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{member.mention} on potkittu. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"👢 **Potku**\n👤 {member.mention}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n🗑 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except Exception as e:
            await interaction.response.send_message(f"Potku epäonnistui: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Bannaa käyttäjä.")
    @app_commands.describe(
        member="Käyttäjä",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ban")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ban_komento")

        poistetut = []
        if viesti_id:
            ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
            for vid in ids:
                try:
                    msg = await interaction.channel.fetch_message(int(vid))
                    if msg.author.id == member.id:
                        await msg.delete()
                        poistetut.append(vid)
                except:
                    continue

        try:
            await member.send(f"Sinut on bannattu palvelimelta {interaction.guild.name}.\nSyy: {syy}")
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{member.mention} on bannattu. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"⛔ **Porttikielto**\n👤 {member.mention}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n🗑 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except discord.Forbidden:
            await interaction.response.send_message("Ei oikeuksia bannata tätä käyttäjää.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Bannaus epäonnistui: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Poista käyttäjän porttikielto.")
    @app_commands.describe(
        käyttäjänimi="Käyttäjänimi muodossa nimi#0001",
        syy="Syy unbannille",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.autocomplete(käyttäjänimi=autocomplete_bannatut_käyttäjät)
    async def unban(self, interaction: discord.Interaction, käyttäjänimi: str, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/unban")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unban_komento")

        try:
            banned_users = [entry async for entry in interaction.guild.bans()]
        except Exception as e:
            await interaction.followup.send(f"Virhe haettaessa banneja: {e}", ephemeral=True)
            return

        nimi, _, discrim = käyttäjänimi.partition("#")
        if "#" in käyttäjänimi and not discrim.isdigit():
            await interaction.followup.send("Virheellinen käyttäjänimi. Käytä muotoa nimi#1234.", ephemeral=True)
            return

        for ban_entry in banned_users:
            user = ban_entry.user
            match = (user.name, user.discriminator) == (nimi, discrim) if discrim else user.name == käyttäjänimi
            if match:
                try:
                    await user.send(f"Porttikielto palvelimelta {interaction.guild.name} on poistettu.\nSyy: {syy}")
                except discord.Forbidden:
                    pass

                await interaction.guild.unban(user, reason=f"{syy} (Poisti: {interaction.user})")
                await interaction.followup.send(f"{user.name}#{user.discriminator} unbannattu. Syy: {syy}")

                modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
                if modlog_channel:
                    log_msg = f"✅ **Unban**\n👤 {user.mention if hasattr(user, 'mention') else user.name}\n📝 {syy}\n👮 {interaction.user.mention}"
                    await modlog_channel.send(log_msg)
                return

        await interaction.followup.send("Käyttäjää ei löytynyt bannatuista.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_kickban(bot)
    await bot.add_cog(cog)