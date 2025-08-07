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
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

async def hae_ruoka(interaction, valinta="päivän ruoka", kasvisvaihtoehto=False):
    try:
        if valinta == "päivän ruoka":
            if datetime.now().weekday() >= 5:
                await interaction.followup.send("Ei ruokana tänään mitään.")
                return

            url = "https://aromimenu.cgisaas.fi/VantaaAromieMenus/FI/Default/Vantti/TikkurilaKO/Page/Restaurant"

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)

            await asyncio.sleep(3)

            labels = driver.find_elements(By.CSS_SELECTOR, "mat-label.labeltext")
            texts = [label.text.strip() for label in labels]

            driver.quit()

            if len(texts) < 8:
                await interaction.followup.send("Ruokalistaa ei löytynyt tai se on puutteellinen.")
                return

            kasvisruuat = [
                f"{texts[0]}, {texts[1]}",
                f"{texts[2]}, {texts[3]}"
            ]

            paivaruoka = [
                f"{texts[4]}, {texts[5]}",
                f"{texts[6]}, {texts[7]}"
            ]

            menu_text = "**📆 Päivän ruoka:**\n"
            for dish in paivaruoka:
                menu_text += f"• {dish}\n"

            if kasvisvaihtoehto:
                menu_text += "\n**🥕 Valinnainen kasvisvaihtoehto:**\n"
                for dish in kasvisruuat:
                    menu_text += f"• {dish}\n"

            await interaction.followup.send(menu_text)

        elif valinta == "viikon ruoka":
            await interaction.followup.send(
                "📅 Viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
            )

        elif valinta == "seuraavan viikon ruoka":
            await interaction.followup.send(
                "📅 Seuraavan viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
            )

        elif valinta == "kolmannen viikon ruoka":
            await interaction.followup.send(
                "📅 Kolmannen viikon ruokalista ei ole vielä saatavilla. Päivitämme sen, kun tiedot julkaistaan."
            )

        else:
            await interaction.followup.send("❓ Valintaa ei tunnistettu.")

    except Exception as e:
        await interaction.followup.send(f"⚠️ Virhe komennon suorittamisessa: {e}", ephemeral=True)

class ruoka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ruokailuvuorot", description="Näyttää uusimmat ruokailuvuorot.")
    @app_commands.checks.has_role("24G")
    async def ruokailuvuorot(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/ruokailuvuorot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "ruokailuvuorot_komento")
        await interaction.response.send_message("https://drive.google.com/file/d/1GO1RoNwSxGwP9T8Ta5_zCfyUDmuPZT1r/view?usp=drivesdk")

    @app_commands.command(name="ruoka", description="Näyttää Tilun ruokalistan.")
    @app_commands.checks.has_role("24G")
    @app_commands.describe(
        valinta="Valitse ruokalistan tyyppi",
        kasvisvaihtoehto="Näytä valinnainen kasvisvaihtoehto"
    )
    async def ruoka(
        self,
        interaction: discord.Interaction,
        valinta: str,
        kasvisvaihtoehto: bool = False
    ):
        await interaction.response.defer()
        await hae_ruoka(interaction, valinta=valinta.lower(), kasvisvaihtoehto=kasvisvaihtoehto)

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