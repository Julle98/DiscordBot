import os
import json
import re
from collections import Counter
from datetime import datetime, timedelta, time
from pathlib import Path
import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.logger import kirjaa_komento_lokiin
from bot.utils.logger import kirjaa_ga_event
from bot.utils.settings_utils import get_user_settings
from bot.cogs.achievements import ACHIEVEMENTS_PATH

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  

from bot.utils.tiedot_utils import (
    TIEDOSTOT,
    XP_JSON_PATH,
    JSON_DIRS,
    hae_tehtäväviestit,
    hae_ostosviestit,
    hae_osallistumisviestit,
    hae_tarjousviestit,
    JäsenToimintaAnalyysi,
)

VUODEN_PÄIVÄT = 365
YHTEENVETO_PATH = XP_JSON_PATH / "yhteenveto.json"
HELSINKI_TZ = ZoneInfo("Europe/Helsinki") if ZoneInfo else None

def xp_kommentti(total_xp: int) -> str:
    if total_xp <= 0:
        return "XP:tä ei ole vielä kertynyt. Kaikki on vielä edessä!"
    if total_xp < 2_000:
        return "XP-määrä on vielä melko pieni. Alkuvaiheessa ollaan."
    if total_xp < 10_000:
        return "XP:tä on kertynyt mukavasti. Aktiivinen, muttei vielä maksimigrindaaja."
    if total_xp < 50_000:
        return "XP:tä on todella paljon. Selvästi yksi palvelimen aktiivisimmista."
    return "XP-taso on aivan massiivinen. Todellinen huippuaktiivi palvelimella."

def varoitus_kommentti(warnings: int) -> str:
    if warnings <= 0:
        return "Moderointimerkintöjä ei ole lainkaan. Maine on täysin puhdas."
    if warnings == 1:
        return "Yksi pieni merkintä. Ei vielä huolestuttavaa, mutta tarkkuus kannattaa."
    if warnings <= 3:
        return "Muutamia merkintöjä. Pientä skarppausta käytökseen voisi tehdä."
    return "Moderointimerkintöjä on kertynyt selvästi. Jatkossa kannattaa olla erityisen tarkkana."

def puhe_kommentti(total_seconds: int) -> str:
    tunnit = total_seconds / 3600 if total_seconds else 0
    if tunnit < 1:
        return "Puhekanavilla ei juuri ole vietetty aikaa."
    if tunnit < 10:
        return "Puhekanavilla on oltu silloin tällöin. Kevyt käyttötaso."
    if tunnit < 50:
        return "Puhekanavia käytetään säännöllisesti! Aktiivinen jutustelija."
    if tunnit < 150:
        return "Puhekanavilla vietetään todella paljon aikaa. Vakioääni porukassa."
    return "Puhekanavat ovat kuin toinen koti. Äänitoiminta on erittäin vilkasta."

def osallistuminen_kommentti(total: int, arvonnat: int, voitot: int, aanestykset: int) -> str:
    if total <= 0:
        return "Et ole vielä osallistunut arvontoihin tai äänestyksiin. Kaikki tilaisuudet ovat vielä edessä!"
    
    if total < 5:
        base = "Muutamia osallistumisia. Käyt kurkkaamassa, mutta et vielä aktiivisesti jahtaa kaikkea."
    elif total < 20:
        base = "Osallistut säännöllisesti. Olet mukana päätöksenteossa ja arvonnoissa ihan kivalla tahdilla."
    elif total < 50:
        base = "Osallistumisia on kertynyt paljon. Olet yksi palvelimen aktiivisemmista osallistujista."
    else:
        base = "Osallistumisia on valtavasti. Olet selvästi yksi palvelimen kovimmista osallistujista!"

    lisä = []
    if arvonnat > 0:
        lisä.append(f"Arvontoihin osallistuttu **{arvonnat}** kertaa.")
    if voitot > 0:
        lisä.append(f"ja voitettu **{voitot}** kertaa. 🎉")
    if aanestykset > 0 and not lisä:
        lisä.append(f"Äänestyksiin osallistuttu **{aanestykset}** kertaa.")

    if lisä:
        return base + " " + " ".join(lisä)
    return base

def tehtava_kommentti(count: int, daily: int, weekly: int, monthly: int) -> str:
    if count <= 0:
        return "Tehtäviä ei ole vielä tehty. Tästä on hyvä aloittaa – ensimmäinen tehtävä odottaa!"

    if count < 10:
        perus = "Muutamia tehtäviä suoritettu. Rauhallinen aloitustahti."
    elif count < 40:
        perus = "Tehtäviä on tehty mukavasti. Olet selvästi mukana tehtävämeiningissä."
    elif count < 100:
        perus = "Tehtäviä on suoritettu paljon. Olet yksi palvelimen aktiivisista tekijöistä."
    else:
        perus = "Tehtäviä on aivan valtava määrä. Olet todellinen tehtäväkone!"

    streak_osuus = []

    if daily > 0:
        streak_osuus.append(f"päivittäinen streak **{daily}**")
    if weekly > 0:
        streak_osuus.append(f"viikoittainen streak **{weekly}**")
    if monthly > 0:
        streak_osuus.append(f"kuukausittainen streak **{monthly}**")

    if streak_osuus:
        return perus + " Lisäksi sinulla on " + ", ".join(streak_osuus) + "."

    return perus

def saavutusten_kategoria(key: str) -> str:
    if key.startswith("member_"):
        return "Jäsenyys"
    if key.startswith("xp_"):
        return "XP"
    if key.startswith("tasks_"):
        return "Tehtävät"
    if key.startswith("level_"):
        return "Tasot"
    if key.startswith("voice_"):
        return "Puhe"
    if key.startswith("participation_"):
        return "Osallistumiset"
    if key.startswith("cmd_") or key == "all_core_commands_once":
        return "Komennot"
    if key == "rule_breaker":
        return "Erikoiset"
    return "Muut"

