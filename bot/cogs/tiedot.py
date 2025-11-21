import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.tiedot_utils import KategoriaView
from bot.utils.tiedot_utils import DataValintaView
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from typing import Optional

class TiedotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tiedot", description="Näytä oma tai toisen käyttäjän bottidata.")
    @app_commands.describe(
        käyttäjä="(vain Mestari) Näytä toisen käyttäjän tiedot.",
        ohje="Näytä ohjeet tieto komentoon. Näyttää vain ohjeet, ei tietoja (valinnainen)"
    )
    async def tiedot(self, interaction: discord.Interaction, käyttäjä: discord.User = None, ohje: Optional[bool] = False):
        await kirjaa_komento_lokiin(self.bot, interaction, "/tiedot")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tiedot_komento")
        await interaction.response.defer(ephemeral=True)

        if käyttäjä and not any(r.name == "Mestari" for r in interaction.user.roles):
            await interaction.followup.send("⚠️ Sinulla ei ole oikeuksia tarkastella muiden tietoja.", ephemeral=True)
            return

        target = käyttäjä or interaction.user

        if ohje:
            embed = discord.Embed(
                title="📘 Bottitietojen katselu ja hallinta",
                description="Näet eri kategorioihin jaoteltuna sinusta tallennetut tiedot. Voit pyytää tiedot ladattavaksi tai poistettavaksi.\nBottin tallentamat tiedot noudattavat EU:n yleistä tietosuoja-asetusta (**GDPR**) sekä muita soveltuvia lakeja.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="🗂️ Tietokategoriat",
                value=(
                    "• 🧩 Tehtävät – suoritetut tehtävät ja armojen käyttö\n"
                    "• 🛒 Ostokset – ostohistoria ja tuotteet\n"
                    "• 🎟️ Kupongit – käytetyt alennuskoodit\n"
                    "• 🎯 Tarjous – kampanjatuotteiden käytöt\n"
                    "• 🛡️ Moderointi – varoitukset ja valvontatiedot\n"
                    "• 🔁 Streakit – päivittäiset, viikoittaiset, kuukausittaiset\n"
                    "• 💬 Puhe-streak – viestien jatkuvuus\n"
                    "• ⭐ XP-data – kertyneet kokemuspisteet\n"
                    "• 🧍 Osallistumiset – äänestykset ja voitot\n"
                    "• ⚙️ Toiminta – aktiivisuus teksti ja puhekanavilla\n"
                    "• ⌨️ Komennot – käytetyt komennot ja milloin\n\n"
                ),
                inline=False
            )
            embed.add_field(
                name="📲 Tietojen lataaminen",
                value=(
                    "• Voit pyytää tiedot ladattavaksi kategoriakohtaisesti.\n"
                    "• Lataus tapahtuu erikseen moderaattoreiden tarkistamana – botti ilmoittaa kun tiedosto on valmis yksityisviestinä.\n"
                    "• Kaikki tiedot eivät ole tarkkoja, vaan osa perustuu arvioon tai vuorovaikutukseen."
                ),
                inline=False
            )
            embed.add_field(
                name="🗑️ Tietojen poistaminen",
                value=(
                    "• Voit poistaa yksittäisiä kategorioita tai koko datan.\n"
                    "• Poisto tapahtuu manuaalisesti moderaattoreiden kautta ja on pysyvä.\n"
                    "• Arvioitu tieto ei aina ole tallennettua – voit pyytää sen unohtamista erikseen."
                ),
                inline=False
            )
            embed.add_field(
                name="⁉️ Huomioitavaa",
                value=(
                    "• Tiedot eivät ole julkisia – vain sinä näet omasi.\n"
                    "• Tietojasi ei myydä minnekkään ja ne pidetään tallessa kaikelta.\n"
                    "• Jos haluat kaiken datan ladattavaksi tai poistettavaksi kerralla, käytä `/help` ja ota yhteyttä ylläpitoon."
                ),
                inline=False
            )
            embed.set_footer(text="Tietosi ovat sinun. Voit hallita niitä vapaasti. ☺️")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.followup.send(
            content="📁 Valitse kategoria, jonka tiedot haluat nähdä tai hallita:\n"
                    "-# Jos haluat kaiken datan ladattavaksi tai poistettavaksi, käytä `/help` ja ota yhteyttä.",
            view=KategoriaView(target, valittu=None, alkuperäinen_käyttäjä=interaction.user),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(TiedotCog(bot))