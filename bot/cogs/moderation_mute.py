import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot.utils.logger import kirjaa_ga_event, kirjaa_komento_lokiin
from dotenv import load_dotenv
import os
import re
from bot.utils.error_handler import CommandErrorHandler
import asyncio

load_dotenv()
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", 0))

class Moderation_mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.modlog_channel_id: int = int(os.getenv("MODLOG_CHANNEL_ID", "0"))
        self.roles_to_toggle = [
            1413094672804347965,
            1339846579766694011,
            1339854259432329246,
            1370704701250601030,
            1370704731567161385,
            1370704765809332254,
            1370704818875928628,
            1370704865138839564,
            1370704889398825041
        ]

    def parse_duration(self, duration_str: str) -> int:
        pattern = re.compile(r'^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?$')
        match = pattern.fullmatch(duration_str.strip().lower())
        if not match:
            return -1
        days = int(match.group(1)) if match.group(1) else 0
        hours = int(match.group(2)) if match.group(2) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        return days * 1440 + hours * 60 + minutes

    def format_duration(self, total_minutes: int) -> str:
        days, remainder = divmod(total_minutes, 1440)
        hours, remainder = divmod(remainder, 60)
        mins = remainder
        parts = []
        if days:
            parts.append(f"{days} päivää")
        if hours:
            parts.append(f"{hours} tuntia")
        if mins:
            parts.append(f"{mins} minuuttia")
        return ", ".join(parts) if parts else "0 minuuttia"

    @app_commands.command(name="mute", description="Aseta jäähy jäsenelle.")
    @app_commands.describe(
        jäsen="Jäsen, jolle asetetaan jäähy",
        kesto="Jäähyn kesto (esim. 10s, 5m, 1h)",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    async def mute(self, interaction: discord.Interaction, jäsen: discord.Member, kesto: str, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/mute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "mute_komento")
        if jäsen == interaction.user:
            await interaction.response.send_message("Et voi asettaa itseäsi jäähylle.", ephemeral=True)
            return
        try:
            seconds = int(kesto[:-1])
            unit = kesto[-1]
            if unit == "s":
                duration = timedelta(seconds=seconds)
            elif unit == "m":
                duration = timedelta(minutes=seconds)
            elif unit == "h":
                duration = timedelta(hours=seconds)
            else:
                await interaction.response.send_message("Virheellinen aikaformaatti. Käytä esim. 10s, 5m, 1h", ephemeral=True)
                return

            poistetut = []
            if viesti_id:
                ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
                for vid in ids:
                    try:
                        msg = await interaction.channel.fetch_message(int(vid))
                        if msg.author.id == jäsen.id:
                            await msg.delete()
                            poistetut.append(vid)
                    except:
                        continue

            try:
                await jäsen.send(f"Sinut on asetettu jäähylle palvelimella {interaction.guild.name} ajaksi {kesto}.\nSyy: {syy}")
            except discord.Forbidden:
                pass

            await jäsen.timeout(duration, reason=f"{syy} (Asetti: {interaction.user})")
            await interaction.response.send_message(f"{jäsen.mention} asetettu jäähylle ajaksi {kesto}. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"🔇 **Jäähy asetettu**\n👤 {jäsen.mention}\n⏱ {kesto}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n📨 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except Exception as e:
            await interaction.response.send_message(f"Virhe asetettaessa jäähyä: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Poista jäähy jäseneltä.")
    @app_commands.describe(
        jäsen="Jäsen, jolta poistetaan jäähy",
        syy="Syy",
        viesti_id="Viestin ID tai useampi pilkulla erotettuna"
    )
    @app_commands.checks.has_role("Mestari")
    async def unmute(self, interaction: discord.Interaction, jäsen: discord.Member, syy: str = "Ei syytä annettu", viesti_id: str = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/unmute")
        await kirjaa_ga_event(self.bot, interaction.user.id, "unmute_komento")
        if jäsen.timed_out_until is None:
            await interaction.response.send_message(f"{jäsen.mention} ei ole jäähyllä.", ephemeral=True)
            return
        try:
            poistetut = []
            if viesti_id:
                ids = [i.strip() for i in viesti_id.split(",") if i.strip().isdigit()]
                for vid in ids:
                    try:
                        msg = await interaction.channel.fetch_message(int(vid))
                        if msg.author.id == jäsen.id:
                            await msg.delete()
                            poistetut.append(vid)
                    except:
                        continue

            await jäsen.timeout(None, reason=f"{syy} (Poisti: {interaction.user})")

            try:
                await jäsen.send(f"Jäähysi on poistettu palvelimella {interaction.guild.name}.\nSyy: {syy}")
            except discord.Forbidden:
                pass

            await interaction.response.send_message(f"{jäsen.mention} on vapautettu jäähyltä. Syy: {syy}")

            modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                log_msg = f"✅ **Jäähy poistettu**\n👤 {jäsen.mention}\n📝 {syy}\n👮 {interaction.user.mention}"
                if poistetut:
                    log_msg += f"\n🗑 Poistetut viestit: {', '.join(poistetut)}"
                await modlog_channel.send(log_msg)
        except Exception as e:
            await interaction.response.send_message(f"Virhe poistettaessa jäähyä: {e}", ephemeral=True)

    @app_commands.command(name="jäähyt", description="Näytä jäsenen jäähyhistoria.")
    @app_commands.describe(jäsen="Jäsen, jonka jäähyt halutaan tarkistaa")
    @app_commands.checks.has_role("Mestari")
    async def jäähyt(self, interaction: discord.Interaction, jäsen: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/jäähyt")
        await kirjaa_ga_event(self.bot, interaction.user.id, "jäähyt_komento")

        modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
        if not modlog_channel:
            await interaction.response.send_message("Modlog-kanavaa ei löytynyt.", ephemeral=True)
            return

        history = []
        async for msg in modlog_channel.history(limit=500):
            if msg.author.bot and f"{jäsen.mention}" in msg.content and "Jäähy asetettu" in msg.content:
                kesto_match = re.search(r"⏱ (.+)", msg.content)
                syy_match = re.search(r"📝 (.+)", msg.content)
                asettaja_match = re.search(r"👮 (.+)", msg.content)
                poistetut_match = re.search(r"📨 Poistetut viestit: (.+)", msg.content)

                kesto = kesto_match.group(1) if kesto_match else "?"
                syy = syy_match.group(1) if syy_match else "?"
                asettaja = asettaja_match.group(1) if asettaja_match else "?"
                poistetut = poistetut_match.group(1) if poistetut_match else None

                history.append({
                    "aika": msg.created_at.strftime("%d.%m.%Y %H:%M"),
                    "kesto": kesto,
                    "syy": syy,
                    "asettaja": asettaja,
                    "poistetut": poistetut
                })

        if not history:
            await interaction.response.send_message(f"{jäsen.mention} ei ole saanut jäähyjä.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Jäähyhistoria: {jäsen}", color=discord.Color.orange())
        for i, h in enumerate(history, 1):
            value = (
                f"📅 Aika: {h['aika']}\n"
                f"⏱️ Kesto: {h['kesto']}\n"
                f"📝 Syy: {h['syy']}\n"
                f"👮 Asettaja: {h['asettaja']}"
            )
            if h["poistetut"]:
                value += f"\n📨 Poistetut viestit: {h['poistetut']}"
            embed.add_field(name=f"Jäähy #{i}", value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mute_rooli", description="Anna jäsenelle mute-rooli määräajaksi syyn kera.")
    @app_commands.describe(
        member="Jäsen, joka halutaan mutettaa",
        duration="Rangaistuksen kesto (esim. 1d2h30m, 3h, 45m)",
        reason="Syy rangaistukselle"
    )
    async def mute_rooli(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "Ei syytä annettu"
    ):
        mute_role_id = 1341078448042672148
        guild = interaction.guild
        mute_role = guild.get_role(mute_role_id)

        if not mute_role:
            return await interaction.response.send_message("❌ Mute-roolia ei löytynyt.", ephemeral=True)

        total_minutes = self.parse_duration(duration)
        if total_minutes <= 0:
            return await interaction.response.send_message(
                "❌ Virheellinen kesto. Käytä muotoa esim. `1d2h30m`, `3h`, `45m`. Hyväksytyt yksiköt: d (päivä), h (tunti), m (minuutti).",
                ephemeral=True
            )

        roles_to_remove = [guild.get_role(rid) for rid in self.roles_to_toggle if guild.get_role(rid) in member.roles]

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"Mute: {reason}")
            await member.add_roles(mute_role, reason=f"Mute: {reason}")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Ei oikeuksia muuttaa rooleja.", ephemeral=True)

        duration_str = self.format_duration(total_minutes)

        await interaction.response.send_message(
            f"🔇 {member.mention} sai mute-roolin {duration_str}. Syy: {reason}"
        )

        if self.modlog_channel_id:
            modlog_channel = guild.get_channel(self.modlog_channel_id)
            if modlog_channel:
                embed = discord.Embed(
                    title="🔇 Mute annettu",
                    description=f"{member.mention} sai mute-roolin.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Kesto", value=duration_str, inline=False)
                embed.add_field(name="Syy", value=reason, inline=False)
                embed.add_field(name="Moderaattori", value=interaction.user.mention, inline=False)
                await modlog_channel.send(embed=embed)

        await asyncio.sleep(total_minutes * 60)
        try:
            await member.remove_roles(mute_role, reason="Mute päättyi")
            if roles_to_remove:
                await member.add_roles(*roles_to_remove, reason="Mute päättyi")

            if self.modlog_channel_id:
                modlog_channel = guild.get_channel(self.modlog_channel_id)
                if modlog_channel:
                    embed = discord.Embed(
                        title="✅ Mute päättyi",
                        description=f"{member.mention}n mute-rooli poistettiin ja roolit palautettiin.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Kesto", value=duration_str, inline=False)
                    await modlog_channel.send(embed=embed)

        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Moderation_mute(bot)
    await bot.add_cog(cog)