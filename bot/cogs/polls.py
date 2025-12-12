import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from bot.utils.bot_setup import bot
from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
from discord import Interaction
from discord import Embed, Color
from discord.ext import commands
from discord import ui

load_dotenv()
DB_PATH = os.getenv("POLLS_JSON_PATH")
LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))

class FeedbackButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="📝 Anna palautetta",
            style=discord.ButtonStyle.secondary,
            custom_id="feedback_button"
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(FeedbackModal())

class FeedbackModal(ui.Modal, title="📝 Anna palautetta"):
    palaute = ui.TextInput(label="Palaute", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: Interaction):
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)

        embed = discord.Embed(
            title="📝 Uusi palaute äänestyksestä",
            description=self.palaute.value or "*Ei sisältöä*",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Lähettäjä: {interaction.user} • ID: {interaction.user.id}")

        if log_channel:
            await log_channel.send(embed=embed)

        view = discord.ui.View()
        view.add_item(FeedbackButton())

        await interaction.response.send_message(
            "Kiitos palautteestasi! 💙",
            ephemeral=True,
            view=view
        )

def load_poll_from_db(message_id: int):
    try:
        with open(DB_PATH, "r") as f:
            db = json.load(f)
    except FileNotFoundError:
        return None, None

    poll = next((p for p in db if int(p.get("message_id", 0)) == int(message_id)), None)
    return poll, db

def _safe_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None

class VoteButton(ui.Button):
    def __init__(self, index: int, label: str, poll_data: dict, parent_view):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"vote_{index}_{poll_data['message_id']}"
        )
        self.index = index
        self.poll_data = poll_data
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        user_roles = [r.id for r in interaction.user.roles]

        if any(r in self.poll_data["denied_roles"] for r in user_roles):
            msg = "🚫 Et saa äänestää tässä äänestyksessä."
        elif self.poll_data["allowed_roles"] and not any(
            r in self.poll_data["allowed_roles"] for r in user_roles
        ):
            msg = "🚫 Et saa äänestää tässä äänestyksessä."
        elif user_id in self.poll_data["votes"]:
            msg = "ℹ️ Olet jo äänestänyt."
        else:
            self.poll_data["votes"][user_id] = self.index
            self.parent_view._update_db()
            self.parent_view._refresh_labels()
            msg = f"Äänesi vaihtoehdolle {self.index + 1} on rekisteröity!"
            await self.parent_view._log_vote(interaction, self.index)

        view = ui.View()
        view.add_item(UnvoteButton(self.poll_data, self.parent_view))
        view.add_item(FeedbackButton())

        await interaction.response.send_message(msg, ephemeral=True, view=view)

class UnvoteButton(ui.Button):
    def __init__(self, poll_data: dict, parent_view):
        super().__init__(
            label="❎ Peru ääni",
            style=discord.ButtonStyle.danger,
            custom_id=f"unvote_{poll_data['message_id']}"
        )
        self.poll_data = poll_data
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        user_id = str(interaction.user.id)

        if user_id in self.poll_data.get("votes", {}):
            del self.poll_data["votes"][user_id]
            self.parent_view._update_db()
            self.parent_view._refresh_labels()
            await self.parent_view._log_unvote(interaction)
            msg = "Äänesi on peruttu."
        else:
            msg = "ℹ️ Sinulla ei ole aktiivista ääntä."

        view = ui.View()
        view.add_item(FeedbackButton())

        await interaction.response.send_message(
            msg,
            ephemeral=True,
            view=view
        )

