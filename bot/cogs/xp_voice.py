import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import discord
from discord.ext import commands, tasks
from bot.utils.XPstorage import XPStorage

from bot.utils.xp_utils import (
    load_xp_data,
    save_xp_data,
    calculate_level,
    tarkista_tasonousu,
    paivita_streak,
    DOUBLE_XP_ROLES
)

XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))
IGNORED_VOICE_CHANNEL_ID = int(os.getenv("IGNORED_VOICE_CHANNEL_ID", 0))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
XP_VOICE_DATA_PATH = Path(os.getenv("XP_VOICE_DATA_PATH"))

xp_storage = XPStorage(XP_JSON_PATH, XP_VOICE_DATA_PATH)

class XPVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_activity_data = xp_storage.load_voice_activity()
        self.voice_states = {}
        self.xp_voice_loop.start()

    def cog_unload(self):
        self.xp_voice_loop.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        user_id = str(member.id)
        timestamp_now = datetime.utcnow().timestamp()
        guild = member.guild
        channel = guild.get_channel(XP_CHANNEL_ID)

        def handle_flag(flag_name, activity_start, activity_end):
            state_key = f"{user_id}_{flag_name}"
            before_val = getattr(before, flag_name)
            after_val = getattr(after, flag_name)

            if after_val and not before_val:
                self.voice_activity_data["temporary_flags"][state_key] = timestamp_now
                return f"@{member.display_name} {activity_start}"

            elif not after_val and before_val:
                start_time = self.voice_activity_data["temporary_flags"].get(state_key)
                if start_time:
                    duration = int(timestamp_now - start_time)
                    return f"@{member.display_name} {activity_end}. Kokonaisaika {str(timedelta(seconds=duration))}"
            return None

        msg = handle_flag("self_mute", "mykisti itsensä", "lopetti mykistyksen")
        if not msg:
            msg = handle_flag("self_stream", "aloitti näytön jaon", "lopetti näytön jaon")

        if after.channel == guild.afk_channel and before.channel != guild.afk_channel:
            msg = f"@{member.display_name} siirtyi AFK-tilaan 😴"
        elif before.channel == guild.afk_channel and after.channel != guild.afk_channel:
            msg = f"@{member.display_name} palasi aktiiviseksi 🎉"

        if msg and channel:
            await channel.send(msg)

    @tasks.loop(seconds=60)
    async def xp_voice_loop(self):
        xp_data = load_xp_data()

        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                if vc.id == IGNORED_VOICE_CHANNEL_ID or vc == guild.afk_channel:
                    continue  

                for member in vc.members:
                    if member.bot or not member.voice:
                        continue

                    user_id = str(member.id)
                    curr_state = {
                        "muted": member.voice.self_mute or member.voice.mute,
                        "streaming": member.voice.self_stream
                    }

                    user_info = xp_data.get(user_id, {"xp": 0, "level": 0})
                    xp_gain = 10

                    if any(role.id in DOUBLE_XP_ROLES for role in member.roles):
                        xp_gain *= 2
                    if curr_state["muted"]:
                        xp_gain *= 0.5
                    if curr_state["streaming"]:
                        xp_gain *= 1.5

                    user_info["xp"] += int(xp_gain)
                    new_level = calculate_level(user_info["xp"])

                    if new_level > user_info["level"]:
                        channel = guild.get_channel(XP_CHANNEL_ID)
                        if channel:
                            dummy_message = type("DummyMessage", (), {
                                "author": member,
                                "guild": guild,
                                "channel": channel
                            })()
                            await tarkista_tasonousu(self.bot, dummy_message, user_info["level"], new_level)

                    user_info["level"] = new_level
                    xp_data[user_id] = user_info
                    await paivita_streak(int(user_id))

        xp_storage.save_voice_activity(self.voice_activity_data)
        save_xp_data(xp_data)

async def setup(bot):
    await bot.add_cog(XPVoice(bot))