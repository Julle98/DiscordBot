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
CONSOLE_LOG = int(os.getenv("CONSOLE_LOG"))

CATEGORY_IDS_LIMITED = [
    int(os.getenv("CATEGORY_LIMITED_1")),
    int(os.getenv("CATEGORY_LIMITED_2")),
    int(os.getenv("CATEGORY_LIMITED_3")),
    int(os.getenv("CATEGORY_LIMITED_4"))
]

CATEGORY_ID_VIP_HIDE = int(os.getenv("CATEGORY_VIP_HIDE"))

CHANNEL_ID_NIGHT_ONLY = int(os.getenv("CHANNEL_NIGHT_ONLY"))

TASO_ROLE_IDS = [
    int(os.getenv("ROLE_TASO_1")),
    int(os.getenv("ROLE_TASO_5")),
    int(os.getenv("ROLE_TASO_10")),
    int(os.getenv("ROLE_TASO_15")),
    int(os.getenv("ROLE_TASO_25")),
    int(os.getenv("ROLE_TASO_50"))
]

class NightVisibilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.restriction_active = None
        self.check_restrictions.start()

    @tasks.loop(minutes=1)
    async def check_restrictions(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        tz = pytz.timezone("Europe/Helsinki")
        now = datetime.now(tz)
        weekday = now.weekday()

        is_weekend = (
            weekday == 4 and now.hour >= 23 or  
            weekday == 5 or                     
            (weekday == 6 and now.hour < 8)     
        )

        if is_weekend:
            start = time(0, 30)
            end = time(8, 30)
        else:
            start = time(23, 0)
            end = time(7, 0)

        in_restriction = self.is_time_between(start, end, now.time())

        if in_restriction != self.restriction_active:
            self.restriction_active = in_restriction
            await self.update_channel_visibility(guild, in_restriction)
            await self.log_status(guild, in_restriction, now)

    @check_restrictions.before_loop
    async def before_check_restrictions(self):
        await self.bot.wait_until_ready()
        await self.check_restrictions()

    async def update_channel_visibility(self, guild: discord.Guild, in_restriction: bool):
        role_24g = guild.get_role(ROLE_24G_ID)
        role_vip = guild.get_role(ROLE_VIP_ID)
        everyone = guild.default_role

        for cat_id in CATEGORY_IDS_LIMITED:
            category = guild.get_channel(cat_id)
            if category:
                overwrites = category.overwrites
                if role_24g:
                    overwrites[role_24g] = discord.PermissionOverwrite(view_channel=not in_restriction)
                if role_vip:
                    overwrites[role_vip] = discord.PermissionOverwrite(view_channel=not in_restriction)
                await category.edit(overwrites=overwrites)

        vip_category = guild.get_channel(CATEGORY_ID_VIP_HIDE)
        if vip_category:
            overwrites = vip_category.overwrites
            for role_id in [ROLE_VIP_ID] + TASO_ROLE_IDS:
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=not in_restriction)
            await vip_category.edit(overwrites=overwrites)

        night_channel = guild.get_channel(CHANNEL_ID_NIGHT_ONLY)
        if night_channel:
            overwrites = {
                everyone: discord.PermissionOverwrite(view_channel=False),
                role_24g: discord.PermissionOverwrite(view_channel=in_restriction),
                role_vip: discord.PermissionOverwrite(view_channel=in_restriction)
            }
            await night_channel.edit(overwrites=overwrites)

    async def log_status(self, guild: discord.Guild, in_restriction: bool, now: datetime):
        channel = guild.get_channel(CONSOLE_LOG)
        if channel:
            status = "⛔ Rajoitukset päällä" if in_restriction else "✅ Rajoitukset poistettu"
            await channel.send(f"{status} ({now.strftime('%H:%M')})")

    def is_time_between(self, start: time, end: time, check: time):
        if start < end:
            return start <= check <= end
        else:
            return check >= start or check <= end
        
    @check_restrictions.before_loop
    async def before_check_restrictions(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(NightVisibilityCog(bot))