class VoteButtonView(ui.View):
    def __init__(self, options: list[str], poll_data: dict):
        super().__init__(timeout=None)
        self.poll_data = poll_data
        self.message = None
        self.options = options

        for i, opt in enumerate(options):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][i]
            self.add_item(VoteButton(i, f"{emoji} {opt}", poll_data, self))

    async def _refresh_embed_and_view(self):
        if not self.message or not self.message.embeds:
            return

        counts = {i: 0 for i in range(len(self.options))}
        buckets = {i: [] for i in range(len(self.options))}

        for uid, opt_index in self.poll_data.get("votes", {}).items():
            if isinstance(opt_index, int) and 0 <= opt_index < len(self.options):
                counts[opt_index] += 1
                buckets[opt_index].append(uid)

        base = self.message.embeds[0]
        updated = discord.Embed.from_dict(base.to_dict())

        for i, opt in enumerate(self.options):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][i]
            voters = [f"<@{uid}>" for uid in buckets[i]]
            voters_text = ", ".join(voters) if voters else "*Ei ääniä*"

            value = f"Äänestäjät: {voters_text}"
            if len(value) > 1024:
                value = value[:1020] + "…"

            name = f"{emoji} {opt} (äänimäärä: {counts[i]})"

            if i < len(updated.fields):
                updated.set_field_at(i, name=name, value=value, inline=False)
            else:
                updated.add_field(name=name, value=value, inline=False)

        await self.message.edit(embed=updated, view=self)

    def _refresh_labels(self):
        asyncio.create_task(self._refresh_embed_and_view())

    def _update_db(self):
        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
            for p in db:
                if p["message_id"] == self.poll_data["message_id"]:
                    p["votes"] = self.poll_data["votes"]
                    break
            with open(DB_PATH, "w") as f:
                json.dump(db, f, indent=2)
        except Exception as e:
            print(f"⚠️ DB-päivitys epäonnistui: {e}")

    def disable_all(self):
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = True
                child.style = discord.ButtonStyle.secondary
        if self.message:
            asyncio.create_task(self.message.edit(view=self))

    async def _log_vote(self, interaction: Interaction, index: int):
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="✅ Ääni rekisteröity",
                description=f"{interaction.user} äänesti vaihtoehtoa {index + 1}",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"ID: {interaction.user.id}")
            await log_channel.send(embed=embed)

    async def _log_unvote(self, interaction: Interaction):
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="❎ Ääni peruttu",
                description=f"{interaction.user} perui äänensä",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"ID: {interaction.user.id}")
            await log_channel.send(embed=embed)

