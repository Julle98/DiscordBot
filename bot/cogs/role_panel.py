from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import discord
import os
from pathlib import Path
from discord import app_commands
from discord.ext import commands
import asyncio
import json
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin

BASE_DATA_PATH = Path(os.getenv("ROLES_JSON_PATH", "."))
ROLE_LOG_JSON_PATH = BASE_DATA_PATH / "role_toggle_log.json"
SESSIONS_JSON_PATH = BASE_DATA_PATH / "rolepanel_builder_sessions.json"
ROLE_PANELS_JSON_PATH = BASE_DATA_PATH / "rolepanel_templates.json"
PUBLISHED_PANELS_JSON_PATH = BASE_DATA_PATH / "rolepanel_published_panels.json"
ROLE_LOG_CHANNEL_ID = int(os.getenv("ROLE_LOG_CHANNEL_ID", "0"))
MAX_OPTIONS = 10

@dataclass
class RoleOption:
    title: str
    emoji: Optional[str]
    role_id: int
    description: str

def parse_role_id(raw: str) -> int:
    raw = raw.strip()
    if raw.startswith("<@&") and raw.endswith(">"):
        raw = raw[3:-1]
    if not raw.isdigit():
        raise ValueError("role id")
    return int(raw)

def build_embed(options: list[RoleOption]) -> discord.Embed:
    now = datetime.now()
    timestamp = now.strftime("%d.%m.%Y klo %H:%M")

    emb = discord.Embed(
        color=discord.Color.blue(),
        description=(
            "**Haluatko extra rooleja?**\n"
            "Valitse alla olevista vaihtoehtoista sen minkä haluat.\n"
            "Klikkaa oikeaa nappulaa saadaksesi roolin! Klikkaa uudestaan poistaaksesi roolin."
        )
    )

    for opt in options:
        emoji = (opt.emoji or "").strip()
        prefix = f"{emoji} " if emoji else ""
        field_name = f"**{prefix}-> {opt.title}**".replace("->", " ->", 1)
        emb.add_field(name=field_name, value=opt.description or "—", inline=False)

    emb.set_footer(text=f"Päivitetty viimeksi {timestamp}")
    return emb

class CountModal(discord.ui.Modal, title="Roolipaneeli: montako vaihtoehtoa?"):
    count = discord.ui.TextInput(
        label="Montako roolia lisätään? (1-10)",
        placeholder="esim. 4",
        max_length=2,
    )

    def __init__(self, title: str = "Roolipaneeli: montako vaihtoehtoa?",
             label: str = "Montako roolia lisätään? (1-10)",
             min_n: int = 1, max_n: int = MAX_OPTIONS):
        super().__init__(timeout=300, title=title)
        self.value: Optional[int] = None
        self.min_n = min_n
        self.max_n = max_n
        self.count.label = label

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(str(self.count.value).strip())
            if not (self.min_n <= n <= self.max_n):
                raise ValueError
            self.value = n
            await interaction.response.defer(ephemeral=True)
        except Exception:
            await interaction.response.send_message("Anna numero väliltä 1–10.", ephemeral=True)

class RoleOptionModal(discord.ui.Modal):
    def __init__(self, index: int):
        super().__init__(title=f"Roolivaihtoehto {index}", timeout=300)
        self.result: Optional[RoleOption] = None

        self.opt_title = discord.ui.TextInput(
            label="Otsikko (esim. Hyväksyt palvelimen säännöt)",
            max_length=80,
        )
        self.opt_emoji = discord.ui.TextInput(
            label="Emoji (valinnainen)",
            placeholder="esim. 🫡",
            required=False,
            max_length=20,
        )
        self.opt_role = discord.ui.TextInput(
            label="Rooli (ID tai @rooli)",
            placeholder="esim. 123456789012345678 tai <@&123...>",
            max_length=40,
        )
        self.opt_desc = discord.ui.TextInput(
            label="Kuvaus",
            style=discord.TextStyle.paragraph,
            max_length=400,
        )

        self.add_item(self.opt_title)
        self.add_item(self.opt_emoji)
        self.add_item(self.opt_role)
        self.add_item(self.opt_desc)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            role_id = parse_role_id(str(self.opt_role.value))
            emoji = str(self.opt_emoji.value).strip() or None
            self.result = RoleOption(
                title=str(self.opt_title.value).strip(),
                emoji=emoji,
                role_id=role_id,
                description=str(self.opt_desc.value).strip(),
            )
            await interaction.response.defer(ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                "Rooli pitää olla rooli-ID tai @rooli (esim. `<@&123...>`).",
                ephemeral=True,
            )

