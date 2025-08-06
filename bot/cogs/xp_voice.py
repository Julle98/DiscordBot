import discord
from discord.ext import tasks, commands
import os, json
from datetime import datetime, timedelta
from pathlib import Path

from bot.utils.xp_utils import (
    make_xp_content,
    calculate_level,
    load_xp_data,
    save_xp_data,
    LEVEL_ROLES,
    LEVEL_MESSAGES,
    DOUBLE_XP_ROLES,
    tarkista_tasonousu
)

XP_CHANNEL_ID = int(os.getenv("XP_CHANNEL_ID", 0))
IGNORED_VOICE_CHANNEL_ID = int(os.getenv("IGNORED_VOICE_CHANNEL_ID", 0))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH", "voice_activity.json"))

class XPVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_activity_data = self.load_voice_activity()
        self.voice_states = {}
        self.xp_voice_loop.start()
        self.cleanup_flags.start()

    def cog_unload(self):
        self.xp_voice_loop.cancel()
        self.cleanup_flags.cancel()

    def load_voice_activity(self):
        if XP_JSON_PATH.exists():
            with open(XP_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"total_voice_usage": {}, "temporary_flags": {}}

    def save_voice_activity(self, data):
        XP_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(XP_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @tasks.loop(seconds=60)
    async def xp_voice_loop(self):
        xp_data = load_xp_data()

        for guild in self.bot.guilds:
            channels = await guild.fetch_channels()
            for vc in channels:
                if not isinstance(vc, discord.VoiceChannel) or vc.id == IGNORED_VOICE_CHANNEL_ID:
                    continue

                for member in vc.members:
                    if member.bot:
                        continue

                    user_id = str(member.id)
                    prev_state = self.voice_states.get(user_id, {})
                    curr_state = {
                        "muted": member.voice.self_mute or member.voice.mute,
                        "streaming": member.voice.self_stream,
                        "speaking": not (member.voice.self_mute or member.voice.mute)
                    }

                    for key, status in curr_state.items():
                        state_key = f"{user_id}_{key}"
                        timestamp_now = datetime.utcnow().timestamp()

                        if status and not prev_state.get(key):
                            self.voice_activity_data["temporary_flags"][state_key] = timestamp_now
                            activity = {
                                "muted": "mykisti itsensä",
                                "streaming": "aloitti näytön jaon",
                                "speaking": "aloitti keskustelun"
                            }[key]
                            msg = f"@{member.display_name} {activity} #{vc.name} kanavalla."

                        elif not status and prev_state.get(key):
                            start_time = self.voice_activity_data["temporary_flags"].get(state_key)
                            if start_time:
                                duration = int(timestamp_now - start_time)
                                activity = {
                                    "muted": "lopetti mykistyksen",
                                    "streaming": "lopetti näytön jaon",
                                    "speaking": "lopetti puhumisen"
                                }[key]
                                msg = f"@{member.display_name} {activity} #{vc.name} kanavalla. Kokonaisaika {str(timedelta(seconds=duration))}"

                                if key == "speaking":
                                    total = self.voice_activity_data["total_voice_usage"].get(user_id, 0)
                                    self.voice_activity_data["total_voice_usage"][user_id] = total + duration

                                self.voice_activity_data["temporary_flags"].pop(state_key, None)
                            else:
                                continue

                        channel = guild.get_channel(XP_CHANNEL_ID)
                        if channel and "msg" in locals():
                            await channel.send(msg)
                            msg = None

                    self.voice_states[user_id] = curr_state

                    # XP-laskenta
                    user_info = xp_data.get(user_id, {"xp": 0, "level": 0})
                    xp = user_info["xp"]
                    prev_level = user_info["level"]

                    xp_gain = 10
                    if any(role.id in DOUBLE_XP_ROLES for role in member.roles):
                        xp_gain *= 2
                    if curr_state["muted"]:
                        xp_gain *= 0.5
                    if curr_state["streaming"]:
                        xp_gain *= 1.5

                    xp += int(xp_gain)
                    new_level = calculate_level(xp)
                    make_xp_content(user_id, xp, new_level)

                    # Tasonnousun tarkastus + roolien päivitys + ilmoitus
                    channel = guild.get_channel(XP_CHANNEL_ID)
                    if channel:
                        dummy_message = type("DummyMessage", (), {
                            "author": member,
                            "guild": guild,
                            "channel": channel
                        })()
                        await tarkista_tasonousu(self.bot, dummy_message, prev_level, new_level)

        self.save_voice_activity(self.voice_activity_data)

    @tasks.loop(hours=24)
    async def cleanup_flags(self):
        self.voice_activity_data["temporary_flags"] = {}
        self.save_voice_activity(self.voice_activity_data)
        print("✅ Tilapäiset puhetilatiedot tyhjennetty")

async def setup(bot):
    await bot.add_cog(XPVoice(bot))