import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.settings_utils import get_user_settings, save_user_settings

class SettingsView(discord.ui.View):
    def __init__(self, settings, update_callback, default_settings):
        super().__init__(timeout=None)
        self.settings = settings
        self.update_callback = update_callback
        self.default_settings = default_settings

        options = [
            discord.SelectOption(label="Kaikki päälle", value="enable_all", description="Aktivoi kaikki XP-asetukset"),
            discord.SelectOption(label="Kaikki pois", value="disable_all", description="Poista kaikki XP-asetukset käytöstä"),
            discord.SelectOption(label="Palauta oletukset", value="reset_defaults", description="Palauta alkuperäiset asetukset"),
            discord.SelectOption(label="XP viesteistä", value="xp_viestit"),
            discord.SelectOption(label="XP puhekanavalta", value="xp_puhe"),
            discord.SelectOption(label="XP komennoista", value="xp_komennot"),
            discord.SelectOption(label="XP bonus epäaktiivisuudesta", value="xp_epaaktiivisuus"),
        ]

        self.select = discord.ui.Select(
            placeholder="Valitse XP-asetukset",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        selected = self.select.values

        if "enable_all" in selected:
            for key in self.settings:
                self.settings[key] = True
            message = "✅ Kaikki asetukset otettu käyttöön."
        elif "disable_all" in selected:
            for key in self.settings:
                self.settings[key] = False
            message = "❌ Kaikki asetukset poistettu käytöstä."
        elif "reset_defaults" in selected:
            self.settings.update(self.default_settings)
            message = "🔄 Asetukset palautettu oletusarvoihin."
        else:
            for key in self.settings:
                self.settings[key] = key in selected
            message = "✅ Asetukset päivitetty valintasi mukaan."

        save_user_settings()
        await self.update_callback(interaction, self.settings, message)

class Asetukset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="asetukset", description="Muuta XP-asetuksiasi")
    async def asetukset(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        settings = get_user_settings(user_id)

        default_settings = {
            "xp_viestit": True,
            "xp_puhe": True,
            "xp_komennot": True,
            "xp_epaaktiivisuus": True
        }

        def format_status(value: bool) -> str:
            return "✅ Päällä" if value else "❌ Pois"

        async def update_embed(inter: discord.Interaction, updated_settings, status_message: str):
            embed = discord.Embed(
                title="⚙️ XP-asetuksesi (päivitetty)",
                description=status_message,
                color=discord.Color.green()
            )
            for key, label in {
                "xp_viestit": "XP viesteistä",
                "xp_puhe": "XP puhekanavalta",
                "xp_komennot": "XP komennoista",
                "xp_epaaktiivisuus": "XP bonus epäaktiivisuudesta"
            }.items():
                embed.add_field(name=label, value=format_status(updated_settings[key]), inline=False)

            await inter.response.edit_message(embed=embed, view=SettingsView(updated_settings, update_embed, default_settings))

        embed = discord.Embed(
            title="⚙️ XP-asetuksesi",
            color=discord.Color.blurple()
        )
        for key, label in {
            "xp_viestit": "XP viesteistä",
            "xp_puhe": "XP puhekanavalta",
            "xp_komennot": "XP komennoista",
            "xp_epaaktiivisuus": "XP bonus epäaktiivisuudesta"
        }.items():
            embed.add_field(name=label, value=format_status(settings[key]), inline=False)

        view = SettingsView(settings, update_embed, default_settings)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Asetukset(bot))
