from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv
import discord
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.bot_setup import bot
from typing import Optional

from bot.utils.tasks_utils import (
    load_tasks,
    load_user_tasks,
    onko_tehtava_suoritettu_ajankohtaisesti,
    DAILY_TASKS,
    WEEKLY_TASKS,
    MONTHLY_TASKS,
    TASK_INSTRUCTIONS,
    StartTaskView,
    TaskControlView,
    active_listeners,
    load_streaks
)

load_dotenv()

REWARD_THRESHOLDS = {
    "daily": [7, 30],
    "weekly": [4, 12],
    "monthly": [3, 6]
}

TASK_LOG_CHANNEL_ID = int(os.getenv("TASK_LOG_CHANNEL_ID", 0))

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
    name="tehtävät", 
    description="Näytä ja suorita päivittäisiä, viikottaisia tai kuukausittaisia tehtäviä."
    )
    @app_commands.describe(ohje="Näytä tehtävien ohjeet, näyttää vain ohjeet ei tehtävät valikkoa (valinnainen)")
    @app_commands.checks.has_role("24G")
    async def tehtavat(self, interaction: discord.Interaction, ohje: Optional[bool] = False):
        await kirjaa_komento_lokiin(self.bot, interaction, "/tehtävät")
        await kirjaa_ga_event(self.bot, interaction.user.id, "tehtävät_komento")

        if ohje:
            embed = discord.Embed(
                title="📘 Tehtävien suoritusohjeet",
                description="Näin tehtävät toimivat ja miten voit hyödyntää streak- ja XP-logiikkaa:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Tehtävätyypit",
                value=(
                    "• 📅 **Päivittäiset** – vaihtuvat joka päivä.\n"
                    "• 📆 **Viikoittaiset** – vaihtuvat viikon alussa.\n"
                    "• 🗓️ **Kuukausittaiset** – vaihtuvat kuukauden vaihtuessa.\n"
                    "Kaikki tehtävät antavat XP:tä suoritettaessa."
                ),
                inline=False
            )
            embed.add_field(
                name="Streakit ja bonukset",
                value=(
                    "• Suorita tehtäviä peräkkäisinä päivinä/viikkoina/kuukausina.\n"
                    "• Tietyissä kohdissa (esim. 3, 7, 14, 30) saat **bonus-XP:tä**.\n"
                    "• Streakit näkyvät tilastoissa ja päivittyvät reaaliajassa."
                ),
                inline=False
            )
            embed.add_field(
                name="Armo ja katkeaminen",
                value=(
                    "• Sinulla on **3 armoa**, jotka estävät streakin katkeamisen.\n"
                    "• Armo käytetään automaattisesti, jos unohdat tehtävän.\n"
                    "• Armo ei palaudu ellet osta sitä Sannamaijan Shopista. Osto vaatii XP:tä."
                ),
                inline=False
            )
            embed.add_field(
                name="Vinkkejä",
                value=(
                    "• Käytä valikkoa valitaksesi tehtävän tai katsoaksesi tilastot.\n"
                    "• Suorita tehtävä ohjeiden mukaan – saat XP:tä ja kasvatat streakia.\n"
                    "• Pidä silmällä seuraavaa bonusta – se näkyy tilastoembedissä!"
                ),
                inline=False
            )
            embed.set_footer(text="Pysy aktiivisena – streakit palkitaan ja armo suojaa unohduksilta. ☺️")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        data = await asyncio.to_thread(load_tasks)
        daily = data.get("daily_tasks", [])
        weekly = data.get("weekly_tasks", [])
        monthly = data.get("monthly_tasks", [])
        done = await load_user_tasks()
        user_done = done.get(str(interaction.user.id), [])

        def seuraava_palkinto(streak, rewards, tyyppi):
            for raja in REWARD_THRESHOLDS.get(tyyppi, []):
                reward_id = f"{raja}_{'day' if tyyppi == 'daily' else 'week' if tyyppi == 'weekly' else 'month'}"
                if reward_id not in rewards:
                    return max(0, raja - streak)
            return 0

        class TaskMenuDropdown(discord.ui.Select):
            def __init__(self, user, daily, weekly, monthly, user_done):
                self.user = user
                self.user_done = user_done
                options = []

                def add_tasks(tasks, tyyppi_emoji, tyyppi_nimi):
                    for task in tasks:
                        is_done = onko_tehtava_suoritettu_ajankohtaisesti(task, user_done)
                        emoji = "✅ " if is_done else ""
                        label = f"{emoji}{tyyppi_emoji} {tyyppi_nimi}"
                        description = f"Suorita {tyyppi_nimi.lower()} tehtävä {task}"
                        options.append(discord.SelectOption(label=label, description=description, value=task))

                add_tasks(daily, "📅", "Päivittäinen")
                add_tasks(weekly, "📆", "Viikoittainen")
                add_tasks(monthly, "🗓️", "Kuukausittainen")

                options.append(discord.SelectOption(
                    label="📊 Näytä tilastot",
                    description="Katso omat suoritus- ja streak-tilastot",
                    value="stats"
                ))

                super().__init__(placeholder="Valitse toiminto...", options=options, min_values=1, max_values=1)

            async def callback(self, interaction: discord.Interaction):
                if interaction.user != self.user:
                    await interaction.response.send_message("Et voi käyttää toisen valikkoa!", ephemeral=True)
                    return

                chosen_value = self.values[0]

                if chosen_value == "stats":
                    uid = str(self.user.id)
                    streaks = load_streaks()
                    total_tasks = len(self.user_done)
                    total_xp = total_tasks * 50

                    daily = streaks.get(uid, {}).get("daily", {})
                    weekly = streaks.get(uid, {}).get("weekly", {})
                    monthly = streaks.get(uid, {}).get("monthly", {})

                    embed = discord.Embed(
                        title=f"📊 Tehtävätilastot – {self.user.display_name}",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Suoritettuja tehtäviä", value=f"**{total_tasks}**", inline=True)
                    embed.add_field(name="XP yhteensä", value=f"**{total_xp} XP**", inline=True)
                    embed.add_field(name="—", value="—", inline=True)
                    embed.add_field(
                        name="📅 Päivittäinen streak",
                        value=(
                            f"Nykyinen: **{daily.get('streak', 0)}**\n"
                            f"Pisin: **{daily.get('max_streak', 0)}**\n"
                            f"🎯 Seuraava palkinto: {seuraava_palkinto(daily.get('streak', 0), daily.get('rewards', []), 'daily')} päivän päästä"
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="📆 Viikoittainen streak",
                        value=(
                            f"Nykyinen: **{weekly.get('streak', 0)}**\n"
                            f"Pisin: **{weekly.get('max_streak', 0)}**\n"
                            f"🎯 Seuraava palkinto: {seuraava_palkinto(weekly.get('streak', 0), weekly.get('rewards', []), 'weekly')} viikon päästä"
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="🗓️ Kuukausittainen streak",
                        value=(
                            f"Nykyinen: **{monthly.get('streak', 0)}**\n"
                            f"Pisin: **{monthly.get('max_streak', 0)}**\n"
                            f"🎯 Seuraava palkinto: {seuraava_palkinto(monthly.get('streak', 0), monthly.get('rewards', []), 'monthly')} kuukauden päästä"
                        ),
                        inline=False
                    )
                    embed.set_footer(text="Pidä streak hengissä – tehtäväpäivitys päivittyy reaaliajassa.")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                if onko_tehtava_suoritettu_ajankohtaisesti(chosen_value, self.user_done):
                    await interaction.response.send_message(f"Olet jo suorittanut tehtävän ✅ **{chosen_value}**", ephemeral=True)
                    return

                instruction = TASK_INSTRUCTIONS.get(chosen_value, "Seuraa ohjeita ja suorita tehtävä.")
                view = StartTaskView(interaction.user, chosen_value, "Tehtävä")
                await interaction.response.send_message(
                    f"**Tehtävä:** {chosen_value}\n📘 **Ohjeet:** {instruction}",
                    view=view,
                    ephemeral=True
                )
        
        class TaskSelectorView(discord.ui.View):
            def __init__(self, user, daily, weekly, monthly, user_done, task_list):
                super().__init__(timeout=300)
                self.user = user
                self.user_done = user_done
                self.task_list = task_list
                self.add_item(TaskMenuDropdown(user, daily, weekly, monthly, user_done))

        now = datetime.now()
        end_of_day = now.replace(hour=23, minute=59).strftime("%d.%m.%Y klo %H:%M")
        end_of_week = (now + timedelta(days=(6 - now.weekday()))).replace(hour=23, minute=59).strftime("%d.%m.%Y klo %H:%M")
        end_of_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end_of_month_str = end_of_month.replace(hour=23, minute=59).strftime("%d.%m.%Y klo %H:%M")

        task_list = (
            "```md\n"
            f"# 📅 Päivittäiset tehtävät (vanhentuu: {end_of_day})\n" +
            ("\n".join(f"- {task}" for task in daily) if daily else "- Ei aktiivisia tehtäviä.") +
            f"\n\n# 📆 Viikoittaiset tehtävät (vanhentuu: {end_of_week})\n" +
            ("\n".join(f"- {task}" for task in weekly) if weekly else "- Ei aktiivisia tehtäviä.") +
            f"\n\n# 🗓️ Kuukausittaiset tehtävät (vanhentuu: {end_of_month_str})\n" +
            ("\n".join(f"- {task}" for task in monthly) if monthly else "- Ei aktiivisia tehtäviä.") +
            "\n```"
        )

        view = TaskSelectorView(interaction.user, daily, weekly, monthly, user_done, task_list)
        await interaction.response.send_message(content=task_list, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))