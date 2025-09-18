import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.settings_utils import get_user_settings, save_user_settings
from bot.utils.bot_setup import bot
from dotenv import load_dotenv
import os

load_dotenv()
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", "0"))

async def kirjaa_asetusmuutos_lokiin(bot, user: discord.User, muutokset: dict):
    kanava = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not kanava:
        return

    from datetime import datetime
    nyt = datetime.now().strftime("%d.%m.%Y klo %H:%M")

    kuvaus = "\n".join([f"🔧 `{key}` → {'✅ Päällä' if val else '❌ Pois'}" for key, val in muutokset.items()])
    embed = discord.Embed(
        title="⚙️ XP-asetusten muutos",
        description=f"**Käyttäjä:** {user.mention} (`{user.id}`)\n**Aikaleima:** {nyt}\n\n{kuvaus}",
        color=discord.Color.gold()
    )
    await kanava.send(embed=embed)

class SettingsView(discord.ui.View):
    def __init__(self, settings, update_callback, default_settings):
        super().__init__(timeout=None)
        self.settings = settings
        self.update_callback = update_callback
        self.default_settings = default_settings

        options = [
            discord.SelectOption(label="✅ Kaikki päälle", value="enable_all", description="Aktivoi kaikki XP-asetukset"),
            discord.SelectOption(label="❌ Kaikki pois", value="disable_all", description="Poista kaikki XP-asetukset käytöstä"),
            discord.SelectOption(label="🔄 Palauta oletukset", value="reset_defaults", description="Palauta alkuperäiset XP-asetukset"),
            discord.SelectOption(label="💬 XP viesteistä", value="xp_viestit", description="Käyttäjä saa XP:tä tekstiviesteistä"),
            discord.SelectOption(label="🎙️ XP puhekanavalta", value="xp_puhe", description="Käyttäjä saa XP:tä puhekanavalla olemisesta"),
            discord.SelectOption(label="⚙️ XP komennoista", value="xp_komennot", description="Käyttäjä saa XP:tä komentoja käyttämällä"),
            discord.SelectOption(label="🕒 XP bonus epäaktiivisuudesta", value="xp_epaaktiivisuus", description="Käyttäjä saa XP-bonusta palatessaan pitkän tauon jälkeen"),
        ]

        self.select = discord.ui.Select(
            placeholder="Valitse XP-asetukset",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        for key, label in {
            "xp_viestit": "XP viesteistä",
            "xp_puhe": "XP puhekanavalta",
            "xp_komennot": "XP komennoista",
            "xp_epaaktiivisuus": "XP bonus epäaktiivisuudesta"
        }.items():
            self.add_item(self.ToggleButton(key, label, self.settings[key]))

    class ToggleButton(discord.ui.Button):
        def __init__(self, key, label, state):
            style = discord.ButtonStyle.success if state else discord.ButtonStyle.danger
            text = f"{label}: {'Poista käytöstä' if state else 'Ota käyttöön'}"
            super().__init__(label=text, style=style)
            self.key = key
            self.label_base = label
            self.state = state

        async def callback(self, interaction: discord.Interaction):
            self.state = not self.state
            self.view.settings[self.key] = self.state
            save_user_settings()
            msg = f"🔧 {self.label_base} {'otettu käyttöön' if self.state else 'poistettu käytöstä'}."
            await self.view.update_callback(interaction, self.view.settings, msg)

    async def select_callback(self, interaction: discord.Interaction):
        selected = self.select.values

        if "enable_all" in selected and all(self.settings.values()):
            await interaction.response.send_message("ℹ️ Kaikki asetukset ovat jo päällä.", ephemeral=True)
            return
        if "disable_all" in selected and not any(self.settings.values()):
            await interaction.response.send_message("ℹ️ Kaikki asetukset ovat jo pois päältä.", ephemeral=True)
            return

        if any(v in selected for v in ["enable_all", "disable_all", "reset_defaults"]):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Vahvista asetusten muutos",
                    description="Olet tekemässä laajaa muutosta XP-asetuksiin.\nKlikkaa alla olevaa nappia vahvistaaksesi tai peruaksesi.",
                    color=discord.Color.orange()
                ),
                view=ConfirmationView(selected, self.settings, self.update_callback, self.default_settings),
                ephemeral=True
            )
        else:
            for key in self.settings:
                self.settings[key] = key in selected
            save_user_settings()
            await self.update_callback(interaction, self.settings, "✅ Asetukset päivitetty valintasi mukaan.")

class ConfirmationView(discord.ui.View):
    def __init__(self, selected, settings, update_callback, default_settings):
        super().__init__(timeout=60)
        self.selected = selected
        self.settings = settings
        self.update_callback = update_callback
        self.default_settings = default_settings

    @discord.ui.button(label="✅ Vahvista muutos", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if "enable_all" in self.selected:
            for key in self.settings:
                self.settings[key] = True
            msg = "✅ Kaikki asetukset otettu käyttöön."
        elif "disable_all" in self.selected:
            for key in self.settings:
                self.settings[key] = False
            msg = "❌ Kaikki asetukset poistettu käytöstä."
        elif "reset_defaults" in self.selected:
            self.settings.update(self.default_settings)
            msg = "🔄 Asetukset palautettu oletusarvoihin."
        else:
            msg = "✅ Asetukset päivitetty."

        save_user_settings()
        await self.update_callback(interaction, self.settings, msg)

    @discord.ui.button(label="❌ Peruuta", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            content="⚙️ Muutos peruutettu. Asetuksia ei päivitetty.",
            ephemeral=True
        )

class Asetukset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="asetukset", description="Muuta XP-asetuksiasi")
    async def asetukset(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/asetukset")
        await kirjaa_ga_event(self.bot, interaction.user.id, "asetukset_komento")
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

        from datetime import datetime

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
                embed.add_field(name=label, value="✅ Päällä" if updated_settings[key] else "❌ Pois", inline=False)

            now = datetime.now().strftime("%d.%m.%Y klo %H:%M")
            embed.set_footer(text=f"Päivitetty: {now}")

            await kirjaa_asetusmuutos_lokiin(bot, inter.user, updated_settings)
            await inter.message.edit(embed=embed, view=SettingsView(updated_settings, update_embed, default_settings))

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