import discord
from discord.ext import commands, tasks
from datetime import datetime, time
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
ROLE_24G_ID = int(os.getenv("ROLE_24G_ID"))
ROLE_VIP_ID = int(os.getenv("ROLE_VIP_ID"))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))

class NightRestriction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.restriction_active = None
        self.check_restrictions.start()

    def cog_unload(self):
        self.check_restrictions.cancel()

    @tasks.loop(minutes=1)
    async def check_restrictions(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        roles = [guild.get_role(ROLE_24G_ID), guild.get_role(ROLE_VIP_ID)]
        tz = pytz.timezone("Europe/Helsinki")
        now = datetime.now(tz)
        weekday = now.weekday()

        if weekday in [5] or (weekday == 6 and now.hour < 23):  # viikonloppu
            start = time(0, 30)
            end = time(8, 30)
        else:  # arki
            start = time(23, 0)
            end = time(7, 0)

        in_restriction = self.is_time_between(start, end, now.time())

        if in_restriction != self.restriction_active:
            self.restriction_active = in_restriction
            await self.update_roles(roles, in_restriction)
            await self.log_status(guild, in_restriction, now)

    async def update_roles(self, roles: list[discord.Role], in_restriction: bool):
        for role in roles:
            if role is None:
                continue

            perms = role.permissions
            if in_restriction:
                perms.update(
                    send_messages=False,
                    connect=False,
                    add_reactions=False,
                    use_external_emojis=False
                )
            else:
                perms.update(
                    send_messages=True,
                    connect=True,
                    add_reactions=True,
                    use_external_emojis=True
                )

            await role.edit(
                permissions=perms,
                reason="Yön aikainen moderointipuute / palautus"
            )

    async def log_status(self, guild: discord.Guild, in_restriction: bool, now: datetime):
        channel = guild.get_channel(MOD_LOG_CHANNEL_ID)
        if channel:
            role_names = [r.name for r in [guild.get_role(ROLE_24G_ID), guild.get_role(ROLE_VIP_ID)] if r]
            if in_restriction:
                msg = f"⛔ Rajoitukset päällä rooleille {', '.join(role_names)} ({now.strftime('%H:%M')})"
            else:
                msg = f"✅ Rajoitukset poistettu rooleilta {', '.join(role_names)} ({now.strftime('%H:%M')})"
            await channel.send(msg)

    def is_time_between(self, start: time, end: time, check: time):
        if start < end:
            return start <= check <= end
        else:
            return check >= start or check <= end

async def setup(bot: commands.Bot):
    await bot.add_cog(NightRestriction(bot))