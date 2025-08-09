import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
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

class AanestysModal(ui.Modal, title="📊 Luo uusi äänestys"):
    def __init__(self):
        super().__init__()

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

        self.add_item(self.kysymys)
        self.add_item(self.vaihtoehdot)
        self.add_item(self.aikaraja)

    async def on_submit(self, interaction: Interaction):
        try:
            minutes = int(self.aikaraja.value)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("⚠️ Virheellinen aikaraja.", ephemeral=True)
            return

        options = [opt.strip() for opt in self.vaihtoehdot.value.split(",") if opt.strip()]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        if not 2 <= len(options) <= 5:
            await interaction.response.send_message("⚠️ Anna 2–5 vaihtoehtoa.", ephemeral=True)
            return

        embed = Embed(title="📊 Äänestys", description=self.kysymys.value, color=Color.blurple())
        for i, opt in enumerate(options):
            embed.add_field(name=emojis[i], value=opt, inline=False)
        embed.set_footer(text=f"Päättyy {minutes} minuutissa.")

        poll_msg = await interaction.channel.send(embed=embed)
        for emoji in emojis[:len(options)]:
            await poll_msg.add_reaction(emoji)

        role = discord.utils.get(interaction.guild.roles, name="Mr. Vastaaja")
        if role and role.mentionable:
            await interaction.channel.send(f"{role.mention} aika äänestää!")
        else:
            await interaction.channel.send("@Mr. Vastaaja aika äänestää!")

        await interaction.response.send_message("✅ Äänestys luotu!", ephemeral=True)

        poll_data = {
            "message_id": poll_msg.id,
            "channel_id": poll_msg.channel.id,
            "question": self.kysymys.value,
            "options": options,
            "emojis": emojis[:len(options)],
            "active": True
        }

        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            db = []

        db.append(poll_data)
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=2)

        asyncio.create_task(wait_and_end_poll(interaction.client, poll_msg.id, minutes))

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
    message = await channel.fetch_message(poll["message_id"])
    counts = {emoji: 0 for emoji in poll["emojis"]}

    for reaction in message.reactions:
        if str(reaction.emoji) in counts:
            counts[str(reaction.emoji)] = reaction.count - 1

    max_votes = max(counts.values())
    winners = [poll["options"][poll["emojis"].index(e)] for e, c in counts.items() if c == max_votes]

    result = discord.Embed(title="📊 Äänestyksen tulokset", description=poll["question"], color=discord.Color.green())
    for emoji, count in counts.items():
        result.add_field(name=emoji, value=f"{count} ääntä", inline=True)
    result.add_field(name="🏆 Voittaja(t)", value=", ".join(winners), inline=False)

    await channel.send(embed=result)

    poll["active"] = False
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

class Aanestys(commands.GroupCog, name="äänestys"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="uusi", description="Luo uusi äänestys")
    async def uusi(self, interaction: Interaction):
        await interaction.response.send_modal(AanestysModal())

        asyncio.create_task(kirjaa_komento_lokiin(self.bot, interaction, "/äänestys uusi"))
        asyncio.create_task(kirjaa_ga_event(self.bot, interaction.user.id, "uusi_äänestys_komento"))

    @app_commands.command(name="tulokset", description="Näytä äänestyksen nykytilanne")
    async def tulokset(self, interaction: discord.Interaction, message_id: int):
        await interaction.response.defer(thinking=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/äänestys tulokset")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tulokset_äänestys_komento")
        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            await interaction.response.send_message("❌ Äänestystietokantaa ei löytynyt.", ephemeral=True)
            return

        poll = next((p for p in db if str(p["message_id"]) == message_id), None)
        if not poll:
            await interaction.response.send_message("❌ Äänestystä ei löytynyt.", ephemeral=True)
            return

        channel = self.bot.get_channel(poll["channel_id"])
        message = await channel.fetch_message(poll["message_id"])
        counts = {emoji: 0 for emoji in poll["emojis"]}

        for reaction in message.reactions:
            if str(reaction.emoji) in counts:
                counts[str(reaction.emoji)] = reaction.count - 1  

        result = discord.Embed(title="📊 Äänestyksen nykytilanne", description=poll["question"], color=discord.Color.orange())
        for emoji, count in counts.items():
            option = poll["options"][poll["emojis"].index(emoji)]
            result.add_field(name=f"{emoji} {option}", value=f"{count} ääntä", inline=False)

        await interaction.response.send_message(embed=result, ephemeral=True)

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

    @bot.event
    async def on_raw_reaction_add(payload):
        try:
            with open(DB_PATH, "r") as f:
                db = json.load(f)
        except FileNotFoundError:
            return

        poll = next((p for p in db if p["message_id"] == payload.message_id and p["active"]), None)
        if not poll or str(payload.emoji.name) not in poll["emojis"]:
            return

        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)

        if member and not member.bot:
            await log_channel.send(f"🗳️ {member.mention} äänesti **{poll['question']}** reaktiolla {payload.emoji.name}")