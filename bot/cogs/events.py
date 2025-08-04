import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from collections import Counter
import os
from ..config import (
    EVENT_CHANNEL_ID, PRESENTATION_CHANNEL_ID, VOICE_CHANNEL_ID,
    EVENT_WINNER_ROLE_ID, EVENT_PARTICIPANT_ROLE_ID
)
from ..utils.event_data_manager import EventDataManager, get_random_joke

class EventCommands(commands.GroupCog, name="event"):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = EventDataManager()
        self.event_channel = None
        self.presentation_channel = None
        self.voice_channel = None
        self.round_topics = [
            {"name": "Paras vitsi", "description": "Keksi paras vitsi /event vitsikone -komennolla tai omasta päästäsi.", "example_cmd": "/event vitsikone"},
            {"name": "Uusin ja ihmeellisin fakta", "description": "Keksi uusin ja ihmeellisin fakta.", "example_cmd": "-"},
            {"name": "Paras asia Discordissa", "description": "Mikä on mielestäsi paras asia Discordissa?", "example_cmd": "-"},
            {"name": "Hauskin/hyödyllisin uusi bottikomento", "description": "Mikä olisi hauskin tai hyödyllisin uusi bottikomento?", "example_cmd": "-"}
        ]
        self.current_topic = None
        self.vote_history = Counter()

    async def cog_load(self):
        self.event_channel = self.bot.get_channel(EVENT_CHANNEL_ID)
        self.presentation_channel = self.bot.get_channel(PRESENTATION_CHANNEL_ID)
        self.voice_channel = self.bot.get_channel(VOICE_CHANNEL_ID)

    @app_commands.command(name="kierros", description="Aloittaa uuden event-kierroksen.")
    @app_commands.checks.has_role("Mestari")
    async def kierros(self, interaction: discord.Interaction):
        if interaction.channel_id != EVENT_CHANNEL_ID:
            await interaction.response.send_message("Tämä komento toimii vain event-kanavalla.", ephemeral=True)
            return

        if self.data_manager.is_round_active() or self.data_manager.is_voting_active():
            await interaction.response.send_message("Kierros on jo käynnissä tai äänestys aktiivinen.", ephemeral=True)
            return

        import random
        self.current_topic = random.choice(self.round_topics)
        self.data_manager.set_round_active(self.current_topic['name'])

        embed = discord.Embed(
            title=f"Kierros alkaa: {self.current_topic['name']}",
            description=f"{self.current_topic['description']}",
            color=discord.Color.blue()
        )
        if self.current_topic['example_cmd'] != "-":
            embed.add_field(name="Esimerkkikomento", value=f"Voit kokeilla esim. `{self.current_topic['example_cmd']}`", inline=False)
        embed.set_footer(text="Aikaa vastauksen lähettämiseen on kunnes juontaja käyttää /event päätös komentoa.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="päätös", description="Lopettaa vastausten vastaanoton.")
    @app_commands.checks.has_role("Mestari")
    async def päätös(self, interaction: discord.Interaction):
        if interaction.channel_id != EVENT_CHANNEL_ID:
            await interaction.response.send_message("Tämä komento toimii vain event-kanavalla.", ephemeral=True)
            return

        if not self.data_manager.is_round_active():
            await interaction.response.send_message("Ei aktiivista kierrosta.", ephemeral=True)
            return

        self.data_manager.end_round_submission()
        await interaction.channel.send("Vastausaika päättynyt! Uusia vastauksia ei oteta vastaan.")

    @app_commands.command(name="vastaus", description="Lähetä oma vastauksesi lomakkeella.")
    @app_commands.checks.has_role("Event kesä ´25 osallistuja")
    async def vastaus(self, interaction: discord.Interaction):
        if not self.data_manager.is_round_active():
            await interaction.response.send_message("Ei aktiivista kierrosta juuri nyt.", ephemeral=True)
            return

        class AnswerModal(discord.ui.Modal, title="Lähetä vastauksesi"):
            vastaus_input = discord.ui.TextInput(label="Vastauksesi", style=discord.TextStyle.paragraph, max_length=500)

            async def on_submit(modal_self, modal_interaction: discord.Interaction):
                uid = str(modal_interaction.user.id)
                if uid in self.data_manager.get_submissions():
                    await modal_interaction.response.send_message("Olet jo vastannut.", ephemeral=True)
                    return

                self.data_manager.add_submission(modal_interaction.user.id, modal_interaction.user.display_name, modal_self.vastaus_input.value)
                await modal_interaction.response.send_message(f"Vastauksesi vastaanotettu: '{modal_self.vastaus_input.value}'", ephemeral=True)

        await interaction.response.send_modal(AnswerModal())

    @app_commands.command(name="vitsikone", description="Saat satunnaisen vitsin.")
    @app_commands.checks.has_role("Event kesä ´25 osallistuja")
    async def vitsikone(self, interaction: discord.Interaction):
        await interaction.response.send_message(get_random_joke())

    @app_commands.command(name="ohje", description="Näyttää ohjeet event-komennoille.")
    @app_commands.checks.has_role("Event kesä ´25 osallistuja")
    async def ohje(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Event-komennot", color=discord.Color.green())
        embed.add_field(name="/event kierros", value="Aloita uusi kierros aiheen arvonnalla.", inline=False)
        embed.add_field(name="/event vastaus", value="Lähetä oma vastauksesi lomakkeella.", inline=False)
        embed.add_field(name="/event päätös", value="Lopeta vastausten vastaanotto.", inline=False)
        embed.add_field(name="/event vitsikone", value="Saat satunnaisen vitsin.", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="läpikäynti", description="Käy läpi vastaukset yksitellen reagoimalla.")
    @app_commands.checks.has_role("Mestari")
    async def läpikäynti(self, interaction: discord.Interaction):
        submissions = list(self.data_manager.get_submissions().items())
        if not submissions:
            await interaction.response.send_message("Ei vastauksia läpikäytäväksi.", ephemeral=True)
            return

        await interaction.response.send_message("Aloitetaan vastausten läpikäynti...", ephemeral=True)

        for user_id, data in submissions:
            user = self.bot.get_user(int(user_id))
            content = data['content']
            msg = await interaction.channel.send(f"**{user.display_name if user else 'Tuntematon'}**: {content}")
            await msg.add_reaction("➡️")

            def check(reaction, user_reactor):
                return user_reactor == interaction.user and str(reaction.emoji) == "➡️" and reaction.message.id == msg.id

            try:
                await self.bot.wait_for("reaction_add", check=check, timeout=120)
            except asyncio.TimeoutError:
                await interaction.channel.send("Läpikäynti aikakatkaistiin.")
                break

    @app_commands.command(name="loppu", description="Päättää eventin ja näyttää top-3 osallistujaa.")
    @app_commands.checks.has_role("Mestari")
    async def loppu(self, interaction: discord.Interaction):
        all_votes = self.data_manager.get_vote_counts()
        if not all_votes:
            await interaction.response.send_message("Ei ääniä koottu kierroksilta.", ephemeral=True)
            return

        sorted_votes = sorted(all_votes.items(), key=lambda x: x[1], reverse=True)
        top_three = sorted_votes[:3]
        others = sorted_votes[3:]

        top_lines = []
        for i, (uid, count) in enumerate(top_three, 1):
            user = interaction.guild.get_member(int(uid))
            top_lines.append(f"{i}. {user.display_name if user else 'Tuntematon'} – {count} ääntä")
            if i == 1 and user:
                winner_role = interaction.guild.get_role(EVENT_WINNER_ROLE_ID)
                if winner_role:
                    await user.add_roles(winner_role, reason="Event-voittaja")

        other_lines = []
        for uid, count in others:
            user = interaction.guild.get_member(int(uid))
            other_lines.append(f"{user.display_name if user else 'Tuntematon'} – {count} ääntä")

        msg = "🎉 **Event päättynyt, kiitos kaikille pelaajille!**\n\n"
        msg += "**Top-3 tänään:**\n" + "\n".join(top_lines)
        if other_lines:
            msg += "\n\n**Loput osallistujat:**\n" + "\n".join(other_lines)

        await interaction.response.send_message(msg)

    @app_commands.command(name="lukitus", description="Antaa osallistujaroolin puhekanavalla oleville.")
    @app_commands.checks.has_role("Mestari")
    async def lukitus(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Komento toimii vain palvelimella.", ephemeral=True)
            return

        voice_channel = interaction.guild.get_channel(VOICE_CHANNEL_ID)
        if not voice_channel or not voice_channel.members:
            await interaction.response.send_message("Puhekanava on tyhjä tai ei löytynyt.", ephemeral=True)
            return

        participant_role = interaction.guild.get_role(EVENT_PARTICIPANT_ROLE_ID)
        if not participant_role:
            await interaction.response.send_message("Osallistujaroolia ei löytynyt.", ephemeral=True)
            return

        for member in voice_channel.members:
            if not member.bot:
                await member.add_roles(participant_role, reason="Event-lukitus")

        await interaction.response.send_message(f"Rooli **{participant_role.name}** lisätty {len(voice_channel.members)} osallistujalle.")

async def setup(bot):
    await bot.add_cog(EventCommands(bot))