def saavutukset_kommentti(total_year: int, total_all: int, by_cat_year: dict[str, int]) -> str:
    if total_year <= 0 and total_all <= 0:
        return "Et ole vielä avannut yhtään saavutusta. Kaikki palkinnot ovat vielä edessä!"

    if total_year <= 0 and total_all > 0:
        return (
            f"Olet avannut yhteensä **{total_all}** saavutusta, "
            "mutta et yhtään uutta tänä vuonna. Ehkä tänä vuonna haetaan uusi pokaali? 🏅"
        )

    if total_year < 3:
        perus = f"Tänä vuonna avattu **{total_year}** saavutusta. Rauhallinen keräilytahti."
    elif total_year < 10:
        perus = f"Tänä vuonna avattu **{total_year}** saavutusta. Olet hyvin mukana metsästämässä palkintoja!"
    elif total_year < 25:
        perus = f"Tänä vuonna avattu **{total_year}** saavutusta. Olet selvästi yksi palvelimen aktiivisista keräilijöistä!"
    else:
        perus = f"Tänä vuonna avattu peräti **{total_year}** saavutusta. Todellinen achievement-hirviö! 🔥"

    if by_cat_year:
        suosituin_kat, määrä = max(by_cat_year.items(), key=lambda x: x[1])
        lisä = f" Eniten saavutuksia on tullut kategoriasta **{suosituin_kat}** ({määrä} kpl)."
    else:
        lisä = ""

    kokonais = f" Yhteensä sinulla on avattuna **{total_all}** saavutusta kaikkina aikoina."

    return perus + lisä + kokonais

def ero_str(nyky: int | float, edellinen: int | float | None, yksikkö: str = "") -> str:
    if edellinen is None:
        return "Ei aiempaa yhteenvetoa vertailuun."
    diff = nyky - edellinen
    if diff == 0:
        return "Ei muutosta edelliseen yhteenvetoon."
    etumerkki = "+" if diff > 0 else "−"
    arvo = abs(int(diff))
    return f"Muutos edelliseen yhteenvetoon: **{etumerkki}{arvo} {yksikkö}**."

def is_mestari(member: discord.Member) -> bool:
    roles = getattr(member, "roles", [])
    return any(r.name == "Mestari" for r in roles)

def get_visible_until(year: int) -> datetime:
    env = os.getenv("REWIND_VISIBLE_UNTIL")
    tz = HELSINKI_TZ
    if env:
        try:
            d = datetime.strptime(env, "%Y-%m-%d").date()
            dt = datetime.combine(d, time(23, 59, 59))
            return dt.replace(tzinfo=tz) if tz else dt
        except Exception:
            pass

    dt = datetime(year, 12, 31, 23, 59, 59)
    return dt.replace(tzinfo=tz) if tz else dt

def now_local() -> datetime:
    if HELSINKI_TZ:
        return datetime.now(tz=HELSINKI_TZ)
    return datetime.utcnow()

