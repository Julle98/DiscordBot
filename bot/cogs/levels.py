import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
import asyncio
import os
from dotenv import load_dotenv

from bot.utils.bot_setup import bot
from bot.utils.xp_utils import (
    get_user_xp_message,
    parse_xp_content,
    make_xp_content,
    calculate_level,
    LEVEL_ROLES,
    DOUBLE_XP_ROLES,
    LEVEL_MESSAGES
)
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.xp_utils import load_xp_data, save_xp_data
from bot.utils.error_handler import CommandErrorHandler

load_dotenv()
XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))
IGNORED_VOICE_CHANNEL_ID = int(os.getenv("IGNORED_VOICE_CHANNEL_ID", 0))

from discord.ext import tasks
import discord

import os

@tasks.loop(seconds=60)
async def tarkista_puhekanavat():
    for guild in bot.guilds:
        xp_channel_id = int(os.getenv("XP_CHANNEL_ID"))
        xp_channel = guild.get_channel(xp_channel_id)
        if not xp_channel:
            continue

        channels = await guild.fetch_channels()
        for vc in channels:
            if not isinstance(vc, discord.VoiceChannel):
                continue
            
            if vc.id == IGNORED_VOICE_CHANNEL_ID:
                continue

            for member in vc.members:
                if member.bot:
                    continue

                user_id = str(member.id)

                msg = None
                async for m in xp_channel.history(limit=100):
                    if m.author == bot.user and m.content.startswith(f"{user_id}:"):
                        msg = m
                        break

                xp_str = msg.content if msg else f"{user_id}:0:0"
                xp, level = parse_xp_content(xp_str)

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
                    if new_level in LEVEL_MESSAGES:
                        await xp_channel.send(LEVEL_MESSAGES[new_level].format(user=member.mention))
                    else:
                        await xp_channel.send(f"{member.mention} nousi tasolle {new_level}! 🎉")

                    if new_level in LEVEL_ROLES:
                        uusi_rooli = guild.get_role(LEVEL_ROLES[new_level])
                        if uusi_rooli:
                            for lvl, role_id in LEVEL_ROLES.items():
                                if lvl < new_level and any(r.id == role_id for r in member.roles):
                                    vanha = guild.get_role(role_id)
                                    if vanha:
                                        await member.remove_roles(vanha)
                            await member.add_roles(uusi_rooli)

from discord import app_commands, Interaction
from discord.ext import commands
import discord

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="taso", description="Näytä oma tasosi tai Top-10 lista.")
    @app_commands.describe(vaihtoehto="Oma taso tai kaikkien tasot")
    @app_commands.choices(vaihtoehto=[
        app_commands.Choice(name="Oma taso", value="oma"),
        app_commands.Choice(name="Kaikkien tasot", value="kaikki")
    ])
    @app_commands.checks.has_role("24G")
    async def taso(self, interaction: Interaction, vaihtoehto: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True, ephemeral=True)

        await kirjaa_komento_lokiin(self.bot, interaction, "/taso")
        await kirjaa_ga_event(self.bot, interaction.user.id, "taso_komento")

        xp_data = load_xp_data()

        if vaihtoehto.value == "oma":
            uid = str(interaction.user.id)
            tiedot = xp_data.get(uid, {"xp": 0, "level": 0})
            xp = tiedot["xp"]
            level = tiedot["level"]
            next_level = level + 1
            next_level_xp = (next_level ** 2) * 100
            remaining_xp = max(0, next_level_xp - xp)

            await interaction.followup.send(
                f"Sinulla on {xp} XP:tä ja olet tasolla {level}.\n"
                f"Seuraava taso ({next_level}) vaatii **{next_level_xp} XP** – "
                f"{remaining_xp} XP jäljellä. 🎯",
                ephemeral=True
            )

        elif vaihtoehto.value == "kaikki":
            mestari = discord.utils.get(interaction.guild.roles, name="Mestari")
            if mestari not in interaction.user.roles:
                await interaction.followup.send("Vain Mestari-roolilla voi tarkastella kaikkien tasoja.", ephemeral=True)
                return

            entries = []
            for user_id, tiedot in xp_data.items():
                try:
                    member = await interaction.guild.fetch_member(int(user_id))
                    entries.append((member.display_name, tiedot["xp"], tiedot["level"]))
                except:
                    continue

            if not entries:
                await interaction.followup.send("Ei löytynyt tasotietoja.", ephemeral=True)
                return

            entries.sort(key=lambda x: x[1], reverse=True)
            lines = [f"**{name}** – Taso {lvl} ({xp} XP)" for name, xp, lvl in entries[:10]]

            await interaction.followup.send("Top 10 jäsenet:\n" + "\n".join(lines), ephemeral=True)

    async def hae_tasot(self, xp_channel):
        tulokset = []
        async for msg in xp_channel.history(limit=1000):
            if msg.author != self.bot.user:
                continue
            try:
                user_id, xp, level = msg.content.split(":")
                tulokset.append((user_id, int(xp), int(level)))
            except:
                continue
        return tulokset

    @app_commands.command(name="lisää_xp", description="Lisää käyttäjälle XP:tä.")
    @app_commands.checks.has_role("Mestari")
    @app_commands.describe(jäsen="Jäsen", määrä="Lisättävä XP määrä")
    async def lisää_xp(self, interaction: Interaction, jäsen: discord.Member, määrä: int):
        user_id = str(jäsen.id)
        xp_data = load_xp_data()
        tiedot = xp_data.get(user_id, {"xp": 0, "level": 0})

        tiedot["xp"] += määrä
        tiedot["level"] = calculate_level(tiedot["xp"])

        xp_data[user_id] = tiedot
        save_xp_data(xp_data)

        await interaction.response.send_message(
            f"Lisättiin {määrä} XP:tä käyttäjälle {jäsen.display_name}. Nykyinen XP: {tiedot['xp']}, Taso: {tiedot['level']}",
            ephemeral=True
        )

    @app_commands.command(name="vähennä_xp", description="Vähennä käyttäjältä XP:tä.")
    @app_commands.checks.has_role("Mestari")
    @app_commands.describe(jäsen="Jäsen", määrä="Vähennettävä XP määrä")
    async def vähennä_xp(self, interaction: Interaction, jäsen: discord.Member, määrä: int):
        user_id = str(jäsen.id)
        xp_data = load_xp_data()
        tiedot = xp_data.get(user_id, {"xp": 0, "level": 0})

        tiedot["xp"] = max(0, tiedot["xp"] - määrä)
        tiedot["level"] = calculate_level(tiedot["xp"])

        xp_data[user_id] = tiedot
        save_xp_data(xp_data)

        await interaction.response.send_message(
            f"Vähennettiin {määrä} XP:tä käyttäjältä {jäsen.display_name}. Nykyinen XP: {tiedot['xp']}, Taso: {tiedot['level']}",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    await bot.add_cog(Levels(bot))
