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

class FeedbackModal(ui.Modal, title="📝 Anna palautetta"):
    palaute = ui.TextInput(label="Palaute", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.send_message("Kiitos palautteestasi! 💙", ephemeral=True)

        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📝 Uusi palaute äänestyksestä",
                description=self.palaute.value or "*Ei sisältöä*",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Lähettäjä: {interaction.user} • ID: {interaction.user.id}")
            await log_channel.send(embed=embed)

class FeedbackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Anna palautetta", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeedbackModal())

class VoteButton(discord.ui.Button):
    def __init__(self, index: int, poll_data: dict, parent_view: discord.ui.View):
        self.index = index
        self.poll_data = poll_data
        self.parent_view = parent_view
        super().__init__(label=self._label_with_count(), style=discord.ButtonStyle.primary)

    def _label_with_count(self):
        count = sum(1 for v in self.poll_data["votes"].values() if v == self.index)
        return f"{self.index + 1} ({count} ääntä)"

    def refresh_label(self):
        self.label = self._label_with_count()

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)
            user_role_ids = [r.id for r in interaction.user.roles]

            if any(r in self.poll_data["denied_roles"] for r in user_role_ids):
                msg = "🚫 Et saa äänestää tässä äänestyksessä."
            elif self.poll_data["allowed_roles"] and not any(r in self.poll_data["allowed_roles"] for r in user_role_ids):
                msg = "🚫 Et saa äänestää tässä äänestyksessä."
            elif user_id in self.poll_data["votes"]:
                msg = "ℹ️ Olet jo äänestänyt."
            else:
                self.poll_data["votes"][user_id] = self.index
                self._update_db()
                self._refresh_all_buttons()
                msg = "✅ Äänesi on rekisteröity!"

                log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    embed = discord.Embed(
                        title="✅ Ääni rekisteröity",
                        description=f"{interaction.user} äänesti vaihtoehtoa {self.index + 1}",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text=f"ID: {interaction.user.id}")
                    await log_channel.send(embed=embed)

            view = discord.ui.View()
            view.add_item(FeedbackButton())
            view.add_item(UnvoteButton(self.poll_data, self.parent_view))
            await interaction.response.send_message(msg, ephemeral=True, view=view)
        except Exception as e:
            print(f"VoteButton virhe: {e}")
            await interaction.response.send_message("⚠️ Tapahtui virhe nappulan käsittelyssä.", ephemeral=True)

    def _refresh_all_buttons(self):
        for item in self.parent_view.children:
            if isinstance(item, VoteButton):
                item.refresh_label()
        message = self.parent_view.message
        if message:
            asyncio.create_task(message.edit(view=self.parent_view))

    def _update_db(self):
        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
            for p in db:
                if p["message_id"] == self.poll_data["message_id"]:
                    p["votes"] = self.poll_data["votes"]
            with open(DB_PATH, "w") as f:
                json.dump(db, f, indent=2)
        except Exception:
            pass

class UnvoteButton(discord.ui.Button):
    def __init__(self, poll_data: dict, parent_view: discord.ui.View):
        super().__init__(label="Peru ääni", style=discord.ButtonStyle.danger)
        self.poll_data = poll_data
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.poll_data["votes"]:
            del self.poll_data["votes"][user_id]
            self._update_db()
            self._refresh_all_buttons()
            msg = "❎ Äänesi on peruttu."
        else:
            msg = "ℹ️ Sinulla ei ole aktiivista ääntä."

        view = discord.ui.View()
        view.add_item(FeedbackButton())
        await interaction.response.send_message(msg, ephemeral=True, view=view)

    def _refresh_all_buttons(self):
        for item in self.parent_view.children:
            if isinstance(item, VoteButton):
                item.refresh_label()

    def _update_db(self):
        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
            for p in db:
                if p["message_id"] == self.poll_data["message_id"]:
                    p["votes"] = self.poll_data["votes"]
            with open(DB_PATH, "w") as f:
                json.dump(db, f, indent=2)
        except Exception:
            pass