class AanestysModal(ui.Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="📊 Luo uusi äänestys")
        self.bot = bot

        self.kysymys = ui.TextInput(label="Äänestyksen otsikko", max_length=100)
        self.vaihtoehdot = ui.TextInput(
            label="Vaihtoehdot (pilkulla eroteltuna)",
            placeholder="Esim. Kissa, Koira, Lintu",
            max_length=200
        )
        self.aikaraja = ui.TextInput(
            label="Aikaraja (min)",
            placeholder="Esim. 5",
            max_length=5
        )
        self.rooli_id = ui.TextInput(
            label="Roolin ID (tägättävä)",
            placeholder="Esim. 123456789012345678",
            required=False,
            max_length=20
        )
        self.jasenrajoitukset = ui.TextInput(
            label="Jäsenrajoitukset",
            placeholder="Sallitut, erotin |, kielletyt... Esim: 111,222 | 333,444",
            required=False,
            max_length=400
        )

        self.add_item(self.kysymys)
        self.add_item(self.vaihtoehdot)
        self.add_item(self.aikaraja)
        self.add_item(self.rooli_id)
        self.add_item(self.jasenrajoitukset)

    async def on_submit(self, interaction: Interaction):
        try:
            minutes = int(self.aikaraja.value)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("⚠️ Virheellinen aikaraja. Käytä kokonaislukua yli 0.", ephemeral=True)
            return

        options = [opt.strip() for opt in self.vaihtoehdot.value.split(",") if opt.strip()]
        if not 2 <= len(options) <= 5:
            await interaction.response.send_message("⚠️ Anna 2–5 vaihtoehtoa pilkulla eroteltuna.", ephemeral=True)
            return

        allowed_roles, denied_roles = [], []
        raw = self.jasenrajoitukset.value.strip()

        try:
            if raw:
                parts = raw.split("|")
                if parts[0].strip():
                    allowed_roles = [int(i.strip()) for i in parts[0].split(",") if i.strip().isdigit()]
                if len(parts) > 1 and parts[1].strip():
                    denied_roles = [int(i.strip()) for i in parts[1].split(",") if i.strip().isdigit()]
        except Exception:
            await interaction.response.send_message("⚠️ Virheellinen jäsenrajoitusten muoto.", ephemeral=True)
            return

        rajoitus_str = ""
        if allowed_roles:
            nimet = [interaction.guild.get_role(r_id).mention if interaction.guild.get_role(r_id) else f"<@&{r_id}>" for r_id in allowed_roles]
            rajoitus_str += f"✅ Sallitut roolit: {', '.join(nimet)}\n"
        if denied_roles:
            nimet = [interaction.guild.get_role(r_id).mention if interaction.guild.get_role(r_id) else f"<@&{r_id}>" for r_id in denied_roles]
            rajoitus_str += f"🚫 Estetyt roolit: {', '.join(nimet)}\n"
        if not rajoitus_str:
            rajoitus_str = "🌐 Kaikki voivat äänestää\n"

        numerotemojit = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        embed = Embed(
            title="📊 Äänestys",
            description=f"{self.kysymys.value}\n{rajoitus_str}",
            color=Color.blurple()
        )
        for i, opt in enumerate(options):
            embed.add_field(name=f"{numerotemojit[i]} {opt}", value="\u200b", inline=False)

        aika_str = f"{minutes // 60}h {minutes % 60}min" if minutes >= 60 else f"{minutes}min"
        embed.set_footer(text=f"Päättyy {aika_str}. Luoja: {interaction.user.display_name}")

        poll_data = {
            "channel_id": interaction.channel.id,
            "question": self.kysymys.value,
            "options": options,
            "active": True,
            "allowed_roles": allowed_roles,
            "denied_roles": denied_roles,
            "creator_id": interaction.user.id,
            "votes": {}
        }

        await interaction.response.send_message("✅ Äänestys luotu!", ephemeral=True)

        poll_msg = await interaction.channel.send(embed=embed)
        poll_data["message_id"] = poll_msg.id

        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            db = []
        db.append(poll_data)
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=2)

        view = VoteButtonView(options, poll_data)
        view.message = poll_msg
        await poll_msg.edit(embed=embed, view=view)

        role_id_str = self.rooli_id.value.strip()
        if role_id_str.isdigit():
            role = interaction.guild.get_role(int(role_id_str))
            if role:
                mention_text = role.mention if role.mentionable else f"<@&{role.id}>"
                await interaction.channel.send(f"{mention_text} aika äänestää!")
            else:
                await interaction.channel.send("⚠️ Roolia ei löytynyt tai sitä ei voi tägätä.")

        asyncio.create_task(wait_and_end_poll(self.bot, poll_msg.id, minutes))

async def wait_and_end_poll(client, message_id, minutes):
    await asyncio.sleep(minutes * 60)
    await end_poll(client, message_id)

TROPHY_EMOJI = "🏆"
TIE_EMOJI = "🤝"
NO_WINNER_TEXT = "Ei ääniä"

