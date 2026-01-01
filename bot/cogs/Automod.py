import os
import discord
from discord.ext import commands

GUILD_ID = int(os.getenv("GUILD_ID", "0")) or None
MODLOG_CHANNEL_ID = int(os.getenv("MODLOG_CHANNEL_ID", "0")) or None

class AutoModNotifier(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._offence_counts: dict[tuple[int, int], int] = {}

    def _get_offence_count(self, guild_id: int, user_id: int) -> int:
        key = (guild_id, user_id)
        self._offence_counts[key] = self._offence_counts.get(key, 0) + 1
        return self._offence_counts[key]

    @staticmethod
    def _consequence_text(offence_count: int) -> str:
        if offence_count <= 2:
            return (
                "Tämä toimii **varoituksena**. Seuraathan jatkossa sääntöjä huolellisemmin."
            )
        elif offence_count <= 4:
            return (
                "Tämä on **3.–4. rikkomus**. Jatkossa rikkomuksista voidaan antaa "
                "**15 minuutin aikalisä (jäähy)**."
            )
        elif offence_count <= 6:
            return (
                "Tämä on **5.–6. rikkomus**. Jatkossa rikkomuksista voidaan antaa "
                "**30 minuutin aikalisä (jäähy)**."
            )
        else:
            return (
                "Rikkomuksia on kertynyt useita. Seuraavaksi voidaan harkita pidempää "
                "jäähyä, oikeuksien rajoittamista tai porttikieltoa palvelimelle."
            )

    async def _send_modlog(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        rule_name: str,
        matched_keyword: str,
        matched_content: str,
        offence_count: int,
        dm_success: bool,
    ) -> None:
        if MODLOG_CHANNEL_ID is None:
            return

        channel = guild.get_channel(MODLOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await guild.fetch_channel(MODLOG_CHANNEL_ID)
            except discord.HTTPException:
                return

        log_embed = discord.Embed(
            title="🔎 AutoMod-rike",
            colour=discord.Colour.red(),
        )
        log_embed.add_field(
            name="Käyttäjä",
            value=f"{user} (`{user.id}`)",
            inline=False,
        )
        log_embed.add_field(
            name="Rikottu sääntö",
            value=rule_name,
            inline=False,
        )
        log_embed.add_field(
            name="Avainsana / trigger",
            value=matched_keyword or "Ei määritelty",
            inline=False,
        )

        content_preview = matched_content or "Ei saatavilla"
        if len(content_preview) > 1000:
            content_preview = content_preview[:1000] + "…"

        log_embed.add_field(
            name="Estetty viesti",
            value=content_preview,
            inline=False,
        )

        log_embed.add_field(
            name="Rikemäärä (tämän cogin mittaus)",
            value=str(offence_count),
            inline=True,
        )
        log_embed.add_field(
            name="DM lähetetty",
            value="✅ Kyllä" if dm_success else "⚠️ Ei (DM kiinni / epäonnistui)",
            inline=True,
        )

        await channel.send(embed=log_embed)

    @commands.Cog.listener()
    async def on_automod_action(self, execution: discord.AutoModAction):
        guild = getattr(execution, "guild", None) or self.bot.get_guild(execution.guild_id)
        if guild is None:
            return

        if GUILD_ID is not None and guild.id != GUILD_ID:
            return

        try:
            rule = await guild.fetch_automod_rule(execution.rule_id)
            rule_name = rule.name
        except Exception:
            rule = None
            rule_name = f"Sääntö #{execution.rule_id}"

        member = guild.get_member(execution.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(execution.user_id)
            except discord.HTTPException:
                member = None

        user = member or self.bot.get_user(execution.user_id)
        if user is None:
            return

        matched_content = getattr(execution, "matched_content", None) or getattr(
            execution, "content", None
        ) or "Ei saatavilla"
        matched_keyword = getattr(execution, "matched_keyword", None) or "Ei määritelty"

        offence_count = self._get_offence_count(guild.id, user.id)
        consequence_text = self._consequence_text(offence_count)

        user_embed = discord.Embed(
            title="⚠️ AutoMod-huomautus",
            description=(
                f"Palvelimen **{guild.name}** automoderointi esti viestisi.\n"
                f"Olet rikkonut sääntöä: **{rule_name}**."
            ),
            colour=discord.Colour.orange(),
        )

        user_embed.add_field(
            name="Rikottu sääntö / avainsana",
            value=matched_keyword,
            inline=False,
        )

        content_preview = matched_content
        if len(content_preview) > 1000:
            content_preview = matched_content[:1000] + "…"

        user_embed.add_field(
            name="Estetty viesti",
            value=content_preview,
            inline=False,
        )

        user_embed.add_field(
            name="Rikemäärä (Sannamaijan mittaus)",
            value=str(offence_count),
            inline=True,
        )

        user_embed.add_field(
            name="Mitä jatkossa seuraa",
            value=consequence_text,
            inline=False,
        )

        user_embed.set_footer(
            text="Jos koet tämän virheeksi, ota yhteyttä palvelimen moderaattoreihin."
        )

        dm_success = True
        try:
            await user.send(embed=user_embed)
        except discord.Forbidden:
            dm_success = False

        await self._send_modlog(
            guild=guild,
            user=user,
            rule_name=rule_name,
            matched_keyword=matched_keyword,
            matched_content=matched_content,
            offence_count=offence_count,
            dm_success=dm_success,
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModNotifier(bot))