class VoteButtonView(discord.ui.View):
    def __init__(self, options: list[str], poll_data: dict):
        super().__init__(timeout=None)
        self.message = None  
        for i in range(len(options)):
            self.add_item(VoteButton(index=i, poll_data=poll_data, parent_view=self))

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

        allowed_roles = []
        denied_roles = []
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
        if allowed_roles or denied_roles:
            if allowed_roles:
                nimet = []
                for r_id in allowed_roles:
                    rooli = interaction.guild.get_role(r_id)
                    nimet.append(rooli.mention if rooli else f"<@&{r_id}>")
                rajoitus_str += f"✅ Sallitut roolit: {', '.join(nimet)}\n"

            if denied_roles:
                nimet = []
                for r_id in denied_roles:
                    rooli = interaction.guild.get_role(r_id)
                    nimet.append(rooli.mention if rooli else f"<@&{r_id}>")
                rajoitus_str += f"🚫 Estetyt roolit: {', '.join(nimet)}\n"
        else:
            rajoitus_str = "🌐 Kaikki voivat äänestää\n"

        numerotemojit = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        embed = Embed(
            title="📊 Äänestys",
            description=f"{self.kysymys.value}\n{rajoitus_str}",
            color=Color.blurple()
        )

        for i, opt in enumerate(options):
            emoji = numerotemojit[i]
            embed.add_field(name=f"{emoji} {opt}", value="\u200b", inline=False)

        hours, minutes_rem = divmod(minutes, 60)
        aika_str = f"{hours}h {minutes_rem}min" if hours else f"{minutes_rem}min"
        laatija_str = f"Luoja: {interaction.user.display_name}"
        embed.set_footer(text=f"Päättyy {aika_str}. {laatija_str}")

        poll_data = {
            "message_id": None,
            "channel_id": interaction.channel.id,
            "question": self.kysymys.value,
            "options": options,
            "active": True,
            "allowed_roles": allowed_roles,
            "denied_roles": denied_roles,
            "creator_id": interaction.user.id,
            "votes": {}
        }

        dummy_view = discord.ui.View()

        poll_msg = await interaction.channel.send(embed=embed)
        poll_data["message_id"] = poll_msg.id

        view = VoteButtonView(options, poll_data)
        view.message = poll_msg
        await self.bot.add_view(view)
        await poll_msg.edit(view=view)

        role_id_str = self.rooli_id.value.strip()
        role = None
        if role_id_str.isdigit():
            role_id = int(role_id_str)
            role = interaction.guild.get_role(role_id)

        if role_id_str:
            if role and role.mentionable:
                await interaction.channel.send(f"{role.mention} aika äänestää!")
            elif role:
                await interaction.channel.send(f"<@&{role.id}> aika äänestää!")
            else:
                await interaction.response.send_message("⚠️ Roolia ei löytynyt tai sitä ei voi tägätä.", ephemeral=True)
                return

        hours, minutes_rem = divmod(minutes, 60)
        aika_str = f"{hours}h {minutes_rem}min" if hours else f"{minutes_rem}min"

        member = interaction.user
        user_role_ids = [r.id for r in member.roles]

        poll_data = {
            "message_id": None,
            "channel_id": interaction.channel.id,
            "question": self.kysymys.value,
            "options": options,
            "active": True,
            "allowed_roles": allowed_roles,
            "denied_roles": denied_roles,
            "creator_id": interaction.user.id,
            "votes": {}
        }

        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            db = []

        db.append(poll_data)
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=2)

        await interaction.response.send_message("✅ Äänestys luotu!", ephemeral=True)
        asyncio.create_task(wait_and_end_poll(self.bot, poll_msg.id, minutes))

async def wait_and_end_poll(client, message_id, minutes):
    await asyncio.sleep(minutes * 60)
    await end_poll(client, message_id)

async def end_poll(bot: commands.Bot, message_id: int):
    try:
        with open(DB_PATH, "r") as f:
            db = json.load(f)
    except FileNotFoundError:
        return

    poll = next((p for p in db if p["message_id"] == message_id and p["active"]), None)
    if not poll:
        return

    channel = bot.get_channel(poll["channel_id"])
    if not channel:
        return

    counts = {i: 0 for i in range(len(poll["options"]))}
    for user_id, opt_index in poll.get("votes", {}).items():
        counts[opt_index] += 1

    max_votes = max(counts.values(), default=0)
    winners = [poll["options"][i] for i, c in counts.items() if c == max_votes and max_votes > 0]

    result = discord.Embed(title="📊 Äänestyksen tulokset", description=poll["question"], color=discord.Color.green())
    for i, count in counts.items():
        option = poll["options"][i]
        result.add_field(name=option, value=f"{count} ääntä", inline=True)

    if winners:
        result.add_field(name="🏆 Voittaja(t)", value=", ".join(winners), inline=False)
    else:
        result.add_field(name="🏆 Voittaja(t)", value="Ei ääniä", inline=False)

    await channel.send(embed=result)

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
        await interaction.response.send_message("⏹️ Äänestys lopetettu.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    await bot.add_cog(Aanestys(bot))