async def end_poll(bot: commands.Bot, message_id: int):
    try:
        with open(DB_PATH, "r") as f:
            db = json.load(f)
    except FileNotFoundError:
        return

    msg_id = _safe_int(message_id)
    if msg_id is None:
        return

    poll = next((p for p in db if _safe_int(p.get("message_id")) == msg_id and p.get("active")), None)
    if not poll:
        return

    channel = bot.get_channel(poll["channel_id"])
    if not channel:
        return

    try:
        poll_msg = await channel.fetch_message(message_id)
    except Exception:
        poll_msg = None

    if not poll_msg or not poll_msg.embeds:
        poll["active"] = False
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=2)
        return

    base = poll_msg.embeds[0]
    ended_embed = discord.Embed.from_dict(base.to_dict())

    if ended_embed.title and "(Päättynyt)" not in ended_embed.title:
        ended_embed.title = f"{ended_embed.title} (Päättynyt)"
    elif not ended_embed.title:
        ended_embed.title = "(Päättynyt)"

    options = poll["options"]
    numerotemojit = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    counts = {i: 0 for i in range(len(options))}
    buckets = {i: [] for i in range(len(options))}

    for uid, opt_index in poll.get("votes", {}).items():
        if isinstance(opt_index, int) and 0 <= opt_index < len(options):
            counts[opt_index] += 1
            buckets[opt_index].append(uid)

    max_votes = max(counts.values(), default=0)
    winners = [i for i, c in counts.items() if c == max_votes and max_votes > 0]
    is_tie = len(winners) > 1
    has_votes = max_votes > 0

    if not has_votes:
        winner_str = NO_WINNER_TEXT
    else:
        winner_names = ", ".join(options[i] for i in winners)
        winner_str = f"Tasapeli: {winner_names}" if is_tie else f"Voittaja: {winner_names}"

    old_footer = (ended_embed.footer.text or "").strip() if ended_embed.footer else ""
    new_footer = f"{old_footer} • {winner_str}".strip(" •") if old_footer else winner_str
    ended_embed.set_footer(text=new_footer)

    for i, opt in enumerate(options):
        if not has_votes:
            badge = ""
        elif is_tie and i in winners:
            badge = f" {TIE_EMOJI}"
        elif (not is_tie) and i in winners:
            badge = f" {TROPHY_EMOJI}"
        else:
            badge = ""

        name = f"{numerotemojit[i]} {opt} (äänimäärä: {counts[i]}){badge}"

        voters = [f"<@{uid}>" for uid in buckets[i]]
        voters_text = ", ".join(voters) if voters else "*Ei ääniä*"
        value = f"Äänestäjät: {voters_text}"
        if len(value) > 1024:
            value = value[:1020] + "…"

        if i < len(ended_embed.fields):
            ended_embed.set_field_at(i, name=name, value=value, inline=False)
        else:
            ended_embed.add_field(name=name, value=value, inline=False)

    disabled_view = VoteButtonView(options, poll)
    disabled_view.message = poll_msg
    disabled_view.disable_all()

    await poll_msg.edit(embed=ended_embed, view=disabled_view)

    poll["active"] = False
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

class VarmistusView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="✅ Jatka ja luo äänestys", style=discord.ButtonStyle.green)
    async def jatka(self, interaction: Interaction, button: ui.Button):
        try:
            await interaction.response.send_modal(AanestysModal(self.bot))
        except Exception as e:
            print(f"Modalin avaus epäonnistui: {e}")
            await interaction.followup.send(f"⚠️ Modalin avaaminen epäonnistui: {e}", ephemeral=True)

class Aanestys(commands.GroupCog, name="äänestys"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name="uusi", description="Luo uusi äänestys")
    async def uusi(self, interaction: Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/äänestys uusi")
        await kirjaa_ga_event(self.bot, interaction.user.id, "uusi_äänestys_komento")

        await interaction.response.send_message(
            "⚠️ Varmista, että kaikki ID:t on kopioitu oikein ennen jatkamista.\n"
            "- Roolin ID\n- Sallitut jäsen-ID:t\n- Kielletyt jäsen-ID:t",
            view=VarmistusView(self.bot),
            ephemeral=True
        )

    @app_commands.command(name="tulokset", description="Näytä äänestyksen nykytilanne")
    async def tulokset(self, interaction: discord.Interaction, message_id: int):
        await interaction.response.defer(thinking=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/äänestys tulokset")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tulokset_äänestys_komento")

        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            await interaction.followup.send("❌ Äänestystietokantaa ei löytynyt.", ephemeral=True)
            return

        poll = next((p for p in db if str(p["message_id"]) == str(message_id)), None)

        if not poll:
            await interaction.followup.send("❌ Äänestystä ei löytynyt.", ephemeral=True)
            return

        counts = {i: 0 for i in range(len(poll["options"]))}
        for user_id, opt_index in poll.get("votes", {}).items():
            counts[opt_index] += 1

        result = discord.Embed(
            title="📊 Äänestyksen nykytilanne",
            description=poll["question"],
            color=discord.Color.orange()
        )

        for i, count in counts.items():
            result.add_field(name=f"{i + 1}", value=f"{poll['options'][i]} — {count} ääntä", inline=False)

        await interaction.followup.send(embed=result, ephemeral=True)

    @app_commands.command(name="lopetus", description="Lopeta äänestys ennen aikarajaa")
    async def lopetus(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(thinking=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/äänestys lopetus")
        await kirjaa_ga_event(self.bot, interaction.user.id, "lopetus_äänestys_komento")
        
        await end_poll(self.bot, int(message_id))
        await interaction.followup.send("⏹️ Äänestys lopetettu.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    await bot.add_cog(Aanestys(bot))