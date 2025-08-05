import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from dotenv import load_dotenv
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler

load_dotenv()
DB_PATH = os.getenv("POLLS_JSON_PATH")
LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))

class AanestysModal(discord.ui.Modal, title="Luo uusi äänestys"):
    def __init__(self):
        super().__init__()

        self.kysymys = discord.ui.TextInput(label="Äänestyksen otsikko")
        self.vaihtoehto1 = discord.ui.TextInput(label="Vaihtoehto 1")
        self.vaihtoehto2 = discord.ui.TextInput(label="Vaihtoehto 2")
        self.vaihtoehto3 = discord.ui.TextInput(label="Vaihtoehto 3", required=False)
        self.vaihtoehto4 = discord.ui.TextInput(label="Vaihtoehto 4", required=False)
        self.vaihtoehto5 = discord.ui.TextInput(label="Vaihtoehto 5", required=False)
        self.aikaraja = discord.ui.TextInput(label="Aikaraja (min)", placeholder="Esim. 5")

        self.add_item(self.kysymys)
        self.add_item(self.vaihtoehto1)
        self.add_item(self.vaihtoehto2)
        self.add_item(self.vaihtoehto3)
        self.add_item(self.vaihtoehto4)
        self.add_item(self.vaihtoehto5)
        self.add_item(self.aikaraja)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.aikaraja.value)
        except ValueError:
            await interaction.response.send_message("⚠️ Virheellinen aikaraja.", ephemeral=True)
            return

        options = [self.vaihtoehto1.value, self.vaihtoehto2.value]
        emojis = ["1️⃣", "2️⃣"]
        if self.vaihtoehto3.value: options.append(self.vaihtoehto3.value); emojis.append("3️⃣")
        if self.vaihtoehto4.value: options.append(self.vaihtoehto4.value); emojis.append("4️⃣")
        if self.vaihtoehto5.value: options.append(self.vaihtoehto5.value); emojis.append("5️⃣")

        embed = discord.Embed(title="📊 Äänestys", description=self.kysymys.value, color=discord.Color.blurple())
        for i, opt in enumerate(options):
            embed.add_field(name=emojis[i], value=opt, inline=False)
        embed.set_footer(text=f"Päättyy {minutes} minuutissa.")

        poll_msg = await interaction.channel.send(embed=embed)
        for emoji in emojis:
            await poll_msg.add_reaction(emoji)

        await interaction.channel.send("@Mr. Vastaaja aika äänestää!")
        await interaction.response.send_message("✅ Äänestys luotu!", ephemeral=True)

        poll_data = {
            "message_id": poll_msg.id,
            "channel_id": poll_msg.channel.id,
            "question": self.kysymys.value,
            "options": options,
            "emojis": emojis,
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

        await asyncio.sleep(minutes * 60)
        await end_poll(interaction.client, poll_msg.id)

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

class AanestysCog(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="äänestys", description="Äänestystoiminnot")
        self.bot = bot

    @app_commands.command(name="uusi", description="Luo uusi äänestys")
    async def uusi(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await kirjaa_komento_lokiin(self.bot, interaction, "/äänestys uusi")
        await kirjaa_ga_event(self.bot, interaction.user.id, "uusi_äänestys_komento")
        await interaction.response.send_modal(AanestysModal())

    @app_commands.command(name="tulokset", description="Näytä äänestyksen nykytilanne")
    async def tulokset(self, interaction: discord.Interaction, message_id: str):
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
    cog = AanestysCog(bot)
    await bot.add_cog(cog)

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