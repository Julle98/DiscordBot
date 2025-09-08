import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.settings_utils import get_user_settings, save_user_settings

class Asetukset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="asetukset", description="Muuta XP-asetuksiasi")
    async def asetukset(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        settings = get_user_settings(user_id)

        def format_status(value: bool) -> str:
            return "✅ Päällä" if value else "❌ Pois"

        embed = discord.Embed(
            title="⚙️ XP-asetuksesi",
            color=discord.Color.blurple()
        )
        embed.add_field(name="XP viesteistä", value=format_status(settings["xp_viestit"]), inline=False)
        embed.add_field(name="XP puhekanavalta", value=format_status(settings["xp_puhe"]), inline=False)
        embed.add_field(name="XP komennoista", value=format_status(settings["xp_komennot"]), inline=False)
        embed.add_field(name="XP bonus epäaktiivisuudesta", value=format_status(settings["xp_epaaktiivisuus"]), inline=False)

        options = [
            discord.SelectOption(label="XP viesteistä", value="xp_viestit", default=settings["xp_viestit"]),
            discord.SelectOption(label="XP puhekanavalta", value="xp_puhe", default=settings["xp_puhe"]),
            discord.SelectOption(label="XP komennoista", value="xp_komennot", default=settings["xp_komennot"]),
            discord.SelectOption(label="XP bonus epäaktiivisuudesta", value="xp_epaaktiivisuus", default=settings["xp_epaaktiivisuus"]),
        ]

        select = discord.ui.Select(
            placeholder="Valitse käytössä olevat XP-lähteet",
            min_values=0,
            max_values=4,
            options=options
        )

        async def select_callback(inter: discord.Interaction):
            new_settings = {k: (k in select.values) for k in settings.keys()}
            settings.update(new_settings)
            save_user_settings()

            updated_embed = discord.Embed(
                title="⚙️ XP-asetuksesi (päivitetty)",
                color=discord.Color.green()
            )
            updated_embed.add_field(name="XP viesteistä", value=format_status(settings["xp_viestit"]), inline=False)
            updated_embed.add_field(name="XP puhekanavalta", value=format_status(settings["xp_puhe"]), inline=False)
            updated_embed.add_field(name="XP komennoista", value=format_status(settings["xp_komennot"]), inline=False)
            updated_embed.add_field(name="XP bonus epäaktiivisuudesta", value=format_status(settings["xp_epaaktiivisuus"]), inline=False)

            await inter.response.edit_message(embed=updated_embed, view=None)

        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Asetukset(bot))
