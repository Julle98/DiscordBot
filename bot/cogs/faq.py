import discord
from discord.ext import commands
from discord import app_commands
from utils.faq_data import get_embed
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class FAQDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="ℹ️ Yleinen", value="yleinen", description="Yleistä tietoa Sannamaija botista"),
            discord.SelectOption(label="👮 Moderointi", value="moderointi", description="Moderointiominaisuudet"),
            discord.SelectOption(label="🏛️ GDPR & tietosuoja", value="gdpr", description="Tietosuoja ja käyttäjän oikeudet"),
            discord.SelectOption(label="📲 Komennot", value="fun", description="Hauskat komennot ja muut toiminnot"),
            discord.SelectOption(label="⭐ XP systeemi", value="xp", description="Aktiivisuuden palkitseminen ja sen toiminta"),
            discord.SelectOption(label="📊 Tilastot & sijoitukset", value="tilastot", description="Aktiivisuustilastojen katsomiset"),
            discord.SelectOption(label="🧩 Integraatiot", value="integraatiot", description="Mitä palveluita botti käyttää hyväkseen"),
            discord.SelectOption(label="💡 Vinkit parhaaseen käyttöön", value="vinkit", description="Tehokas ja selkeä käyttö"),
            discord.SelectOption(label="🛠️ Kehitys", value="kehitys", description="Tietoa botin kehityksestä"),
            discord.SelectOption(label="📫 Yhteydenotto", value="yhteydenotto", description="Miten ottaa yhteyttä ylläpitoon"),
        ]
        super().__init__(placeholder="Valitse aihe FAQ:sta...", options=options)

    async def callback(self, interaction: discord.Interaction):
        embed = get_embed(self.values[0])
        await interaction.response.edit_message(embed=embed, view=self.view)

class FAQView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FAQDropdown())

class FAQ(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="faq", description="Näytä botin usein kysytyt kysymykset.")
    async def faq(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/faq")
        await kirjaa_ga_event(self.bot, interaction.user.id, "faq_komento")

        await interaction.response.send_message(
            content="📖 Valitse alhaalta olevasta pudotusvalikosta sopiva aihe",
            view=FAQView(),
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    await bot.add_cog(FAQ(bot))