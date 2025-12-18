import os
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections import Counter
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import random
from bot.utils.bot_setup import bot
from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

load_dotenv()

JSON_DIR = Path(os.getenv("XP_JSON_PATH"))
XP_JSON_PATH = Path(os.getenv("XP_JSON_PATH"))
ACHIEVEMENTS_PATH = JSON_DIR / "achievements.json"

TASK_DATA_CHANNEL_ID = int(os.getenv("TASK_DATA_CHANNEL_ID", 0))
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))
MUTE_CHANNEL_ID = int(os.getenv("MUTE_CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))

VOICE_DATA_PATH = Path(
    os.getenv("XP_VOICE_DATA_FILE") or os.getenv("XP_VOICE_DATA_PATH", "")
) if (os.getenv("XP_VOICE_DATA_FILE") or os.getenv("XP_VOICE_DATA_PATH")) else None

STREAKS_PATH = JSON_DIR / "streaks.json"
PUHE_STREAK_PATH = XP_JSON_PATH / "users_streak.json"
XP_DATA_PATH = XP_JSON_PATH / "users_xp.json"

REQUIRED_COMMANDS = ["tehtävät", "kauppa", "asetukset", "tiedot"]

def load_json(path: Path, default):
    try:
        if path and path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Saavutukset] JSON-lukuvirhe {path}: {e}")
    return default

def hae_xp_ja_taso(uid: str) -> tuple[int, int]:
    data = load_json(XP_DATA_PATH, {})
    user = data.get(uid, {})
    return int(user.get("xp", 0)), int(user.get("level", 0))

async def hae_tehtävien_määrä(user_id: str) -> int:
    channel = bot.get_channel(TASK_DATA_CHANNEL_ID)
    if not channel:
        return 0
    count = 0
    async for msg in channel.history(limit=1000):
        try:
            data = json.loads(msg.content)
            if data.get("type") == "user_task" and str(data.get("user_id")) == user_id:
                count += 1
        except Exception:
            continue
    return count

async def laske_moderointi(member: discord.Member) -> tuple[int, int]:
    warnings = 0
    mutes = 0

    varoituskanava = bot.get_channel(MODLOG_CHANNEL_ID)
    mutekanava = bot.get_channel(MUTE_CHANNEL_ID)

    if isinstance(varoituskanava, discord.TextChannel):
        async for msg in varoituskanava.history(limit=1000):
            if f"ID: {member.id}" in msg.content:
                warnings += 1

    if isinstance(mutekanava, discord.TextChannel):
        async for msg in mutekanava.history(limit=1000):
            if (
                "🔇" in msg.content
                and "Jäähy" in msg.content
                and (
                    member.mention in msg.content
                    or str(member.id) in msg.content
                    or member.name in msg.content
                )
            ):
                mutes += 1

    return warnings, mutes

async def hae_osallistumiset(member: discord.Member) -> int:
    console_log = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not isinstance(console_log, discord.TextChannel):
        return 0

    nimet = [member.display_name, member.name, str(member.id)]
    count = 0

    async for msg in console_log.history(limit=1000):
        content = msg.content
        if any(n in content for n in nimet):
            if any(
                x in content
                for x in ["äänesti", "Arvontaan osallistuminen", "Arvonnan voittaja"]
            ):
                count += 1
    return count

async def hae_komennot(member: discord.Member) -> dict[str, int]:
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not isinstance(log_channel, discord.TextChannel):
        return {}

    counts: Counter[str] = Counter()

    async for msg in log_channel.history(limit=1000):
        if f"({member.id})" not in msg.content:
            continue
        name = None
        if "Komento: `" in msg.content:
            try:
                name = msg.content.split("Komento: `", 1)[1].split("`", 1)[0]
            except Exception:
                name = None
        else:
            import re
            m = re.search(r"Komento:\s*/?([^\n`]+)", msg.content)
            if m:
                name = m.group(1)

        if not name:
            continue

        name = name.strip().lstrip("/").lower()
        counts[name] += 1

    return dict(counts)

def hae_streakit(uid: str) -> tuple[int, int, int]:
    data = load_json(STREAKS_PATH, {})
    user = data.get(uid, {})
    daily = int(user.get("daily", {}).get("streak", 0))
    weekly = int(user.get("weekly", {}).get("streak", 0))
    monthly = int(user.get("monthly", {}).get("streak", 0))
    return daily, weekly, monthly

def hae_puhe_streak(uid: str) -> int:
    data = load_json(PUHE_STREAK_PATH, {})
    puhedata = data.get(uid, {})
    return int(puhedata.get("streak", 0))

def award_achievement_xp(uid: str, amount: int, reason: str):
    data = load_json(XP_DATA_PATH, {})
    user = data.get(uid, {})
    xp = int(user.get("xp", 0)) + amount
    if xp < 0:
        xp = 0
    user["xp"] = xp
    data[uid] = user
    try:
        with open(XP_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Saavutukset] XP-tallennus epäonnistui: {e}")

@dataclass
class AchievementDef:
    id: str
    name: str
    description: str
    category: str
    hidden_until_started: bool

    def is_started(self, stats: dict) -> bool:
        return False

    def is_completed(self, stats: dict) -> bool:
        return False

    def progress_text(self, stats: dict) -> str | None:
        return None

class Jasen7pv(AchievementDef):
    def __init__(self):
        super().__init__(
            id="member_7_days",
            name="Tervetuloa taloon",
            description="Ollut jäsenenä palvelimella 7 päivää putkeen.",
            category="Jäsenyys",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["member_days"] >= 1

    def is_completed(self, stats):
        return stats["member_days"] >= 7

    def progress_text(self, stats):
        return f"{stats['member_days']}/7 päivää"

class Jasen30pv(AchievementDef):
    def __init__(self):
        super().__init__(
            id="member_30_days",
            name="Vakioasiakas",
            description="Ollut jäsenenä palvelimella 30 päivää putkeen.",
            category="Jäsenyys",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["member_days"] >= 7

    def is_completed(self, stats):
        return stats["member_days"] >= 30

    def progress_text(self, stats):
        return f"{stats['member_days']}/30 päivää"

class Jasen90pv(AchievementDef):
    def __init__(self):
        super().__init__(
            id="member_90_days",
            name="Kanta-asiakas",
            description="Ollut jäsenenä palvelimella 90 päivää putkeen.",
            category="Jäsenyys",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["member_days"] >= 30

    def is_completed(self, stats):
        return stats["member_days"] >= 90

    def progress_text(self, stats):
        return f"{stats['member_days']}/90 päivää"

class Jasen180pv(AchievementDef):
    def __init__(self):
        super().__init__(
            id="member_180_days",
            name="Asukas",
            description="Ollut jäsenenä palvelimella 180 päivää putkeen.",
            category="Jäsenyys",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["member_days"] >= 90

    def is_completed(self, stats):
        return stats["member_days"] >= 180

    def progress_text(self, stats):
        return f"{stats['member_days']}/180 päivää"

class Jasen365pv(AchievementDef):
    def __init__(self):
        super().__init__(
            id="member_365_days",
            name="Vakiokasvo",
            description="Ollut jäsenenä palvelimella vuoden putkeen.",
            category="Jäsenyys",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["member_days"] >= 180

    def is_completed(self, stats):
        return stats["member_days"] >= 365

    def progress_text(self, stats):
        return f"{stats['member_days']}/365 päivää"

class XP1000(AchievementDef):
    def __init__(self):
        super().__init__(
            id="xp_1000",
            name="Kokenut",
            description="Kertynyt yhteensä vähintään 1000 XP:tä.",
            category="XP",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["xp"] > 0

    def is_completed(self, stats):
        return stats["xp"] >= 1000

    def progress_text(self, stats):
        return f"{stats['xp']}/1000 XP"

class XP5000(AchievementDef):
    def __init__(self):
        super().__init__(
            id="xp_5000",
            name="Legendojen kerho",
            description="Kertynyt yhteensä vähintään 5000 XP:tä.",
            category="XP",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["xp"] >= 1000

    def is_completed(self, stats):
        return stats["xp"] >= 5000

    def progress_text(self, stats):
        return f"{stats['xp']}/5000 XP"

class XP10000(AchievementDef):
    def __init__(self):
        super().__init__(
            id="xp_10000",
            name="XP-jumala",
            description="Kertynyt yhteensä vähintään 10000 XP:tä.",
            category="XP",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["xp"] >= 5000

    def is_completed(self, stats):
        return stats["xp"] >= 10000

    def progress_text(self, stats):
        return f"{stats['xp']}/10000 XP"

class Tehtava10(AchievementDef):
    def __init__(self):
        super().__init__(
            id="tasks_10",
            name="Ahkera suorittaja",
            description="Suorittanut vähintään 10 tehtävää.",
            category="Tehtävät",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["tasks"] > 0

    def is_completed(self, stats):
        return stats["tasks"] >= 10

    def progress_text(self, stats):
        return f"{stats['tasks']}/10 tehtävää"

class Taso10(AchievementDef):
    def __init__(self):
        super().__init__(
            id="level_10",
            name="Tasonousija",
            description="Saavuttanut vähintään tason 10.",
            category="Taso",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["level"] >= 1

    def is_completed(self, stats):
        return stats["level"] >= 10

    def progress_text(self, stats):
        return f"Taso {stats['level']}/10"

class Rikkoja(AchievementDef):
    def __init__(self):
        super().__init__(
            id="rule_breaker",
            name="Oho...",
            description="Saanut vähintään yhden varoituksen tai jäähyn.",
            category="Moderointi",
            hidden_until_started=False,
        )

    def is_started(self, stats):
        return stats["warnings"] + stats["mutes"] > 0

    def is_completed(self, stats):
        return stats["warnings"] + stats["mutes"] > 0

    def progress_text(self, stats):
        total = stats["warnings"] + stats["mutes"]
        return f"{total} merkintää"

class PuheStreak7(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_streak_7",
            name="Puhekone",
            description="Puhunut puhekanavilla 7 päivää putkeen.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_streak"] > 0

    def is_completed(self, stats):
        return stats["voice_streak"] >= 7

    def progress_text(self, stats):
        return f"{stats['voice_streak']}/7 päivää"

class PuheStreak30(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_streak_30",
            name="Puhemestari",
            description="Puhunut puhekanavilla 30 päivää putkeen.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_streak"] >= 7

    def is_completed(self, stats):
        return stats["voice_streak"] >= 30

    def progress_text(self, stats):
        return f"{stats['voice_streak']}/30 päivää"

class VoiceTime1h(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_time_1h",
            name="Ensimmäinen tunti",
            description="Ollut puhekanavilla yhteensä vähintään 1 tunnin.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_seconds"] > 0

    def is_completed(self, stats):
        return stats["voice_seconds"] >= 3600

    def progress_text(self, stats):
        return f"{stats['voice_seconds'] // 60} / 60 minuuttia"

class VoiceTime10h(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_time_10h",
            name="Juttuseura",
            description="Ollut puhekanavilla yhteensä vähintään 10 tuntia.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_seconds"] >= 3600

    def is_completed(self, stats):
        return stats["voice_seconds"] >= 36000

    def progress_text(self, stats):
        return f"{stats['voice_seconds'] // 3600} / 10 tuntia"

class VoiceTime50h(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_time_50h",
            name="Puhelegendä",
            description="Ollut puhekanavilla yhteensä vähintään 50 tuntia.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_seconds"] >= 36000

    def is_completed(self, stats):
        return stats["voice_seconds"] >= 180000

    def progress_text(self, stats):
        return f"{stats['voice_seconds'] // 3600} / 50 tuntia"

class VoiceTime100h(AchievementDef):
    def __init__(self):
        super().__init__(
            id="voice_time_100h",
            name="Puheikoni",
            description="Ollut puhekanavilla yhteensä vähintään 100 tuntia.",
            category="Puhe",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["voice_seconds"] >= 180000

    def is_completed(self, stats):
        return stats["voice_seconds"] >= 360000

    def progress_text(self, stats):
        return f"{stats['voice_seconds'] // 3600} / 100 tuntia"

class CommandOnce(AchievementDef):
    def __init__(self, cmd_name: str, ach_id: str, nice_name: str, desc: str):
        super().__init__(
            id=ach_id,
            name=nice_name,
            description=desc,
            category="Komennot",
            hidden_until_started=True,
        )
        self.cmd_name = cmd_name

    def is_started(self, stats):
        return stats["commands"].get(self.cmd_name, 0) > 0

    def is_completed(self, stats):
        return stats["commands"].get(self.cmd_name, 0) >= 1

    def progress_text(self, stats):
        return f"Käytetty {stats['commands'].get(self.cmd_name, 0)}×"

class AllCommandsOnce(AchievementDef):
    def __init__(self):
        super().__init__(
            id="all_core_commands_once",
            name="Monitoimija",
            description="Käyttänyt komentoja /tehtävät, /kauppa, /asetukset ja /tiedot vähintään kerran.",
            category="Komennot",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return any(stats["commands"].get(c, 0) > 0 for c in REQUIRED_COMMANDS)

    def is_completed(self, stats):
        return all(stats["commands"].get(c, 0) >= 1 for c in REQUIRED_COMMANDS)

    def progress_text(self, stats):
        done = sum(1 for c in REQUIRED_COMMANDS if stats["commands"].get(c, 0) >= 1)
        return f"{done}/{len(REQUIRED_COMMANDS)} komentoa käytetty"

class AfkMoved(AchievementDef):
    def __init__(self):
        super().__init__(
            id="afk_moved",
            name="Zzz...",
            description="Joutunut AFK-kanavalle epäaktiivisuudesta.",
            category="Puhe",
            hidden_until_started=False,
        )

    def is_started(self, stats):
        return stats["afk_moved"]

    def is_completed(self, stats):
        return stats["afk_moved"]

    def progress_text(self, stats):
        return "AFK-kanavalla käyty" if stats["afk_moved"] else None

class StreakReset(AchievementDef):
    def __init__(self):
        super().__init__(
            id="streak_reset",
            name="Uusi alku",
            description="Joutunut aloittamaan streakin alusta jossain kategoriassa.",
            category="Streakit",
            hidden_until_started=False,
        )

    def is_started(self, stats):
        return True  

    def is_completed(self, stats):
        last = stats.get("last_streaks") or {}
        if any(
            last.get(k, 0) > 0 and stats[s_key] == 0
            for k, s_key in [
                ("daily", "daily_streak"),
                ("weekly", "weekly_streak"),
                ("monthly", "monthly_streak"),
                ("voice", "voice_streak"),
            ]
        ):
            return True
        return False

    def progress_text(self, stats):
        return None

class Osallistuja(AchievementDef):
    def __init__(self):
        super().__init__(
            id="participation_5",
            name="Aktiivinen osallistuja",
            description="Osallistunut vähintään 5 eri tapahtumaan / äänestykseen.",
            category="Osallistumiset",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["participations"] > 0

    def is_completed(self, stats):
        return stats["participations"] >= 5

    def progress_text(self, stats):
        return f"{stats['participations']}/5 osallistumista"

class WrappedViewer(AchievementDef):
    def __init__(self):
        super().__init__(
            id="cmd_yhteenveto_once",
            name="Wrapped katsoja",
            description="Käyttänyt komentoa /yhteenveto kerran.",
            category="Komennot",
            hidden_until_started=True,
        )

    def is_started(self, stats):
        return stats["commands"].get("yhteenveto", 0) > 0

    def is_completed(self, stats):
        return stats["commands"].get("yhteenveto", 0) >= 1

    def progress_text(self, stats):
        return f"Käytetty {stats['commands'].get('yhteenveto', 0)}×"

ACHIEVEMENTS: list[AchievementDef] = [
    Jasen7pv(),
    Jasen30pv(),
    Jasen90pv(),
    Jasen180pv(),
    Jasen365pv(),
    XP1000(),
    XP5000(),
    XP10000(),
    Tehtava10(),
    Taso10(),
    Rikkoja(),
    StreakReset(),
    PuheStreak7(),
    PuheStreak30(),
    VoiceTime1h(),
    VoiceTime10h(),
    VoiceTime50h(),
    VoiceTime100h(),
    AfkMoved(),
    Osallistuja(),
    CommandOnce("tehtävät", "cmd_tehtavat_once", "Tehtävälista", "Käyttänyt komentoa /tehtävät kerran."),
    CommandOnce("kauppa", "cmd_kauppa_once", "Shoppailija", "Käyttänyt komentoa /kauppa kerran."),
    CommandOnce("asetukset", "cmd_asetukset_once", "Säätäjä", "Käyttänyt komentoa /asetukset kerran."),
    CommandOnce("tiedot", "cmd_tiedot_once", "Tietäjä", "Käyttänyt komentoa /tiedot kerran."),
    CommandOnce("yhteenveto", "cmd_yhteenveto_once", "Wrapped katsoja", "Käyttänyt komentoa /yhteenveto kerran."),
    AllCommandsOnce(),
    WrappedViewer(),
]

class AchievementsView(ui.View):
    def __init__(
        self,
        cog: "AchievementsCog",
        target: discord.Member,
        statuses: list[dict],
        viewer: discord.Member,
        new_completed_ids: set[str] | None = None,
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.target = target
        self.statuses = statuses
        self.viewer = viewer
        self.new_completed_ids = new_completed_ids or set()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.viewer.id

    @ui.button(label="✅ Näytä avatut", style=discord.ButtonStyle.success)
    async def show_opened(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.cog._build_overview_embed(
            self.target, self.statuses, mode="opened", new_completed_ids=self.new_completed_ids
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔓 Näytä keskeneräiset", style=discord.ButtonStyle.primary)
    async def show_in_progress(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.cog._build_overview_embed(
            self.target, self.statuses, mode="in_progress", new_completed_ids=self.new_completed_ids
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔒 Näytä lukitut", style=discord.ButtonStyle.secondary)
    async def show_locked(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.cog._build_overview_embed(
            self.target, self.statuses, mode="locked", new_completed_ids=self.new_completed_ids
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="💡 Vihje lukituista", style=discord.ButtonStyle.danger)
    async def show_hint(self, interaction: discord.Interaction, button: ui.Button):
        uid = str(self.viewer.id)
        if not self.cog._can_get_hint(uid):
            await interaction.response.send_message(
                "🔒 Olet käyttänyt tämän päivän vihjeet. Yritä uudelleen huomenna!",
                ephemeral=True,
            )
            return

        locked = [s for s in self.statuses if not s["started"] and not s["completed"]]
        if not locked:
            await interaction.response.send_message(
                "✅ Sinulla ei ole lukittuja saavutuksia, joihin voisi antaa vihjeitä.",
                ephemeral=True,
            )
            return

        choice = random.choice(locked)
        ach: AchievementDef = choice["def"]

        self.cog._register_hint(uid)
        embed = discord.Embed(
            title="💡 Vihje lukitusta saavutuksesta",
            description=(
                "Tässä vihje yhdestä lukitusta saavutuksestasi:\n\n"
                f"**Kategoria:** {ach.category}\n"
                f"📜 Kuvaus: *{ach.description}*"
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="Voit saada enintään 2 vihjettä per päivä.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AchievementsCog(commands.Cog):
    def __init__(self, bot_: commands.Bot):
        self.bot = bot_
        ACHIEVEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load_data()

    def _load_data(self):
        return load_json(ACHIEVEMENTS_PATH, {})

    def _save_data(self):
        try:
            with open(ACHIEVEMENTS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Saavutukset] Tallennus epäonnistui: {e}")

    def _get_user_entry(self, uid: str) -> dict:
        entry = self._data.get(uid)
        if not entry:
            entry = {"completed": {}, "last_streaks": {}, "hint_usage": {}}
            self._data[uid] = entry
        else:
            entry.setdefault("completed", {})
            entry.setdefault("last_streaks", {})
            entry.setdefault("hint_usage", {})
        return entry

    def _can_get_hint(self, uid: str) -> bool:
        entry = self._get_user_entry(uid)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        used = int(entry.get("hint_usage", {}).get(today, 0))
        return used < 2

    def _register_hint(self, uid: str):
        entry = self._get_user_entry(uid)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        hints = entry.setdefault("hint_usage", {})
        used = int(hints.get(today, 0))
        hints[today] = used + 1
        self._save_data()

    async def _collect_stats(self, member: discord.Member, entry_last_streaks: dict) -> dict:
        now = discord.utils.utcnow()
        uid = str(member.id)

        member_days = 0
        if member.joined_at:
            member_days = (now - member.joined_at).days

        xp, level = hae_xp_ja_taso(uid)
        tasks = await hae_tehtävien_määrä(uid)
        warnings, mutes = await laske_moderointi(member)
        participations = await hae_osallistumiset(member)
        daily_streak, weekly_streak, monthly_streak = hae_streakit(uid)
        voice_streak = hae_puhe_streak(uid)

        voice_seconds = 0
        afk_moved = False
        if VOICE_DATA_PATH and VOICE_DATA_PATH.exists():
            vdata = load_json(VOICE_DATA_PATH, {})
            total_usage = vdata.get("total_voice_usage", {}).get(uid, 0)
            voice_seconds = int(total_usage)
            voice_channels = vdata.get("voice_channels", {}).get(uid, {})
            afk_channel = member.guild.afk_channel if member.guild else None
            if afk_channel:
                afk_id = str(afk_channel.id)
                if voice_channels.get(afk_id, 0) > 0:
                    afk_moved = True

        commands_map = await hae_komennot(member)

        stats = {
            "member_days": member_days,
            "xp": xp,
            "level": level,
            "tasks": tasks,
            "warnings": warnings,
            "mutes": mutes,
            "participations": participations,
            "daily_streak": daily_streak,
            "weekly_streak": weekly_streak,
            "monthly_streak": monthly_streak,
            "voice_streak": voice_streak,
            "voice_seconds": voice_seconds,
            "afk_moved": afk_moved,
            "commands": commands_map,
            "last_streaks": entry_last_streaks or {},
        }
        return stats

    async def _evaluate_for_user(
        self, member: discord.Member
    ) -> tuple[list[dict], list[AchievementDef]]:
        uid = str(member.id)
        entry = self._get_user_entry(uid)

        stats = await self._collect_stats(member, entry.get("last_streaks"))
        changed = False
        new_completed: list[AchievementDef] = []
        results: list[dict] = []

        for ach in ACHIEVEMENTS:
            started = ach.is_started(stats)
            completed_now = ach.is_completed(stats)
            completed_before = ach.id in entry["completed"]

            completed = completed_before or completed_now
            completed_at = entry["completed"].get(ach.id)

            if completed_now and not completed_before:
                completed_at = datetime.utcnow().isoformat()
                entry["completed"][ach.id] = completed_at
                new_completed.append(ach)
                changed = True

                amount = -20 if ach.id == "rule_breaker" else 20
                award_achievement_xp(uid, amount, f"Saavutus: {ach.name}")

            results.append(
                {
                    "def": ach,
                    "started": started,
                    "completed": completed,
                    "completed_at": completed_at,
                    "progress": ach.progress_text(stats),
                }
            )

        new_last = {
            "daily": stats["daily_streak"],
            "weekly": stats["weekly_streak"],
            "monthly": stats["monthly_streak"],
            "voice": stats["voice_streak"],
        }
        if new_last != entry.get("last_streaks"):
            entry["last_streaks"] = new_last
            changed = True

        if changed:
            self._save_data()

        return results, new_completed

    def _build_help_embed(self, mod: bool) -> discord.Embed:
        if mod:
            title = "📘 Saavutusjärjestelmän ohjeet (modit)"
            desc = "Näin jäsenien saavutusten tarkastelu ja XP-muutokset toimivat:"
        else:
            title = "📘 Saavutusjärjestelmän ohjeet"
            desc = "Näin omien saavutusten tarkastelu ja XP-palkinnot toimivat:"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="🏆 Saavutusten avaaminen",
            value=(
                "• Osa saavutuksista näkyy heti, osa on piilotettuja.\n"
                "• Piilotetut saavutukset avautuvat näkyviin, kun teet niissä edistystä "
                "(esim. alat puhua puhekanavalla tai keräät XP:tä)."
            ),
            inline=False,
        )
        embed.add_field(
            name="✨ XP-palkinnot",
            value=(
                "• Jokaisesta suoritetusta saavutuksesta saat **+20 XP**.\n"
                "• Poikkeus: sääntöjä rikkova **Rikkoja**-saavutus antaa **-20 XP**.\n"
                "• XP lisätään samaan XP-järjestelmään, jota käytetään tasoihin."
            ),
            inline=False,
        )
        embed.add_field(
            name="📅 Jäsenyys, puheaika ja streakit",
            value=(
                "• Saat saavutuksia pitkästä jäsenyydestä (päivien määrä palvelimella).\n"
                "• Puhekanavilla vietetty aika ja puhe-streakit tuovat omat saavutuksensa.\n"
                "• Jos streak nollautuu (esim. unohdat tehtävän), voit saada **Uusi alku** -saavutuksen."
            ),
            inline=False,
        )
        if mod:
            embed.add_field(
                name="🧑‍💼 Modien käyttö",
                value=(
                    "• Käytä komentoa `/saavutukset_jäsenet` ja valitse jäsen, jonka tiedot haluat nähdä.\n"
                    "• Komentoa voivat käyttää vain roolin **Mestari** omistavat käyttäjät."
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="🔎 Komennon käyttö",
                value=(
                    "• Käytä komentoa `/saavutukset` nähdäksesi oman edistymisesi.\n"
                    "• Voit lisätä valinnan `ohje: True`, jos haluat lukea nämä ohjeet."
                ),
                inline=False,
            )

        embed.add_field(
            name="⁉️ Lisähuomiot",
            value=(
                "• Järjestelmä yrittää automaattisesti tunnistaa vanhat saavutukset "
                "ensimmäisellä käyttökerralla.\n"
                "• Jos jokin ei täsmää (XP / streakit), ota yhteyttä ylläpitoon."
            ),
            inline=False,
        )
        embed.set_footer(text="Kerää saavutuksia ajan kanssa – ne eivät katoa mihinkään. ☺️")
        return embed

    def _build_overview_embed(
        self,
        target: discord.Member,
        statuses: list[dict],
        mode: str = "all",               
        new_completed_ids: set[str] | None = None, 
    ) -> discord.Embed:
        if new_completed_ids is None:
            new_completed_ids = set()

        if mode == "opened":
            filtered = [s for s in statuses if s["completed"]]
            title_suffix = " – avatut"
        elif mode == "in_progress":
            filtered = [s for s in statuses if s["started"] and not s["completed"]]
            title_suffix = " – keskeneräiset"
        elif mode == "locked":
            filtered = [s for s in statuses if not s["started"] and not s["completed"]]
            title_suffix = " – lukitut"
        else:
            filtered = statuses
            title_suffix = ""

        total = len(statuses)
        completed_count = sum(1 for s in statuses if s["completed"])
        missing = total - completed_count
        new_now = len(new_completed_ids)

        embed = discord.Embed(
            title=f"🏆 Saavutukset – {target.display_name}{title_suffix}",
            color=discord.Color.gold(),
        )
        desc_lines = [
            f"Valmiit: **{completed_count}/{total}**",
            f"Puuttuu vielä: **{missing}**",
        ]
        if new_now > 0:
            desc_lines.append(f"✨ Uusia tällä kertaa: **{new_now}**")
        embed.description = "\n".join(desc_lines)

        by_cat: dict[str, list[dict]] = {}
        for st in filtered:
            ach: AchievementDef = st["def"]
            by_cat.setdefault(ach.category, []).append(st)

        for cat, items in by_cat.items():
            lines = []
            for st in items:
                ach: AchievementDef = st["def"]
                started = st["started"]
                completed = st["completed"]
                progress = st["progress"]

                just_now = ach.id in new_completed_ids

                if ach.hidden_until_started and not started and not completed:
                    name = "??? (piilotettu saavutus)"
                    desc = ""
                else:
                    name = ach.name
                    desc = ach.description

                if completed:
                    icon = "✅"
                elif started:
                    icon = "🔓"
                else:
                    icon = "🔒"

                if just_now:
                    name = f"{name} ✨"

                line = f"{icon} **{name}**"
                if desc:
                    line += f"\n> {desc}"
                if progress:
                    line += f"\n> Edistyminen: *{progress}*"
                lines.append(line)

            if lines:
                embed.add_field(name=f"📂 {cat}", value="\n\n".join(lines), inline=False)

        embed.set_footer(
            text="Piilotetut saavutukset paljastuvat, kun alat edistyä niissä. Jokaisesta saavutuksesta +20 XP (Rikkoja: -20 XP)."
        )
        return embed

    async def _maybe_first_run_embed(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        new_completed: list[AchievementDef],
    ):
        first_run_overall = not bool(self._data)
        if not first_run_overall or not new_completed:
            return

        first_embed = discord.Embed(
            title="🎉 Saavutusjärjestelmä aktivoitu!",
            description=(
                f"Seuraavat saavutukset tunnistettiin heti olemassa olevan datan perusteella käyttäjälle {target.mention}:"
            ),
            color=discord.Color.green(),
        )
        for ach in new_completed:
            xp_change = -20 if ach.id == "rule_breaker" else 20
            first_embed.add_field(
                name=f"🏆 {ach.name}",
                value=f"{ach.description}\nXP-muutos: **{xp_change:+d} XP**",
                inline=False,
            )
        await interaction.followup.send(embed=first_embed, ephemeral=True)

    async def _send_new_achievements_embed(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        new_completed: list[AchievementDef],
        first_run_overall: bool,
    ):
        if not new_completed:
            return

        if first_run_overall:
            title = "🎉 Saavutusjärjestelmä aktivoitu!"
            desc = (
                f"Seuraavat saavutukset tunnistettiin heti olemassa olevan datan perusteella käyttäjälle {target.mention}:"
            )
        else:
            title = "🎉 Uusia saavutuksia avattu!"
            desc = (
                f"Käyttäjälle {target.mention} avautui tämän tarkistuksen aikana uusia saavutuksia:"
            )

        embed = discord.Embed(
            title=title,
            description=desc,
            color=discord.Color.green(),
        )

        for ach in new_completed:
            xp_change = -20 if ach.id == "rule_breaker" else 20
            embed.add_field(
                name=f"🏆 {ach.name}",
                value=f"{ach.description}\nXP-muutos: **{xp_change:+d} XP**",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="saavutukset", description="Näytä omat saavutukset.")
    @app_commands.describe(ohje="Näytä ohjeet saavutuksista sen sijaan, että näytetään lista.")
    @app_commands.checks.has_role("24G")
    async def saavutukset(
        self,
        interaction: discord.Interaction,
        ohje: bool = False,
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/saavutukset")
        await kirjaa_ga_event(self.bot, interaction.user.id, "saavutukset_komento")
        target = interaction.user

        if ohje:
            embed = self._build_help_embed(mod=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        lataus_embed = discord.Embed(
            title="⏳ Ladataan saavutustietoja...",
            description=(
                "Haetaan tietoja XP-datasta, puheajasta ja lokikanavista.\n"
                "Tämä saattaa kestää hetken ennen kuin etusivu avautuu.\n"
                "Arvioitu odotusaika: 30 sek – 3 min."
            ),
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(embed=lataus_embed, view=None)

        first_run_overall = not bool(self._data)
        statuses, new_completed = await self._evaluate_for_user(target)

        await self._send_new_achievements_embed(
            interaction, target, new_completed, first_run_overall
        )

        new_ids = {a.id for a in new_completed}
        embed = self._build_overview_embed(
            target, statuses, mode="all", new_completed_ids=new_ids
        )
        view = AchievementsView(
            self, target, statuses, viewer=interaction.user, new_completed_ids=new_ids
        )
        await interaction.edit_original_response(embed=embed, view=view)

    @app_commands.command(name="saavutukset_jäsenet", description="Näytä jäsenen saavutukset (vain modeille).")
    @app_commands.describe(
        jäsen="Jäsen, jonka saavutukset näytetään.",
        ohje="Näytä ohjeet saavutuksista sen sijaan, että näytetään lista.",
    )
    @app_commands.checks.has_role("Mestari")
    async def saavutukset_jäsenet(
        self,
        interaction: discord.Interaction,
        jäsen: discord.Member,
        ohje: bool = False,
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/saavutukset_jäsenet")
        await kirjaa_ga_event(self.bot, interaction.user.id, "saavutukset_jäsenet_komento")

        roolit = getattr(interaction.user, "roles", [])
        is_mestari = any(r.name == "Mestari" for r in roolit)
        if not is_mestari:
            await interaction.response.send_message(
                "❌ Tämä komento on vain roolin **Mestari** omaaville.",
                ephemeral=True,
            )
            return

        if ohje:
            embed = self._build_help_embed(mod=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        lataus_embed = discord.Embed(
            title="⏳ Ladataan jäsenen saavutustietoja...",
            description=(
                f"Haetaan tietoja käyttäjälle {jäsen.mention} lokista ja tietokannoista.\n"
                "Tämä saattaa kestää hetken ennen kuin etusivu avautuu.\n"
                "Arvioitu odotusaika: 30 sek – 3 min."
            ),
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(embed=lataus_embed, view=None)

        first_run_overall = not bool(self._data)
        statuses, new_completed = await self._evaluate_for_user(jäsen)

        await self._send_new_achievements_embed(
            interaction, jäsen, new_completed, first_run_overall
        )

        new_ids = {a.id for a in new_completed}
        embed = self._build_overview_embed(
            jäsen, statuses, mode="all", new_completed_ids=new_ids
        )
        view = AchievementsView(
            self, jäsen, statuses, viewer=interaction.user, new_completed_ids=new_ids
        )
        await interaction.edit_original_response(embed=embed, view=view)

async def setup(bot_: commands.Bot):
    await bot_.add_cog(AchievementsCog(bot_))