class YhteenvetoPaginator(discord.ui.View):
    def __init__(self, pages, *, timeout=180):
        super().__init__(timeout=timeout)
        self.pages = pages  
        self.index = 0
        self._update_button_states()

    def _update_button_states(self):
        self.previous_button.disabled = self.index <= 0
        self.next_button.disabled = self.index >= len(self.pages) - 1

    async def _show_page(self, interaction: discord.Interaction):
        nimi, page_fn = self.pages[self.index]

        lataus_embed = discord.Embed(
            title="⏳ Ladataan yhteenvetoa...",
            description=f"Valmistellaan sivua: **{nimi}**\n\n_Tämä voi kestää hetken..._",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=lataus_embed, view=self)

        embed = page_fn()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="⏮️ Edellinen", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            self._update_button_states()
            await self._show_page(interaction)

    @discord.ui.button(label="⏭️ Seuraava", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
            self._update_button_states()
            await self._show_page(interaction)

class YhteenvetoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _period_range(year: int) -> tuple[datetime, datetime]:
        start = datetime(year, 1, 1, 0, 0, 0)
        end = datetime(year, 12, 31, 23, 59, 59)
        return start, end

    @staticmethod
    def _in_range(dt: datetime, start: datetime, end: datetime) -> bool:
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return start <= dt <= end

    def _key(self, year: int, uid: str) -> str:
        return f"{year}:{uid}"

    def _lue_edellinen_yhteenveto(self, year: int, uid: str) -> dict | None:
        try:
            if not YHTEENVETO_PATH.exists():
                return None

            with open(YHTEENVETO_PATH, encoding="utf-8") as f:
                data = json.load(f)

            entry = data.get(self._key(year, uid))
            if not entry:
                return None

            prev_data = entry.get("data")
            last_run_str = entry.get("last_run")

            if not last_run_str:
                return prev_data

            try:
                last_run = datetime.fromisoformat(last_run_str)
            except Exception:
                return prev_data

            now_utc = datetime.utcnow()
            diff = now_utc - last_run

            if diff.days < VUODEN_PÄIVÄT:
                return None

            return prev_data

        except Exception:
            return None

    def _tallenna_yhteenveto(self, year: int, uid: str, current_data: dict):
        try:
            if YHTEENVETO_PATH.exists():
                with open(YHTEENVETO_PATH, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}

            data[self._key(year, uid)] = {
                "last_run": datetime.utcnow().isoformat(),
                "data": current_data,
            }

            YHTEENVETO_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(YHTEENVETO_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Yhteenvedon tallennus epäonnistui: {e}")

    def _loppu_yhteenveto_sivu(
        self,
        user: discord.User,
        year: int,
        stats: dict,
        start: datetime,
        end: datetime
    ) -> tuple[discord.Embed, dict]:
        xp = stats.get("xp", {})
        tasks = stats.get("tasks", {})
        cmds = stats.get("commands", {})
        part = stats.get("participation", {})
        mod = stats.get("moderation", {})
        act = stats.get("activity", {})
        shop = stats.get("shop", {})
        ach = stats.get("achievements", {}) or {}

        top_task = (tasks.get("top_tasks") or [])[0] if (tasks.get("top_tasks") or []) else None
        top_cmd = (cmds.get("top") or [])[0] if (cmds.get("top") or []) else None
        top_prod = (shop.get("top_products") or [])[0] if (shop.get("top_products") or []) else None

        voice_h = (act.get("total_voice_seconds", 0) / 3600) if act.get("total_voice_seconds", 0) else 0

        embed = discord.Embed(
            title=f"🏁 Loppukooste [{year}]",
            description=f"{user.display_name} – tärkeimmät nostot.",
            color=discord.Color.green(),
        )

        total_xp = int(xp.get("total_xp", 0))
        embed.add_field(name="✨ XP", value=f"**{total_xp} XP**", inline=False)
        embed.add_field(name="📘 Tehtävät", value=f"**{int(tasks.get('count', 0))}**", inline=True)
        embed.add_field(name="💬 Komennot", value=f"**{int(cmds.get('total', 0))}**", inline=True)
        embed.add_field(name="📥 Osallistumiset", value=f"**{int(part.get('total', 0))}**", inline=True)
        embed.add_field(name="⚠️ Varoitukset", value=f"**{int(mod.get('warnings', 0))}**", inline=True)
        embed.add_field(name="🔇 Jäähyt", value=f"**{int(mod.get('mutes', 0))}**", inline=True)
        embed.add_field(name="🆘 Help", value=f"**{int(mod.get('help_requests', 0))}**", inline=True)
        embed.add_field(name="🎙️ Puheaika", value=f"**{voice_h:.1f} h**", inline=True)
        embed.add_field(name="🛒 Ostoksia", value=f"**{int(shop.get('purchases_count', 0))}**", inline=True)
        embed.add_field(name="🎟️ Kuponkeja", value=f"**{int(shop.get('coupons_count', 0))}**", inline=True)
        embed.add_field(name="🎁 Tarjouksia", value=f"**{int(shop.get('offers_count', 0))}**", inline=True)
        embed.add_field(name="🏅 Saavutukset", value=f"**{int(ach.get('total_year', 0))}**", inline=True)
        embed.add_field(name="💡 Vihjeet", value=f"**{int(ach.get('hint_usage_total', 0))}**", inline=True)

        if top_task:
            embed.add_field(name="🏆 Top-tehtävä", value=f"**{top_task[0]}** ({top_task[1]}×)", inline=False)
        if top_cmd:
            embed.add_field(name="🏆 Top-komento", value=f"`{top_cmd[0]}` ({top_cmd[1]}×)", inline=False)
        if top_prod:
            embed.add_field(name="🏆 Top-ostos", value=f"**{top_prod[0]}** ({top_prod[1]}×)", inline=False)

        embed.set_footer(text="Voit tallentaa tämän koosteeksi tiedostona 💾")

        period_str = f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"
        txt = (
            f"{user.display_name} Rewind [{year}]\n"
            f"Ajanjakso: {period_str}\n\n"
            f"XP yhteensä: {total_xp}\n"
            f"Tehtäviä: {int(tasks.get('count', 0))}\n"
            f"Komentoja: {int(cmds.get('total', 0))}\n"
            f"Osallistumisia: {int(part.get('total', 0))}\n"
            f"Varoituksia: {int(mod.get('warnings', 0))}\n"
            f"Jäähyjä: {int(mod.get('mutes', 0))}\n"
            f"Help-pyyntöjä: {int(mod.get('help_requests', 0))}\n"
            f"Puheaika (kokonais): {voice_h:.1f} h\n"
            f"Ostoksia: {int(shop.get('purchases_count', 0))}\n"
            f"Kuponkeja: {int(shop.get('coupons_count', 0))}\n"
            f"Tarjouksia: {int(shop.get('offers_count', 0))}\n"
        )

        payload = {
            "text": txt,
            "json": {
                "year": year,
                "user_id": str(user.id),
                "user_name": user.name,
                "period": {"start": start.isoformat(), "end": end.isoformat()},
                "stats": stats,
            },
            "txt_name": f"rewind_{year}_{user.id}.txt",
            "json_name": f"rewind_{year}_{user.id}.json",
        }

        return embed, payload

    class RewindView(discord.ui.View):
        def __init__(self, pages, save_payload: dict | None, *, timeout=180):
            super().__init__(timeout=timeout)
            self.pages = pages  
            self.index = 0
            self.save_payload = save_payload

            self.save_button: discord.ui.Button | None = None
            self._sync_buttons(first=True)

        def _rebuild_save_button(self):
            if self.save_button is not None:
                self.remove_item(self.save_button)
                self.save_button = None

            is_last = self.index == (len(self.pages) - 1)
            if is_last and self.save_payload is not None:
                btn = discord.ui.Button(label="💾 Tallenna kooste", style=discord.ButtonStyle.success)

                async def _cb(interaction: discord.Interaction):
                    import io
                    txt = self.save_payload.get("text", "")
                    js = self.save_payload.get("json", {})

                    txt_bytes = io.BytesIO(txt.encode("utf-8"))
                    json_bytes = io.BytesIO(json.dumps(js, ensure_ascii=False, indent=2).encode("utf-8"))

                    files = [
                        discord.File(fp=txt_bytes, filename=self.save_payload.get("txt_name", "rewind_kooste.txt")),
                        discord.File(fp=json_bytes, filename=self.save_payload.get("json_name", "rewind_kooste.json")),
                    ]
                    await interaction.response.send_message(
                        "Tallennus valmis! Tässä kooste tiedostoina:",
                        files=files,
                        ephemeral=True
                    )

                btn.callback = _cb
                self.save_button = btn
                self.add_item(btn)

        def _sync_buttons(self, *, first: bool = False):
            self.prev_btn.disabled = self.index <= 0
            self.next_btn.disabled = self.index >= len(self.pages) - 1
            self._rebuild_save_button()
            if not first:
                pass

        async def _show(self, interaction: discord.Interaction):
            nimi, fn = self.pages[self.index]
            self._sync_buttons()

            lataus = discord.Embed(
                title="⏳ Ladataan yhteenvetoa...",
                description=f"Valmistellaan sivua: **{nimi}**\n\n_Tämä voi kestää hetken..._",
                color=discord.Color.orange(),
            )
            await interaction.response.edit_message(embed=lataus, view=self)

            embed = fn()
            await interaction.edit_original_response(embed=embed, view=self)

        @discord.ui.button(label="⏮️ Edellinen", style=discord.ButtonStyle.secondary)
        async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.index > 0:
                self.index -= 1
                await self._show(interaction)

        @discord.ui.button(label="⏭️ Seuraava", style=discord.ButtonStyle.primary)
        async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.index < len(self.pages) - 1:
                self.index += 1
                await self._show(interaction)

    async def _kerää_tilastot(self, interaction: discord.Interaction, user: discord.User, year: int) -> dict:
        uid = str(user.id)
        start, end = self._period_range(year)

        stats: dict = {}

        tehtäväviestit = await hae_tehtäväviestit(uid)
        tehtävä_counter = Counter()
        tehtavat_count = 0

        for t in tehtäväviestit:
            ts = t.get("timestamp")
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            if self._in_range(dt, start, end):
                tehtavat_count += 1
                tehtävä_counter[t.get("task") or "Tuntematon tehtävä"] += 1

        daily_streak = weekly_streak = monthly_streak = 0
        daily_longest = weekly_longest = monthly_longest = 0
        xp_per_task = 50

        try:
            with open(TIEDOSTOT.get("Streakit"), encoding="utf-8") as f:
                streaks = json.load(f)
            d = streaks.get(uid, {}).get("daily", {}) or {}
            w = streaks.get(uid, {}).get("weekly", {}) or {}
            m = streaks.get(uid, {}).get("monthly", {}) or {}

            daily_streak = int(d.get("streak", 0))
            weekly_streak = int(w.get("streak", 0))
            monthly_streak = int(m.get("streak", 0))

            daily_longest = int(d.get("max_streak", daily_streak))
            weekly_longest = int(w.get("max_streak", weekly_streak))
            monthly_longest = int(m.get("max_streak", monthly_streak))

            if monthly_streak >= 1:
                xp_per_task = 150
            elif weekly_streak >= 1:
                xp_per_task = 100
            elif daily_streak >= 1:
                xp_per_task = 50
        except Exception:
            pass

        tehtävä_xp = tehtavat_count * xp_per_task

        puhe_streak = 0
        puhe_pisin = 0
        puhe_viimeisin_pvm = None

        try:
            with open(TIEDOSTOT["Puhe-streak"], encoding="utf-8") as f:
                pdata = json.load(f)

            puhedata = pdata.get(uid, {})
            puhe_streak = int(puhedata.get("streak", 0))
            puhe_pisin = int(puhedata.get("pisin", puhe_streak))
            puhe_viimeisin_pvm = puhedata.get("pvm")

        except Exception:
            pass

        tallennettu_xp = 0
        try:
            with open(TIEDOSTOT["XP-data"], "r", encoding="utf-8") as f:
                xp_data = json.load(f)
            tallennettu_xp = int(xp_data.get(uid, {}).get("xp", 0))
        except Exception:
            pass

        voice_xp = 0
        try:
            voice_path = os.getenv("XP_VOICE_DATA_PATH")
            if voice_path and Path(voice_path).exists():
                with open(voice_path, "r", encoding="utf-8") as f:
                    voice_data = json.load(f)
                voice_minutes = voice_data.get("total_voice_usage", {}).get(uid, 0)
                voice_xp = int((voice_minutes / 60) * 10)
        except Exception:
            pass

        message_xp = max(0, tallennettu_xp - tehtävä_xp - voice_xp)

        stats["xp"] = {
            "tasks_xp": int(tehtävä_xp),
            "voice_xp": int(voice_xp),
            "message_xp": int(message_xp),
            "total_xp": int(tallennettu_xp),
        }

        stats["tasks"] = {
            "count": int(tehtavat_count),
            "xp_per_task": int(xp_per_task),
            "daily_streak": int(daily_streak),
            "weekly_streak": int(weekly_streak),
            "monthly_streak": int(monthly_streak),
            "daily_longest": int(daily_longest),
            "weekly_longest": int(weekly_longest),
            "monthly_longest": int(monthly_longest),
            "top_tasks": list(tehtävä_counter.most_common(5)),
            "voice_streak": {
                "streak": int(puhe_streak),
                "longest": int(puhe_pisin),
                "last_date": puhe_viimeisin_pvm,
            },
        }

        purchases_count = 0
        spent_xp_sample = 0
        top_products = Counter()

        try:
            ostosviestit = await hae_ostosviestit(uid)
            vuoden_ostokset = [m for m in ostosviestit if self._in_range(m.created_at, start, end)]
            purchases_count = len(vuoden_ostokset)

            for m in vuoden_ostokset:
                match = re.search(r"osti tuotteen (.+?) \((\d+) XP\)", m.content)
                tuote = match.group(1).strip() if match else "Tuntematon tuote"
                top_products[tuote] += 1

            for m in vuoden_ostokset[:5]:
                match = re.search(r"osti tuotteen (.+?) \((\d+) XP\)", m.content)
                hinta = int(match.group(2)) if match else 0
                spent_xp_sample += hinta
        except Exception:
            pass

        tarjous_count = 0
        try:
            tarjousviestit = await hae_tarjousviestit(uid)
            vuoden_tarjoukset = [m for m in tarjousviestit if self._in_range(m.created_at, start, end)]
            tarjous_count = len(vuoden_tarjoukset)
        except Exception:
            pass

        kuponki_kerrat = 0
        kuponki_top = Counter()
        arvioitu_saasto = 0

        try:
            with open(TIEDOSTOT["Kuponki"], encoding="utf-8") as f:
                tapahtumat_data = json.load(f)
            tapahtumat = tapahtumat_data.get(uid, []) or []

            try:
                with open(JSON_DIRS / "kuponki.json", encoding="utf-8") as f:
                    kuponki_data = json.load(f)
            except Exception:
                kuponki_data = {}

            try:
                with open(JSON_DIRS / "tuotteet.json", encoding="utf-8") as f:
                    tuotteet_lista = json.load(f)
            except Exception:
                tuotteet_lista = []

            def hae_hinta(nimi: str) -> int:
                for t in tuotteet_lista:
                    if t.get("nimi") == nimi:
                        return int(t.get("hinta", 0))
                return 0

            def hae_tuote_tarj(nimi: str) -> int:
                for t in tuotteet_lista:
                    if t.get("nimi") == nimi:
                        return int(t.get("tarjousprosentti", 0))
                return 0

            for ev in tapahtumat:
                aika = ev.get("aika")
                try:
                    dt = datetime.fromisoformat(aika) if aika else None
                except Exception:
                    dt = None
                if not dt or not self._in_range(dt, start, end):
                    continue

                kuponki = ev.get("kuponki", "Tuntematon")
                tuote = ev.get("tuote", "Tuntematon tuote")
                kuponki_kerrat += 1
                kuponki_top[kuponki] += 1

                prosentti = int(kuponki_data.get(kuponki, {}).get("prosentti", 0))
                hinta = hae_hinta(tuote)
                tuote_pros = hae_tuote_tarj(tuote)
                kokonais = prosentti + tuote_pros
                if hinta and kokonais:
                    arvioitu_saasto += int(hinta * (kokonais / 100))
        except Exception:
            pass

        stats["shop"] = {
            "purchases_count": int(purchases_count),
            "spent_xp_sample": int(spent_xp_sample),
            "top_products": list(top_products.most_common(5)),
            "offers_count": int(tarjous_count),
            "coupons_count": int(kuponki_kerrat),
            "coupons_top": list(kuponki_top.most_common(5)),
            "estimated_savings_xp": int(arvioitu_saasto),
        }

        osallistumiset = await hae_osallistumisviestit(user, self.bot)
        tyyppilaskuri = Counter()
        for data in osallistumiset:
            dt = data.get("aika")
            if isinstance(dt, datetime) and self._in_range(dt, start, end):
                tyyppilaskuri[data["tyyppi"]] += 1

        stats["participation"] = {
            "total": int(sum(tyyppilaskuri.values())),
            "types": dict(tyyppilaskuri)
        }

        commands_total = 0
        commands_top = []
        try:
            log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
            log_channel = self.bot.get_channel(log_channel_id)
            laskuri = Counter()
            if log_channel:
                async for msg_log in log_channel.history(limit=1000):
                    if not self._in_range(msg_log.created_at, start, end):
                        continue
                    if f"({user.id})" in msg_log.content:
                        m = re.search(r"Komento: `(.+?)`", msg_log.content)
                        if m:
                            laskuri[m.group(1)] += 1
                commands_total = sum(laskuri.values())
                commands_top = laskuri.most_common(5)
        except Exception:
            pass
        stats["commands"] = {"total": int(commands_total), "top": commands_top}

        warnings_count = 0
        mute_count = 0
        help_count = 0

        try:
            varoituskanava = self.bot.get_channel(int(os.getenv("MODLOG_CHANNEL_ID")))
            mutekanava = self.bot.get_channel(int(os.getenv("MUTE_CHANNEL_ID")))
            helpkanava = self.bot.get_channel(int(os.getenv("HELP_CHANNEL_ID")))
        except Exception:
            varoituskanava = mutekanava = helpkanava = None

        if varoituskanava:
            async for msg in varoituskanava.history(limit=1000):
                if not self._in_range(msg.created_at, start, end):
                    continue
                if f"ID: {user.id}" in msg.content:
                    warnings_count += 1

        if mutekanava:
            async for msg in mutekanava.history(limit=1000):
                if not self._in_range(msg.created_at, start, end):
                    continue
                if "🔇" not in msg.content or "Jäähy" not in msg.content:
                    continue

                rivit = msg.content.splitlines()
                käyttäjä_rivi = next((r for r in rivit if r.startswith("👤")), "")
                if not any(x in käyttäjä_rivi for x in [user.mention, str(user.id), user.name]):
                    continue

                mute_count += 1

        if helpkanava:
            async for msg in helpkanava.history(limit=500):
                if not self._in_range(msg.created_at, start, end):
                    continue
                if msg.embeds:
                    e0 = msg.embeds[0]
                    footer = e0.footer.text if e0.footer else ""
                    if f"({user.id})" in footer:
                        help_count += 1

        stats["moderation"] = {
            "warnings": int(warnings_count),
            "mutes": int(mute_count),
            "help_requests": int(help_count),
        }

        analysed_messages = 0
        try:
            guild = interaction.guild
            if guild:
                analyysi = JäsenToimintaAnalyysi(user)
                await analyysi.analysoi(guild=guild, limit=1000)
                analysed_messages = sum(analyysi.kanavamäärät.values())
        except Exception:
            pass

        total_voice_seconds = 0
        try:
            voice_data_path = Path(os.getenv("XP_VOICE_DATA_FILE"))
            if voice_data_path.exists():
                with open(voice_data_path, encoding="utf-8") as f:
                    voice_data = json.load(f)
                total_voice_seconds = int(voice_data.get("total_voice_usage", {}).get(uid, 0))
        except Exception:
            pass

        stats["activity"] = {"analysed_messages": int(analysed_messages), "total_voice_seconds": int(total_voice_seconds)}

        try:
            completed_all: dict[str, str] = {}
            last_streaks: dict = {}
            hint_usage_total = 0

            if ACHIEVEMENTS_PATH.exists():
                with open(ACHIEVEMENTS_PATH, encoding="utf-8") as f:
                    a_data = json.load(f)

                a_user = a_data.get(uid, {}) or {}
                completed_all = a_user.get("completed", {}) or {}
                last_streaks = a_user.get("last_streaks", {}) or {}

                hint_usage_dict = a_user.get("hint_usage", {}) or {}
                hint_usage_total = int(sum(int(v) for v in hint_usage_dict.values()))

            total_all = len(completed_all)
            cat_all = Counter()
            cat_year = Counter()
            total_year = 0

            for ach_key, ts in completed_all.items():
                cat = saavutusten_kategoria(ach_key)
                cat_all[cat] += 1

                try:
                    dt = datetime.fromisoformat(ts)
                except Exception:
                    dt = None

                if dt and self._in_range(dt, start, end):
                    total_year += 1
                    cat_year[cat] += 1

            stats["achievements"] = {
                "total_all": int(total_all),
                "total_year": int(total_year),
                "by_category_all": dict(cat_all),
                "by_category_year": dict(cat_year),
                "last_streaks": last_streaks,
                "hint_usage_total": int(hint_usage_total),
            }
        except Exception:
            stats["achievements"] = {
                "total_all": 0,
                "total_year": 0,
                "by_category_all": {},
                "by_category_year": {},
                "last_streaks": {},
                "hint_usage_total": 0,
            }

        return stats

    def _ostokset_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        s = stats.get("shop", {})
        embed = discord.Embed(
            title="🛒 Ostokset, tarjoukset & kupongit",
            description=f"{user.display_name} – kooste.",
            color=discord.Color.blue(),
        )

        embed.add_field(name="🛒 Ostoksia", value=f"**{s.get('purchases_count', 0)}**", inline=True)
        if prev and prev.get("shop", {}).get("purchases_count") is not None:
            embed.add_field(
                name="📈 Vertailu",
                value=ero_str(s.get("purchases_count", 0), prev.get("shop", {}).get("purchases_count"), "ostosta"),
                inline=True,
            )

        embed.add_field(
            name="💰 XP-käyttö (esimerkkilaskelma)",
            value=f"Viiden vuoden ostoksen perusteella käytetty ainakin **{s.get('spent_xp_sample', 0)} XP**.",
            inline=False,
        )

        top_products = s.get("top_products") or []
        embed.add_field(
            name="🏆 Useimmin ostetut tuotteet",
            value=("\n".join([f"- **{name}** ({n}×)" for name, n in top_products]) if top_products else "Ei ostoksia tältä vuodelta."),
            inline=False,
        )

        embed.add_field(name="🎁 Tarjouksia", value=f"**{s.get('offers_count', 0)}**", inline=True)
        embed.add_field(name="🎟️ Kuponkien käyttö", value=f"**{s.get('coupons_count', 0)}**", inline=True)

        coupons_top = s.get("coupons_top") or []
        if coupons_top:
            embed.add_field(
                name="🏆 Käytetyimmät kupongit",
                value="\n".join([f"- **{name}** ({n}×)" for name, n in coupons_top]),
                inline=False,
            )

        embed.add_field(
            name="💸 Arvioitu säästö",
            value=f"**{s.get('estimated_savings_xp', 0)} XP**",
            inline=False,
        )

        return embed

    def _tehtävät_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        t = stats["tasks"]

        embed = discord.Embed(
            title="📘 Tehtävät & streakit",
            description=f"{user.display_name} – kooste.",
            color=discord.Color.blue(),
        )

        embed.add_field(name="📊 Tehtäviä", value=f"**{t['count']}**", inline=True)
        if prev and prev.get("tasks", {}).get("count") is not None:
            embed.add_field(
                name="📈 Vertailu",
                value=ero_str(t["count"], prev.get("tasks", {}).get("count"), "tehtävää"),
                inline=True,
            )

        embed.add_field(
            name="🔥 Streakit",
            value=(
                f"📅 Päivittäinen: **{t['daily_streak']}** (pisin **{t.get('daily_longest', t['daily_streak'])}**)\n"
                f"📆 Viikoittainen: **{t['weekly_streak']}** (pisin **{t.get('weekly_longest', t['weekly_streak'])}**)\n"
                f"🗓️ Kuukausittainen: **{t['monthly_streak']}** (pisin **{t.get('monthly_longest', t['monthly_streak'])}**)"
            ),
            inline=False,
        )

        vs = (t.get("voice_streak") or {})
        if vs.get("streak", 0) > 0 or vs.get("longest", 0) > 0:
            last = vs.get("last_date") or "?"
            embed.add_field(
                name="🎤 Puhe-streak",
                value=f"🔥 {vs.get('streak', 0)} päivää • 🏆 pisin {vs.get('longest', 0)} päivää • 📅 viimeisin {last}",
                inline=False,
            )
        else:
            embed.add_field(name="🎤 Puhe-streak", value="Ei puhe-streakia tallennettuna.", inline=False)

        top = t.get("top_tasks", [])
        embed.add_field(
            name="🏆 Useimmin tehdyt tehtävät",
            value=("\n".join([f"- **{name}** ({n}×)" for name, n in top]) if top else "Ei tehtäviä tältä vuodelta."),
            inline=False,
        )

        embed.add_field(
            name="📝 Tehtäväkommentti",
            value=tehtava_kommentti(
                int(t["count"]),
                int(t.get("daily_streak", 0)),
                int(t.get("weekly_streak", 0)),
                int(t.get("monthly_streak", 0)),
            ),
            inline=False,
        )

        return embed

    def _moderointi_toiminta_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        mod = stats["moderation"]
        act = stats["activity"]

        warnings = mod.get("warnings", 0)
        mutes = mod.get("mutes", 0)
        help_req = mod.get("help_requests", 0)

        analysed = act.get("analysed_messages", 0)
        voice_sec = act.get("total_voice_seconds", 0)
        hours = voice_sec / 3600 if voice_sec else 0

        embed = discord.Embed(
            title="⚖️ Moderointi & toiminta",
            description=f"{user.display_name} – kooste.",
            color=discord.Color.blue(),
        )

        embed.add_field(name="⚠️ Varoituksia", value=f"**{warnings}**", inline=True)
        embed.add_field(name="🔇 Jäähyjä", value=f"**{mutes}**", inline=True)
        embed.add_field(name="🆘 Help-pyyntöjä", value=f"**{help_req}**", inline=True)

        if prev:
            pv = prev.get("moderation", {})
            if pv.get("warnings") is not None:
                embed.add_field(name="📈 Varoitukset", value=ero_str(warnings, pv.get("warnings"), "kpl"), inline=False)
            if pv.get("mutes") is not None:
                embed.add_field(name="📈 Jäähyt", value=ero_str(mutes, pv.get("mutes"), "kpl"), inline=False)
            if pv.get("help_requests") is not None:
                embed.add_field(name="📈 Help", value=ero_str(help_req, pv.get("help_requests"), "kpl"), inline=False)

        embed.add_field(name="📝 Arvio", value=varoitus_kommentti(warnings), inline=False)

        embed.add_field(name="💬 Analysoidut viestit", value=f"**{analysed}**", inline=True)
        embed.add_field(name="🎙️ Puheaika (kokonais)", value=f"**{hours:.1f} h**", inline=True)
        embed.add_field(name="🗣️ Puhe-arvio", value=puhe_kommentti(voice_sec), inline=False)

        return embed

    def _etusivu(
        self,
        user: discord.User,
        year: int,
        start: datetime,
        end: datetime,
        visible_until_dt: datetime
    ) -> discord.Embed:
        ajanjakso = f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"
        until_str = visible_until_dt.strftime("%d.%m.%Y")

        embed = discord.Embed(
            title=f"Tilu 24G Rewind [{year}] ({user.display_name} edition)",
            description=(
                "Oletko valmis näkemään toimintasi tältä vuodelta?\n"
                f"Pystyt näkemään yhteenvedon: **{until_str}** klo 23:59 saakka.\n\n"
                f"**Ajanjakso:** {ajanjakso}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Yhteenveto tehty Sannamaijan tietokannoista.")
        return embed

    def _xp_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        xp = stats.get("xp", {})
        total_xp = int(xp.get("total_xp", 0))

        embed = discord.Embed(
            title="🔢 XP-yhteenveto",
            description=f"Käyttäjän {user.display_name} XP-kooste.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📌 Mistä XP:si tulee",
            value=(
                f"📘 Tehtävät (vuosi arvio): **{int(xp.get('tasks_xp', 0))} XP**\n"
                f"🔊 Puhe (kokonais arvio): **{int(xp.get('voice_xp', 0))} XP**\n"
                f"🔎 Viestit (arvio): **{int(xp.get('message_xp', 0))} XP**\n"
                f"✨ Yhteensä: **{total_xp} XP**"
            ),
            inline=False,
        )
        embed.add_field(name="📝 Arvio", value=xp_kommentti(total_xp), inline=False)

        if prev and prev.get("xp", {}).get("total_xp") is not None:
            embed.add_field(
                name="📊 Vertailu edelliseen",
                value=ero_str(total_xp, int(prev["xp"]["total_xp"]), "XP"),
                inline=False,
            )

        return embed

    def _osallistumiset_komennot_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        part = stats.get("participation", {})
        cmds = stats.get("commands", {})

        part_total = int(part.get("total", 0))
        cmd_total = int(cmds.get("total", 0))

        types = part.get("types") or {}
        arvonnat = int(types.get("Arvonta", 0))
        voitot = int(types.get("Arvontavoitto", 0))
        ruoka = int(types.get("Ruokaäänestys", 0))
        kysely = int(types.get("Kyselyäänestys", 0))
        aanestykset = ruoka + kysely

        embed = discord.Embed(
            title="📥 Osallistumiset & komennot",
            description=f"{user.display_name} – kooste.",
            color=discord.Color.blue(),
        )

        embed.add_field(name="📥 Osallistumisia yhteensä", value=f"**{part_total}**", inline=True)
        if prev and prev.get("participation", {}).get("total") is not None:
            embed.add_field(
                name="📈 Vertailu",
                value=ero_str(part_total, int(prev["participation"]["total"]), "osallistumista"),
                inline=True,
            )

        embed.add_field(
            name="🗳️ Äänestykset",
            value=(
                f"- Kyselyäänestykset: **{kysely}**\n"
                f"- Ruokaäänestykset: **{ruoka}**\n"
                f"= Yhteensä **{aanestykset}** äänestystä"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎟️ Arvonnat",
            value=(
                f"- Arvontaan osallistumisia: **{arvonnat}**\n"
                f"- Arvontavoittoja: **{voitot}**"
            ),
            inline=False,
        )

        embed.add_field(
            name="📝 Osallistumiskommentti",
            value=osallistuminen_kommentti(part_total, arvonnat, voitot, aanestykset),
            inline=False,
        )

        embed.add_field(name="💬 Komentoja", value=f"**{cmd_total}**", inline=True)
        if prev and prev.get("commands", {}).get("total") is not None:
            embed.add_field(
                name="📈 Vertailu",
                value=ero_str(cmd_total, int(prev["commands"]["total"]), "komentoa"),
                inline=True,
            )

        top = cmds.get("top") or []
        embed.add_field(
            name="🏆 Useimmin käytetyt komennot",
            value=(
                "\n".join([f"- `{name}` ({n}×)" for name, n in top])
                if top else "Ei komentoja tältä vuodelta."
            ),
            inline=False,
        )

        return embed

    def _saavutukset_sivu(self, user: discord.User, stats: dict, prev: dict | None) -> discord.Embed:
        a = stats.get("achievements", {}) or {}
        total_year = int(a.get("total_year", 0))
        total_all = int(a.get("total_all", 0))
        by_cat_year = a.get("by_category_year", {}) or {}
        by_cat_all = a.get("by_category_all", {}) or {}
        hint_usage_total = int(a.get("hint_usage_total", 0))

        embed = discord.Embed(
            title="🏅 Saavutukset",
            description=f"{user.display_name} – avatut saavutukset.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📅 Tänä vuonna avatut",
            value=f"**{total_year}** saavutusta",
            inline=True,
        )

        if prev and prev.get("achievements", {}).get("total_year") is not None:
            embed.add_field(
                name="📈 Vertailu",
                value=ero_str(
                    total_year,
                    int(prev["achievements"]["total_year"]),
                    "saavutusta",
                ),
                inline=True,
            )

        embed.add_field(
            name="🗓️ Kaikkina aikoina",
            value=f"**{total_all}** saavutusta",
            inline=True,
        )

        if by_cat_year:
            kat_teksti = "\n".join(
                f"- **{kat}**: {määrä} kpl"
                for kat, määrä in sorted(by_cat_year.items(), key=lambda x: x[1], reverse=True)
            )
        else:
            kat_teksti = "Tänä vuonna ei ole avattu uusia saavutuksia."

        embed.add_field(
            name="📅 Jaottelu (tämä vuosi)",
            value=kat_teksti,
            inline=False,
        )

        if by_cat_all:
            kat_all_teksti = "\n".join(
                f"- **{kat}**: {määrä} kpl"
                for kat, määrä in sorted(by_cat_all.items(), key=lambda x: x[1], reverse=True)
            )
            embed.add_field(
                name="🗓️ Jaottelu (kaikki ajat)",
                value=kat_all_teksti,
                inline=False,
            )

        lisä = []

        if hint_usage_total > 0:
            lisä.append(f"Vihjeitä käytetty yhteensä **{hint_usage_total}** kertaa.")

        if lisä:
            embed.add_field(
                name="💡 Lisäksi",
                value=" ".join(lisä),
                inline=False,
            )

        embed.add_field(
            name="📝 Saavutuskommentti",
            value=saavutukset_kommentti(total_year, total_all, by_cat_year),
            inline=False,
        )

        return embed

    async def _näytä_yhteenveto(self, interaction: discord.Interaction, target: discord.User):
        year = now_local().year
        visible_until_dt = get_visible_until(year)

        try:
            settings = get_user_settings(str(target.id))
        except Exception:
            settings = {}

        if not settings.get("yhteenveto_henkilotiedot", True):
            await interaction.response.send_message(
                "🧾 Et ole sallinut henkilötietojesi yhteenvedon tekemistä asetuksissa.\n"
                "Voit ottaa sen takaisin käyttöön komennolla **/asetukset**.",
                ephemeral=True
            )
            return

        if now_local() > visible_until_dt:
            until_str = visible_until_dt.strftime("%d.%m.%Y")
            await interaction.response.send_message(
                f"Tilu 24G Wrapped-yhteenveto on sulkeutunut ({until_str}).",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        lataus_embed = discord.Embed(
            title="⏳ Ladataan Tilu 24G Wrapped-dataa...",
            description="Haetaan tietoja lokista ja tietokannoista.\nTämä saattaa kestää hetken ennen kuin etusivu avautuu.\nArvioitu odotusaika: 30 sek – 3 min.",
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(embed=lataus_embed, view=None)

        try:
            start, end = self._period_range(year)
            uid = str(target.id)

            current_stats = await self._kerää_tilastot(interaction, target, year)
            prev_stats = self._lue_edellinen_yhteenveto(year, uid)
            self._tallenna_yhteenveto(year, uid, current_stats)

            loppu_embed, save_payload = self._loppu_yhteenveto_sivu(target, year, current_stats, start, end)

            pages = [
                ("Etusivu", lambda: self._etusivu(target, year, start, end, visible_until_dt)),
                ("XP", lambda: self._xp_sivu(target, current_stats, prev_stats)),
                ("Tehtävät & streakit", lambda: self._tehtävät_sivu(target, current_stats, prev_stats)),
                ("Ostokset", lambda: self._ostokset_sivu(target, current_stats, prev_stats)),
                ("Osallistumiset & komennot", lambda: self._osallistumiset_komennot_sivu(target, current_stats, prev_stats)),
                ("Moderointi & toiminta", lambda: self._moderointi_toiminta_sivu(target, current_stats, prev_stats)),
                ("Saavutukset", lambda: self._saavutukset_sivu(target, current_stats, prev_stats)), 
                ("Loppukooste", lambda: loppu_embed),
            ]

            view = self.RewindView(pages, save_payload)

            await interaction.edit_original_response(embed=pages[0][1](), view=view)

        except Exception as e:
            err = discord.Embed(
                title="⚠️ Yhteenvedon lataus epäonnistui",
                description=f"Virhe: `{type(e).__name__}`\n{e}",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=err, view=None)
            raise 

    @app_commands.command(name="yhteenveto", description="Näytä oma Tilu 24G Wrapped.")
    @app_commands.checks.has_role("24G")
    async def yhteenveto(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/yhteenveto")
        await kirjaa_ga_event(self.bot, interaction.user.id, "yhteenveto_komento")
        await self._näytä_yhteenveto(interaction, interaction.user)

    @app_commands.command(name="yhteenveto_jäsenet", description="Näytä jäsenen Tilu 24G Wrapped.")
    @app_commands.describe(jäsen="Jäsen, jonka yhteenveto näytetään.")
    @app_commands.checks.has_role("Mestari")
    async def yhteenveto_jäsenet(self, interaction: discord.Interaction, jäsen: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/yhteenveto_jäsenet")
        await kirjaa_ga_event(self.bot, interaction.user.id, "yhteenveto_jäsenet_komento")
        if not isinstance(interaction.user, discord.Member) or not is_mestari(interaction.user):
            await interaction.response.send_message("Tämä komento on vain Mestari-roolille.", ephemeral=True)
            return
        await self._näytä_yhteenveto(interaction, jäsen)

async def setup(bot: commands.Bot):
    await bot.add_cog(YhteenvetoCog(bot))