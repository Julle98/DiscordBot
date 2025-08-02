import discord
from discord.ext import commands
import asyncio
from ..config import (
    EVENT_CHANNEL_ID, PRESENTATION_CHANNEL_ID, VOICE_CHANNEL_ID, PREFIX
)
from ..utils.event_data_manager import EventDataManager, get_random_joke 

class AnswerModal(discord.ui.Modal):
    def __init__(self, bot, data_manager):
        super().__init__(title="Lähetä vastauksesi")
        self.bot = bot
        self.data_manager = data_manager

        self.answer = discord.ui.TextInput(
            label="Vastauksesi",
            style=discord.TextStyle.paragraph,
            placeholder="Kirjoita vastauksesi tähän...",
            required=True,
            max_length=500
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)

        if not self.data_manager.is_round_active():
            await interaction.response.send_message("Ei aktiivista kierrosta juuri nyt.", ephemeral=True)
            return

        if user_id_str in self.data_manager.get_submissions():
            await interaction.response.send_message("Olet jo lähettänyt vastauksen tällä kierroksella.", ephemeral=True)
            return

        self.data_manager.add_submission(interaction.user.id, interaction.user.display_name, self.answer.value)
        await interaction.response.send_message(f"Vastauksesi vastaanotettu: '{self.answer.value}'", ephemeral=True)

        event_channel = self.bot.get_channel(EVENT_CHANNEL_ID)
        if event_channel:
            await event_channel.send(f"{interaction.user.mention} vastannut!")

class EventCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = EventDataManager()
        self.event_channel = None
        self.presentation_channel = None
        self.voice_channel = None
        self.round_topics = [
            {"name": "Paras vitsi", "description": "Keksi paras vitsi !vitsikone-komennolla tai omasta päästäsi.", "example_cmd": "!vitsikone"},
            {"name": "Uusin ja ihmeellisin fakta", "description": "Keksi uusin ja ihmeellisin fakta.", "example_cmd": "Ei erityistä komentoa."},
            {"name": "Paras asia Discordissa", "description": "Mikä on mielestäsi paras asia Discordissa?", "example_cmd": "Ei erityistä komentoa."},
            {"name": "Hauskin/hyödyllisin uusi bottikomento", "description": "Mikä olisi hauskin tai hyödyllisin uusi bottikomento?", "example_cmd": "Ei erityistä komentoa."}
        ]
        self.current_topic = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.event_channel = self.bot.get_channel(EVENT_CHANNEL_ID)
        self.presentation_channel = self.bot.get_channel(PRESENTATION_CHANNEL_ID)
        self.voice_channel = self.bot.get_channel(VOICE_CHANNEL_ID)
        if not self.event_channel:
            print(f"Varoitus: Event-kanavaa ID {EVENT_CHANNEL_ID} ei löytynyt!")
        if not self.presentation_channel:
            print(f"Varoitus: Esityskanavaa ID {PRESENTATION_CHANNEL_ID} ei löytynyt!")
        if not self.voice_channel:
            print(f"Varoitus: Puhekanavaa ID {VOICE_CHANNEL_ID} ei löytynyt!")


    @commands.command(name='kierros', help='Aloittaa uuden event-kierroksen.')
    @commands.has_permissions(manage_channels=True) 
    async def start_round(self, ctx):
        if ctx.channel.id != EVENT_CHANNEL_ID:
            await ctx.send(f"Tämä komento toimii vain #{self.event_channel.name} kanavalla.")
            return

        if self.data_manager.is_round_active() or self.data_manager.is_voting_active():
            await ctx.send("Kierros on jo käynnissä tai äänestys on aktiivinen. Lopeta ensin aiempi kierros `!päätös` -komennolla.")
            return

        import random
        self.current_topic = random.choice(self.round_topics)
        self.data_manager.set_round_active(self.current_topic['name'])

        embed = discord.Embed(
            title=f"Kierros alkaa: {self.current_topic['name']}",
            description=f"{self.current_topic['description']}\n\nLähetä vastauksesi minulle **yksityisviestillä** komennolla `{PREFIX}vastaus [vastauksesi]`.",
            color=discord.Color.blue()
        )
        if self.current_topic['example_cmd'] != "Ei erityistä komentoa.":
            embed.add_field(name="Esimerkkikomento", value=f"Voit kokeilla esim. `{self.current_topic['example_cmd']}`", inline=False)
        embed.set_footer(text="Aikaa vastauksen lähettämiseen on kunnes juontaja käyttää !päätös komentoa.")
        await self.event_channel.send(embed=embed)


    @commands.command(name='päätös', help='Lopettaa vastausten vastaanoton ja sulkee kirjoitusoikeuden.')
    @commands.has_permissions(manage_channels=True)
    async def end_submission(self, ctx):
        if ctx.channel.id != EVENT_CHANNEL_ID:
            await ctx.send(f"Tämä komento toimii vain #{self.event_channel.name} kanavalla.")
            return

        if not self.data_manager.is_round_active():
            await ctx.send("Ei aktiivista vastaustenkeräyskierrosta.")
            return

        self.data_manager.end_round_submission()
        await self.event_channel.send("Vastausaika päättynyt! Uusia vastauksia ei oteta vastaan.")

        await self.event_channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"Kirjoitusoikeudet poistettu #{self.event_channel.name} kanavalta.")


    @commands.command(name='esitys', help='Aloittaa kerättyjen vastausten esityksen.')
    @commands.has_permissions(manage_channels=True)
    async def start_presentation(self, ctx):
        if ctx.channel.id != EVENT_CHANNEL_ID:
            await ctx.send(f"Tämä komento toimii vain #{self.event_channel.name} kanavalla.")
            return

        submissions = self.data_manager.get_submissions()
        if not submissions:
            await ctx.send("Ei vastauksia esitettäväksi.")
            return

        if not self.presentation_channel:
            await ctx.send("Esityskanavaa ei ole määritelty tai löydetty. Tarkista config.py!")
            return
        
        await self.event_channel.send(f"Siirrythän #{self.presentation_channel.name} kanavalle katsomaan ja kuuntelemaan vastauksia!")

        if self.voice_channel and not self.bot.voice_clients: 
            try:
                await self.voice_channel.connect()
                await ctx.send(f"Yhdistin puhekanavaan {self.voice_channel.name} TTS-esitystä varten.")
            except discord.ClientException as e:
                await ctx.send(f"Virhe yhdistäessä puhekanavaan: {e}")
                self.voice_channel = None 

        await asyncio.sleep(2) 

        for user_id, submission_data in submissions.items():
            username = submission_data["username"]
            content = submission_data["content"]
            message_content = f"**{username}** vastaus: {content}"
            
            await self.presentation_channel.send(message_content)

            if self.bot.voice_clients and self.bot.voice_clients[0].channel.id == self.voice_channel.id:
                try:
                    
                    await self.presentation_channel.send(message_content, tts=True)
                    
                    await asyncio.sleep(len(message_content) / 10 + 2) 
                except discord.HTTPException as e:
                    print(f"TTS virhe: {e}")
                    
            
            await asyncio.sleep(5) 

        await self.event_channel.send("Kaikki vastaukset esitetty! Voitte nyt siirtyä äänestämään.")

        if self.bot.voice_clients:
            await self.bot.voice_clients[0].disconnect()


    @commands.command(name='voittaja', help='Aloittaa äänestyksen ja palauttaa kirjoitusoikeudet.')
    @commands.has_permissions(manage_channels=True)
    async def start_voting(self, ctx):
        if ctx.channel.id != EVENT_CHANNEL_ID:
            await ctx.send(f"Tämä komento toimii vain #{self.event_channel.name} kanavalla.")
            return

        if self.data_manager.is_voting_active():
            await ctx.send("Äänestys on jo aktiivinen.")
            return

        self.data_manager.set_voting_active(True)
        await self.event_channel.send("Äänestys alkaa! Palauta kirjoitusoikeudet. Äänestä suosikkiasi **@mentionilla** komennolla:\n`!äänestä @Käyttäjänimi`.")
        
        await self.event_channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"Kirjoitusoikeudet palautettu #{self.event_channel.name} kanavalle.")

    @commands.command(name='tulokset', help='Näyttää äänestystulokset.')
    @commands.has_permissions(manage_channels=True)
    async def show_results(self, ctx):
        if ctx.channel.id != EVENT_CHANNEL_ID:
            await ctx.send(f"Tämä komento toimii vain #{self.event_channel.name} kanavalla.")
            return
            
        if not self.data_manager.is_voting_active():
            await ctx.send("Äänestys ei ole aktiivinen.")
            return

        vote_counts = self.data_manager.get_vote_counts()
        if not vote_counts:
            await ctx.send("Ääniä ei ole vielä annettu.")
            return

        results_msg = "Äänestystulokset:\n"
        sorted_results = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)

        winner_id = None
        highest_votes = 0

        for user_id_str, count in sorted_results:
            user = self.bot.get_user(int(user_id_str))
            username = user.display_name if user else f"Tuntematon käyttäjä (ID: {user_id_str})"
            results_msg += f"- {username}: {count} ääntä\n"
            
            if count > highest_votes:
                highest_votes = count
                winner_id = user_id_str
            elif count == highest_votes and winner_id is not None:
                winner_id = "Tasa" 

        await ctx.send(results_msg)

        if winner_id == "Tasa":
            await ctx.send("Kilpailu päättyi tasapeliin!")
        elif winner_id:
            winner_user = self.bot.get_user(int(winner_id))
            if winner_user:
                await ctx.send(f"Ja voittaja on... **{winner_user.display_name}**! Onnittelut!")
            else:
                await ctx.send(f"Ja voittaja on... käyttäjä ID:llä **{winner_id}**! Onnittelut!")

        self.data_manager.reset_round()
        await self.event_channel.send("Event-tiedot nollattu seuraavaa kierrosta varten.")

    @commands.command(name='vastaus', help='Avaa lomakkeen vastauksen lähettämistä varten.')
    async def submit_answer(self, ctx):
        if not self.data_manager.is_round_active():
            await ctx.send("Tällä hetkellä ei ole aktiivista event-kierrosta.")
            return

        await ctx.send("Avaan lomakkeen vastauksesi lähettämistä varten...", delete_after=5)
        await ctx.send_modal(AnswerModal(self.bot, self.data_manager))

    @commands.command(name='vitsikone', help='Antaa sinulle vitsin (esim. harjoituskierrokselle).')
    async def joke_machine(self, ctx):
        joke = get_random_joke()
        await ctx.send(f"Tässä sinulle vitsi: {joke}")
        
    @commands.command(name='äänestä', help='Äänestä suosikkiasi @mentionilla.')
    async def vote(self, ctx, member: discord.Member):
        if not self.data_manager.is_voting_active():
            await ctx.send("Äänestys ei ole tällä hetkellä käynnissä.")
            return
        
        if member.bot:
            await ctx.send("Et voi äänestää bottia.")
            return
        
        if member.id == ctx.author.id:
            await ctx.send("Et voi äänestää itseäsi!")
            return

        if str(member.id) not in self.data_manager.get_submissions():
            await ctx.send("Voit äänestää vain niitä käyttäjiä, jotka ovat osallistuneet tällä kierroksella.")
            return

        self.data_manager.add_vote(ctx.author.id, member.id)
        await ctx.send(f"Kiitos! Olet äänestänyt käyttäjää {member.display_name}.")

    @commands.command(name='testi', help='Testaa koko event-prosessi botilla ja yhdellä testikäyttäjällä.')
    @commands.has_permissions(manage_channels=True)
    async def run_test(self, ctx):
        await self.start_round(ctx)

        class MockUser:
            def __init__(self, id, name):
                self.id = id
                self.display_name = name
                self.mention = f"<@{id}>"

        test_user = MockUser(1234567890, "Testikäyttäjä")

        self.data_manager.add_submission(test_user.id, test_user.display_name, "Tämä on testivastaus.")

        await ctx.send(f"{test_user.mention} lähetti testivastauksen.")

        await self.end_submission(ctx)

        await self.start_presentation(ctx)

        await self.start_voting(ctx)

        self.data_manager.add_vote(ctx.author.id, test_user.id)
        await ctx.send(f"{ctx.author.mention} äänesti käyttäjää {test_user.display_name}.")

        await self.show_results(ctx)

        await ctx.send("✅ Testi valmis! Kaikki vaiheet suoritettu.")

async def setup(bot):
    await bot.add_cog(EventCommands(bot))