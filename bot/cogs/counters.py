import os
from datetime import date, datetime, UTC
from typing import Optional, Tuple, List
import discord
from discord.ext import commands, tasks

def split_prefix(name: str) -> str:
    return name.split(":", 1)[0].strip() if ":" in name else name.strip()

def _as_date(year: int, md: Tuple[int, int]) -> date:
    m, d = md
    return date(year, m, d)

def _in_range(today: date, start: date, end: date) -> bool:
    return start <= today <= end

def _next_occurrence_for_range(today: date, start_md: Tuple[int, int], end_md: Tuple[int, int]):
    start_this = _as_date(today.year, start_md)
    end_this = _as_date(today.year, end_md)

    if end_this < start_this:
        end_this = _as_date(today.year + 1, end_md)

    if today > end_this:
        start_next = _as_date(today.year + 1, start_md)
        end_next = _as_date(today.year + 1, end_md)
        if end_next < start_next:
            end_next = _as_date(today.year + 2, end_md)
        return start_next, end_next

    return start_this, end_this

class Counters(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.guild_id = int(os.getenv("GUILD_ID", "0") or "0")
        self.member_vc_id = int(os.getenv("MEMBER_COUNT_VC_ID", "0") or "0")
        self.bot_vc_id = int(os.getenv("BOT_COUNT_VC_ID", "0") or "0")
        self.holiday_vc_id = int(os.getenv("NEXT_HOLIDAY_VC_ID", "0") or "0")

        self.holidays: List[Tuple[str, Tuple[int, int], Tuple[int, int]]] = [
            ("Uudenvuodenpäivä", (1, 1), (1, 1)),
            ("Loppiainen", (1, 6), (1, 6)),
            ("Pitkäperjantai", (4, 18), (4, 18)),    
            ("Pääsiäispäivä", (4, 20), (4, 20)),     
            ("Toinen pääsiäispäivä", (4, 21), (4, 21)),
            ("Vapunpäivä", (5, 1), (5, 1)),
            ("Helluntaipäivä", (5, 18), (5, 18)),    
            ("Juhannuspäivä", (6, 21), (6, 21)),     
            ("Pyhäinpäivä", (11, 1), (11, 1)),        
            ("Itsenäisyyspäivä", (12, 6), (12, 6)),
            ("Joulupäivä", (12, 25), (12, 25)),
            ("Tapaninpäivä", (12, 26), (12, 26)),
            ("Syysloma", (10, 13), (10, 17)),         
            ("Joululoma", (12, 22), (1, 6)),         
            ("Talviloma", (2, 16), (2, 20)),          
        ]

        self.update_counters.start()

    def cog_unload(self):
        self.update_counters.cancel()

    def _get_guild(self) -> Optional[discord.Guild]:
        if self.guild_id:
            return self.bot.get_guild(self.guild_id)
        return self.bot.guilds[0] if self.bot.guilds else None

    async def _rename_voice_channel(self, channel_id: int, new_suffix: str) -> None:
        if not channel_id:
            return
        ch = self.bot.get_channel(channel_id)
        if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            return

        prefix = split_prefix(ch.name)
        new_name = f"{prefix}: {new_suffix}"

        if ch.name != new_name:
            try:
                await ch.edit(name=new_name, reason="Auto counters päivitys")
            except (discord.Forbidden, discord.HTTPException):
                pass

    def _holiday_status_text(self) -> str:
        today = datetime.now(UTC).date()

        for name, start_md, end_md in self.holidays:
            start_dt, end_dt = _next_occurrence_for_range(today, start_md, end_md)

            prev_start = _as_date(today.year - 1, start_md)
            prev_end = _as_date(today.year - 1, end_md)
            if prev_end < prev_start:
                prev_end = _as_date(today.year, end_md)

            if _in_range(today, prev_start, prev_end) or _in_range(today, start_dt, end_dt):
                return f"{name} käynnissä!"

        candidates = []
        for name, start_md, end_md in self.holidays:
            start_dt, end_dt = _next_occurrence_for_range(today, start_md, end_md)
            if start_dt < today:
                start_dt, end_dt = _next_occurrence_for_range(today.replace(year=today.year + 1), start_md, end_md)
            candidates.append((start_dt, name))

        next_start, next_name = min(candidates, key=lambda x: x[0])
        days = (next_start - today).days

        if days == 0:
            return f"{next_name} (tänään)"
        if days == 1:
            return f"{next_name} (1 pv)"
        return f"{next_name} ({days} pv)"

    @tasks.loop(minutes=60)
    async def update_counters(self):
        guild = self._get_guild()
        if not guild:
            return

        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)

        await self._rename_voice_channel(self.member_vc_id, str(humans))
        await self._rename_voice_channel(self.bot_vc_id, str(bots))
        await self._rename_voice_channel(self.holiday_vc_id, self._holiday_status_text())

    @update_counters.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Counters(bot))