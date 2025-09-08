import discord
from discord.ext import commands, tasks
from datetime import datetime, time
from bot.utils.bot_setup import bot
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
ROLE_24G_ID = int(os.getenv("ROLE_24G_ID"))
ROLE_VIP_ID = int(os.getenv("ROLE_VIP_ID"))
CONSOLE_LOG = int(os.getenv("CONSOLE_LOG"))

CHANNEL_IDS_RESTRICTED = [
    int(os.getenv("KANAVA_1ID")),
    int(os.getenv("KANAVA_2ID"))
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
        guild = self.bot.get_guild(GUILD_ID)
        if guild:
            channel = guild.get_channel(CONSOLE_LOG)
            if channel:
                await channel.send("🕒 Yörajoitustoiminto käynnistetty – tarkistetaan tilaa minuutin välein.")
        await self.check_restrictions()

    async def update_channel_visibility(self, guild: discord.Guild, in_restriction: bool):
        role_24g = guild.get_role(ROLE_24G_ID)
        role_vip = guild.get_role(ROLE_VIP_ID)

        restricted_permissions = {
            'send_messages': not in_restriction,
            'send_messages_in_threads': not in_restriction,
            'create_public_threads': not in_restriction,
            'create_private_threads': not in_restriction,
            'add_reactions': not in_restriction,
            'connect': not in_restriction
        }

        for channel_id in CHANNEL_IDS_RESTRICTED:
            channel = guild.get_channel(channel_id)
            if channel:
                overwrites = channel.overwrites

                for role in [role_24g, role_vip]:
                    if role:
                        current = overwrites.get(role, discord.PermissionOverwrite())
                        for perm, value in restricted_permissions.items():
                            setattr(current, perm, value)
                        overwrites[role] = current

                await channel.edit(overwrites=overwrites)

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

async def setup(bot: commands.Bot):
    await bot.add_cog(NightVisibilityCog(bot))