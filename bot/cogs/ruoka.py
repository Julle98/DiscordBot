import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import requests
from bs4 import BeautifulSoup

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Näyttää uusimmat ruokailuvuorot.")
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")
        await interaction.response.send_message("https://drive.google.com/file/d/1GO1RoNwSxGwP9T8Ta5_zCfyUDmuPZT1r/view?usp=drivesdk")

    @app_commands.command(name="ruoka", description="Näyttää koulun ruokalistan.")
    @app_commands.checks.has_role("24G")
    @app_commands.describe(valinta="Valitse ruokalistan tyyppi")
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/ruoka")
            await kirjaa_ga_event(self.bot, interaction.user.id, "ruoka_komento")

            valinta = valinta.lower()

            if valinta == "päivän ruoka":
                if datetime.now().weekday() >= 5:
                    await interaction.followup.send("Ei ruokana tänään mitään.")  
                    return

                url = "https://aromimenu.cgisaas.fi/VantaaAromieMenus/FI/Default/Vantti/TikkurilaKO/Page/Restaurant"
                try:
                    response = requests.get(url)
                    soup = BeautifulSoup(response.text, 'html.parser')

                    weekday = datetime.now().weekday()  
                    base_id = f"MainContent_WeekdayListView_Meals_{weekday}_Meals_1_SecureLabelDish_"
                    dish_ids = [base_id + str(i) for i in range(3)]  
                    dishes = []

                    for dish_id in dish_ids:
                        span = soup.find("span", id=dish_id)
                        if span:
                            dishes.append(span.text.strip())

                    if dishes:
                        menu_text = "**📆 Päivän ruoka:**\n" + "\n".join(f"• {dish}" for dish in dishes)
                        await interaction.followup.send(menu_text)
                    else:
                        await interaction.followup.send(
                            "Ruoan tietoja ei löytynyt. Tarkista asia [tästä linkistä](https://aromimenu.cgisaas.fi/VantaaAromieMenus/FI/Default/Vantti/TikkurilaKO/Restaurant.aspx) tai yritä uudelleen."
                        )
                except Exception as e:
                    await interaction.followup.send(f"Virhe haettaessa ruokalistaa: {e}")

            elif valinta == "viikon ruoka":
                await interaction.followup.send(
                    "Viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
                )

            elif valinta == "seuraavan viikon ruoka":
                await interaction.followup.send(
                    "Seuraavan viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
                )

            elif valinta == "kolmannen viikon ruoka":
                await interaction.followup.send(
                    "Kolmannen viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
                )

            else:
                await interaction.followup.send("Valintaa ei tunnistettu.")

        except Exception as e:
            await interaction.followup.send(f"Virhe komennon suorittamisessa: {e}", ephemeral=True)

    @ruoka.autocomplete("valinta")
    async def ruoka_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        vaihtoehdot = [
            "päivän ruoka",
            "viikon ruoka",
            "seuraavan viikon ruoka",
            "kolmannen viikon ruoka"
        ]
        return [
            app_commands.Choice(name=v, value=v)
            for v in vaihtoehdot if current.lower() in v.lower()
        ]

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = ruoka(bot)
    await bot.add_cog(cog)