class RoleToggleButton(discord.ui.Button):
    def __init__(self, opt: RoleOption, idx: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=opt.title[:80],
            custom_id=f"rolepanel_toggle:{opt.role_id}:{idx}",
        )
        if opt.emoji:
            try:
                self.emoji = opt.emoji
            except Exception:
                pass
        self.opt = opt

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Tämä toimii vain serverillä.", ephemeral=True)

        role = interaction.guild.get_role(self.opt.role_id)
        if role is None:
            return await interaction.response.send_message("Roolia ei löytynyt (poistettu?).", ephemeral=True)

        member: discord.Member = interaction.user
        action = None

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Role panel toggle")
                action = "removed"
                await interaction.response.send_message(f"Poistettiin rooli: {role.mention}", ephemeral=True)
            else:
                await member.add_roles(role, reason="Role panel toggle")
                action = "added"
                await interaction.response.send_message(f"Lisättiin rooli: {role.mention}", ephemeral=True)

            cog = interaction.client.get_cog("RolePanelCog")
            if cog and action:
                entry = {
                    "time": cog._now_str(),
                    "action": action,
                    "guild_id": interaction.guild.id,
                    "channel_id": interaction.channel.id if interaction.channel else None,
                    "user_id": member.id,
                    "user_tag": str(member),
                    "role_id": role.id,
                    "role_name": role.name,
                }
                await cog.append_rolelog_json(entry)

                arrow = "➕" if action == "added" else "➖"
                await cog.send_rolelog_channel(
                    interaction.guild,
                    f"{arrow} {member.mention} {('sai' if action=='added' else 'menetti')} roolin {role.mention} • {entry['time']}",
                )

        except discord.Forbidden:
            await interaction.response.send_message(
                "Ei oikeuksia muokata rooleja. Tarkista botin rooli ja roolijärjestys.",
                ephemeral=True
            )

class RolePanelView(discord.ui.View):
    def __init__(self, options: list[RoleOption]):
        super().__init__(timeout=None)
        for i, opt in enumerate(options):
            self.add_item(RoleToggleButton(opt, i))

class PanelBuilderState:
    def __init__(self, target_count: int, preset_options: Optional[list[RoleOption]] = None):
        self.target_count = target_count
        self.options: list[RoleOption] = list(preset_options or [])

    @property
    def remaining(self) -> int:
        return self.target_count - len(self.options)

    @property
    def next_index(self) -> int:
        return len(self.options) + 1

    @property
    def done(self) -> bool:
        return len(self.options) >= self.target_count

