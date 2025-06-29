import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio  
from datetime import datetime, timedelta
from collections import defaultdict
import discord
from bot.utils.bot_setup import bot 
from bot.utils.xp_utils import (
    get_user_xp_message, 
    parse_xp_content,
    make_xp_content,
    calculate_level
)

from bot.utils.xp_utils import LEVEL_ROLES, DOUBLE_XP_ROLES, LEVEL_MESSAGES, XP_CHANNEL_ID, MODLOG_CHANNEL_ID
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.antinuke import cooldown

from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.xp_utils import (
    get_user_xp_message,
    parse_xp_content,
    make_xp_content,
    calculate_level
)

def start_moderation_loops():
    asyncio.create_task(tarkista_puhekanavat())

load_dotenv()
XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))

load_dotenv()    
IGNORED_VOICE_CHANNEL_ID = int(os.getenv("IGNORED_VOICE_CHANNEL_ID", 0))

from discord.ext import tasks

@tasks.loop(seconds=60)
async def tarkista_puhekanavat():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if vc.id == IGNORED_VOICE_CHANNEL_ID:
                continue

            for member in vc.members:
                if member.bot:
                    continue

                user_id = str(member.id)
                xp_channel = guild.get_channel(XP_CHANNEL_ID)
                if not xp_channel:
                    continue

                msg = await get_user_xp_message(xp_channel, user_id)
                xp, level = parse_xp_content(msg.content if msg else f"{user_id}:0:0")

                xp_gain = 10
                if any(role.id in DOUBLE_XP_ROLES for role in member.roles):
                    xp_gain *= 2

                xp += xp_gain
                new_level = calculate_level(xp)

                content = make_xp_content(user_id, xp, new_level)
                if msg:
                    await msg.edit(content=content)
                else:
                    await xp_channel.send(content)

                if new_level > level:
                    kanava = vc.guild.system_channel or vc  
                    if new_level in LEVEL_MESSAGES:
                        await kanava.send(LEVEL_MESSAGES[new_level].format(user=member.mention))
                    else:
                        await kanava.send(f"{member.mention} nousi tasolle {new_level}! 🎉")

                    if new_level in LEVEL_ROLES:
                        uusi_rooli = guild.get_role(LEVEL_ROLES[new_level])
                        if uusi_rooli:
                            for lvl, role_id in LEVEL_ROLES.items():
                                if lvl < new_level and any(r.id == role_id for r in member.roles):
                                    vanha = guild.get_role(role_id)
                                    if vanha:
                                        await member.remove_roles(vanha)
                            await member.add_roles(uusi_rooli) 

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @app_commands.command(name="taso", description="Näytä oma tasosi tai Top-10 lista.")
    @app_commands.describe(vaihtoehto="Oma taso tai kaikkien tasot")
    @cooldown("taso")
    @app_commands.choices(vaihtoehto=[
        app_commands.Choice(name="Oma taso", value="oma"),
        app_commands.Choice(name="Kaikkien tasot", value="kaikki")
    ])
    @app_commands.checks.has_role("24G")
    async def taso(self, interaction: discord.Interaction, vaihtoehto: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/taso")
        kirjaa_ga_event(interaction.user.id, "taso_komento")

        if XP_CHANNEL_ID == 0:
            await interaction.followup.send("XP-kanavaa ei asetettu.", ephemeral=True)
            return

        xp_channel = interaction.guild.get_channel(XP_CHANNEL_ID)
        if not xp_channel:
            await interaction.followup.send("XP-kanavaa ei löytynyt.", ephemeral=True)
            return

        if vaihtoehto.value == "oma":
            user_id = str(interaction.user.id)
            msg = await get_user_xp_message(xp_channel, user_id)
            xp, level = parse_xp_content(msg.content if msg else f"{user_id}:0:0")
            await interaction.followup.send(f"Sinulla on {xp} XP:tä ja olet tasolla {level}.", ephemeral=True)

        elif vaihtoehto.value == "kaikki":
            mestari = discord.utils.get(interaction.guild.roles, name="Mestari")
            if mestari not in interaction.user.roles:
                await interaction.followup.send("Vain Mestari-roolilla voi tarkastella kaikkien tasoja.", ephemeral=True)
                return

            users = []
            async for msg in xp_channel.history(limit=1000):
                if msg.author != self.bot.user:
                    continue
                try:
                    user_id, xp, level = msg.content.split(":")
                    member = await interaction.guild.fetch_member(int(user_id))
                    users.append((member.display_name, int(xp), int(level)))
                except:
                    continue

            if not users:
                await interaction.followup.send("Ei löytynyt tasotietoja.", ephemeral=True)
                return

            users.sort(key=lambda x: x[1], reverse=True)
            lines = [f"**{name}** – Taso {level} ({xp} XP)" for name, xp, level in users[:10]]
            await interaction.followup.send("Top 10 jäsenet:\n" + "\n".join(lines), ephemeral=True)
 
    
    @app_commands.command(name="lisää_xp", description="Lisää käyttäjälle XP:tä.")
    @app_commands.describe(jäsen="Jäsen", määrä="Lisättävä XP määrä")
    @cooldown("lisää_xp")
    @app_commands.checks.has_role("Mestari")
    async def lisää_xp(self, interaction: discord.Interaction, jäsen: discord.Member, määrä: int):
        await kirjaa_komento_lokiin(self.bot, interaction, "/lisää_xp")
        kirjaa_ga_event(interaction.user.id, "lisää_xp_komento")

        if XP_CHANNEL_ID == 0:
            await interaction.response.send_message("XP-kanavaa ei asetettu.", ephemeral=True)
            return

        xp_channel = interaction.guild.get_channel(XP_CHANNEL_ID)
        user_id = str(jäsen.id)
        msg = await get_user_xp_message(xp_channel, user_id)
        xp, level = parse_xp_content(msg.content if msg else f"{user_id}:0:0")
        xp += määrä
        new_level = calculate_level(xp)
        content = make_xp_content(user_id, xp, new_level)

        if msg:
            await msg.edit(content=content)
        else:
            await xp_channel.send(content)

        await interaction.response.send_message(f"Lisättiin {määrä} XP:tä käyttäjälle {jäsen.display_name}.", ephemeral=True)

    
    @app_commands.command(name="vähennä_xp", description="Vähennä käyttäjältä XP:tä.")
    @app_commands.describe(jäsen="Jäsen", määrä="Vähennettävä XP määrä")
    @cooldown("vähennä_xp")
    @app_commands.checks.has_role("Mestari")
    async def vähennä_xp(self, interaction: discord.Interaction, jäsen: discord.Member, määrä: int):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vähennä_xp")
        kirjaa_ga_event(interaction.user.id, "vähennä_xp_komento")

        if XP_CHANNEL_ID == 0:
            await interaction.response.send_message("XP-kanavaa ei asetettu.", ephemeral=True)
            return

        xp_channel = interaction.guild.get_channel(XP_CHANNEL_ID)
        user_id = str(jäsen.id)
        msg = await get_user_xp_message(xp_channel, user_id)
        xp, level = parse_xp_content(msg.content if msg else f"{user_id}:0:0")
        xp = max(0, xp - määrä)
        new_level = calculate_level(xp)
        content = make_xp_content(user_id, xp, new_level)

        if msg:
            await msg.edit(content=content)
        else:
            await xp_channel.send(content)

        await interaction.response.send_message(f"Vähennettiin {määrä} XP:tä käyttäjältä {jäsen.display_name}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Levels(bot)
    await bot.add_cog(cog)