class PanelBuilderView(discord.ui.View):
    def __init__(self, cog: "RolePanelCog", user_id: int):
        super().__init__(timeout=900)
        self.cog = cog
        self.user_id = user_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Tämä luonti kuuluu toiselle käyttäjälle.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Lisää seuraava rooli", style=discord.ButtonStyle.primary)
    async def add_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.builder_sessions.get(self.user_id)
        if not state:
            return await interaction.response.send_message("Luontisessio puuttuu / vanheni.", ephemeral=True)

        if state.done:
            return await interaction.response.send_message("Kaikki vaihtoehdot on jo lisätty.", ephemeral=True)

        modal = RoleOptionModal(state.next_index)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.result:
            return await interaction.followup.send("Modal peruttiin tai ei palauttanut dataa.", ephemeral=True)

        state.options.append(modal.result)
        await self.cog.save_session_for_user(self.user_id)

        if state.done:
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.label == "Julkaise":
                    child.disabled = False

        await interaction.followup.send(
            f"Lisätty {len(state.options)}/{state.target_count}.",
            ephemeral=True,
        )

        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Julkaise", style=discord.ButtonStyle.success, disabled=True)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.builder_sessions.get(self.user_id)
        if not state or not state.done:
            return await interaction.response.send_message("Lisää ensin kaikki vaihtoehdot.", ephemeral=True)

        emb = build_embed(state.options)
        view = RolePanelView(state.options)

        if interaction.guild:
            await self.cog.save_template(interaction.guild.id, state.options, author_id=interaction.user.id)

        await self.cog.delete_session_for_user(self.user_id)
        await interaction.response.send_message("Julkaistu tähän kanavaan ✅", ephemeral=True)
        msg = await interaction.channel.send(embed=emb, view=view)
        if interaction.guild:
            await self.cog.save_published_panel(interaction.guild.id, msg.channel.id, msg.id, state.options)

        self.stop()

    @discord.ui.button(label="Peruuta", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.delete_session_for_user(self.user_id)
        await interaction.response.send_message("Peruutettu.", ephemeral=True)
        self.stop()

class TemplatePickView(discord.ui.View):
    def __init__(self, cog: "RolePanelCog", user_id: int, guild_id: int, templates: list[dict]):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.templates = templates

        options = [discord.SelectOption(label="Uusi pohja", value="new", description="Aloita tyhjästä")]
        for t in templates[:24]:
            label = t.get("name") or f"Pohja ({len(t.get('options', []))} roolia)"
            desc = f"{len(t.get('options', []))} roolia • {t.get('saved_at','')}".strip()
            options.append(discord.SelectOption(label=label[:100], value=t["id"], description=desc[:100] if desc else None))

        self.select = discord.ui.Select(placeholder="Valitse pohja", min_values=1, max_values=1, options=options)
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Tämä valinta kuuluu toiselle käyttäjälle.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        choice = self.select.values[0]

        if choice == "new":
            count_modal = CountModal()
            await interaction.response.send_modal(count_modal)
            await count_modal.wait()
            if not count_modal.value:
                return

            self.cog.builder_sessions[self.user_id] = PanelBuilderState(count_modal.value)
            await self.cog.save_session_for_user(self.user_id)

            view = PanelBuilderView(self.cog, self.user_id)
            msg = await interaction.followup.send(
                f"Lisätään {count_modal.value} roolia. Paina **Lisää seuraava rooli** ja täytä modal (toista kunnes valmis).",
                ephemeral=True,
                view=view,
            )
            view.message = msg
            self.stop()
            return

        template = next((t for t in self.templates if t["id"] == choice), None)
        if not template:
            return await interaction.response.send_message("Pohjaa ei löytynyt.", ephemeral=True)

        preset = []
        for o in template.get("options", []):
            preset.append(RoleOption(
                title=o["title"],
                emoji=o.get("emoji"),
                role_id=int(o["role_id"]),
                description=o.get("description", "")
            ))

        add_modal = CountModal(
            title="Lisää vanhaan pohjaan",
            label=f"Montako uutta lisätään? (0-10) Nykyinen: {len(preset)}",
            min_n=0,
            max_n=MAX_OPTIONS
        )
        await interaction.response.send_modal(add_modal)
        await add_modal.wait()

        if add_modal.value == 0:
            emb = build_embed(preset)
            view = RolePanelView(preset)
            msg = await interaction.channel.send(embed=emb, view=view)
            await interaction.followup.send("Julkaistu vanha pohja sellaisenaan ✅", ephemeral=True)

            if interaction.guild:
                await self.cog.save_published_panel(interaction.guild.id, msg.channel.id, msg.id, preset)
                await self.cog.save_template(interaction.guild.id, preset, author_id=interaction.user.id)  
            self.stop()
            return

        if not add_modal.value:
            return

        target = len(preset) + add_modal.value
        self.cog.builder_sessions[self.user_id] = PanelBuilderState(target, preset_options=preset)
        await self.cog.save_session_for_user(self.user_id)

        view = PanelBuilderView(self.cog, self.user_id)
        msg = await interaction.followup.send(
            f"Pohja ladattu ({len(preset)} kpl). Lisää vielä {add_modal.value} kpl → yhteensä {target}.",
            ephemeral=True,
            view=view,
        )
        view.message = msg

        self.stop()

class RolePanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.builder_sessions: dict[int, PanelBuilderState] = {}

        self.rolelog_lock = asyncio.Lock()
        self.sessions_lock = asyncio.Lock()
        self.templates_lock = asyncio.Lock()
        self.published_lock = asyncio.Lock()

        self._load_builder_sessions_from_disk()

    async def cog_load(self):
        await self.register_persistent_views()

    def _load_builder_sessions_from_disk(self):
        try:
            if not SESSIONS_JSON_PATH.exists():
                return
            raw = SESSIONS_JSON_PATH.read_text(encoding="utf-8").strip() or "{}"
            blob = json.loads(raw)

            self.builder_sessions = {}
            for user_id_str, sess in blob.items():
                user_id = int(user_id_str)
                st = PanelBuilderState(int(sess["target_count"]))
                for opt in sess.get("options", []):
                    st.options.append(RoleOption(
                        title=opt["title"],
                        emoji=opt.get("emoji"),
                        role_id=int(opt["role_id"]),
                        description=opt.get("description", "")
                    ))
                self.builder_sessions[user_id] = st
        except Exception:
            self.builder_sessions = {}

    async def _save_builder_sessions_to_disk(self):
        async with self.sessions_lock:
            blob = {}
            for user_id, st in self.builder_sessions.items():
                blob[str(user_id)] = {
                    "target_count": st.target_count,
                    "options": [
                        {"title": o.title, "emoji": o.emoji, "role_id": o.role_id, "description": o.description}
                        for o in st.options
                    ],
                }
            SESSIONS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
            SESSIONS_JSON_PATH.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")

    async def save_session_for_user(self, user_id: int):
        await self._save_builder_sessions_to_disk()

    async def delete_session_for_user(self, user_id: int):
        self.builder_sessions.pop(user_id, None)
        await self._save_builder_sessions_to_disk()

    async def _load_published_panels(self) -> dict:
        if not PUBLISHED_PANELS_JSON_PATH.exists():
            return {"guilds": {}}
        try:
            raw = PUBLISHED_PANELS_JSON_PATH.read_text(encoding="utf-8").strip() or '{"guilds":{}}'
            blob = json.loads(raw)
            if "guilds" not in blob:
                blob["guilds"] = {}
            return blob
        except Exception:
            return {"guilds": {}}

    async def _save_published_panels(self, blob: dict):
        PUBLISHED_PANELS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        PUBLISHED_PANELS_JSON_PATH.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")

    async def save_published_panel(self, guild_id: int, channel_id: int, message_id: int, options: list[RoleOption]):
        async with self.published_lock:
            blob = await self._load_published_panels()
            guilds = blob.setdefault("guilds", {})
            arr = guilds.setdefault(str(guild_id), [])
            arr.insert(0, {
                "channel_id": channel_id,
                "message_id": message_id,
                "saved_at": self._now_str(),
                "options": [
                    {"title": o.title, "emoji": o.emoji, "role_id": o.role_id, "description": o.description}
                    for o in options
                ]
            })
            guilds[str(guild_id)] = arr[:50]
            await self._save_published_panels(blob)

    async def register_persistent_views(self):
        blob = await self._load_published_panels()
        for guild_id_str, arr in blob.get("guilds", {}).items():
            for item in arr:
                opts = []
                for o in item.get("options", []):
                    opts.append(RoleOption(
                        title=o["title"],
                        emoji=o.get("emoji"),
                        role_id=int(o["role_id"]),
                        description=o.get("description", "")
                    ))
                self.bot.add_view(RolePanelView(opts), message_id=int(item["message_id"]))

    def _now_str(self) -> str:
        return datetime.now().strftime("%d.%m.%Y klo %H:%M")

    async def _load_templates(self) -> dict:
        if not ROLE_PANELS_JSON_PATH.exists():
            return {"guilds": {}}
        try:
            raw = ROLE_PANELS_JSON_PATH.read_text(encoding="utf-8").strip() or '{"guilds":{}}'
            blob = json.loads(raw)
            if "guilds" not in blob:
                blob["guilds"] = {}
            return blob
        except Exception:
            return {"guilds": {}}

    async def _save_templates(self, blob: dict):
        ROLE_PANELS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        ROLE_PANELS_JSON_PATH.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")

    async def get_templates(self, guild_id: int) -> list[dict]:
        async with self.templates_lock:
            blob = await self._load_templates()
            return list(blob.get("guilds", {}).get(str(guild_id), []))

    async def save_template(self, guild_id: int, options: list[RoleOption], author_id: int):
        async with self.templates_lock:
            blob = await self._load_templates()
            guilds = blob.setdefault("guilds", {})
            arr = guilds.setdefault(str(guild_id), [])

            template_id = f"{int(datetime.now().timestamp())}_{author_id}"
            name = f"Pohja {len(options)} roolia"

            arr.insert(0, {
                "id": template_id,
                "name": name,
                "saved_at": self._now_str(),
                "author_id": author_id,
                "options": [
                    {"title": o.title, "emoji": o.emoji, "role_id": o.role_id, "description": o.description}
                    for o in options
                ]
            })

            guilds[str(guild_id)] = arr[:25]
            await self._save_templates(blob)

    async def append_rolelog_json(self, entry: dict):
        async with self.rolelog_lock:
            data = []
            if ROLE_LOG_JSON_PATH.exists():
                try:
                    data = json.loads(ROLE_LOG_JSON_PATH.read_text(encoding="utf-8") or "[]")
                except Exception:
                    data = []
            data.append(entry)
            ROLE_LOG_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def send_rolelog_channel(self, guild: discord.Guild, text: str):
        if ROLE_LOG_CHANNEL_ID <= 0:
            return
        ch = guild.get_channel(ROLE_LOG_CHANNEL_ID)
        if ch is None:
            try:
                ch = await guild.fetch_channel(ROLE_LOG_CHANNEL_ID)
            except Exception:
                return
        try:
            await ch.send(text)
        except Exception:
            pass

    @app_commands.command(name="roolipaneeli", description="Luo embed+napit roolien valintaan.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roolipaneeli(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/roolipaneeli")
        await kirjaa_ga_event(self.bot, interaction.user.id, "roolipaneeli_komento")

        existing = self.builder_sessions.get(interaction.user.id)
        if existing and not existing.done:
            view = PanelBuilderView(self, interaction.user.id)
            await interaction.response.send_message(
                f"Sinulla on kesken oleva luonti: {len(existing.options)}/{existing.target_count}. Jatketaanko?",
                ephemeral=True,
                view=view
            )
            return

        if not interaction.guild:
            return await interaction.response.send_message("Tämä toimii vain serverillä.", ephemeral=True)

        templates = await self.get_templates(interaction.guild.id)
        pick_view = TemplatePickView(self, interaction.user.id, interaction.guild.id, templates)

        await interaction.response.send_message(
            "Valitse käytetäänkö aiempaa pohjaa vai luodaanko uusi:",
            ephemeral=True,
            view=pick_view
        )

    @roolipaneeli.error
    async def roolipaneeli_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            return await interaction.response.send_message("Tarvitset Manage Roles -oikeuden.", ephemeral=True)
        raise error

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanelCog(bot))