import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
from collections import deque
from dotenv import load_dotenv
from bot.utils.tasks_utils import TaskListener, active_listeners
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.antinuke import cooldown

from bot.utils.tasks_utils import (
    load_tasks,
    load_user_tasks,
    onko_tehtava_suoritettu_ajankohtaisesti,
    DAILY_TASKS,
    WEEKLY_TASKS,
    MONTHLY_TASKS,
    TASK_INSTRUCTIONS,
    StartTaskView
)

from bot.utils.bot_setup import bot
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
load_dotenv()

TASK_LOG_CHANNEL_ID = int(os.getenv("TASK_LOG_CHANNEL_ID", 0))

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_rotations(self):
        from utils.tasks_utils import (
            rotate_daily_tasks,
            rotate_weekly_tasks,
            rotate_monthly_tasks
        )
        if not rotate_daily_tasks.is_running():
            rotate_daily_tasks.start()
        if not rotate_weekly_tasks.is_running():
            rotate_weekly_tasks.start()
        if not rotate_monthly_tasks.is_running():
            rotate_monthly_tasks.start()


    @app_commands.command(name="tehtavat", description="Näytä ja suorita päivittäisiä, viikottaisia tai kuukausittaisia tehtäviä.")
    @app_commands.checks.has_role("24G")
    @cooldown("tehtavat")
    async def tehtavat(self, interaction: discord.Interaction):
        await asyncio.to_thread(kirjaa_komento_lokiin, self.bot, interaction, "/tehtävät")
        await asyncio.to_thread(kirjaa_ga_event, interaction.user.id, "tehtävät_komento")

        data = await asyncio.to_thread(load_tasks)
        daily = data.get("daily_tasks", [])
        weekly = data.get("weekly_tasks", [])
        monthly = data.get("monthly_tasks", [])

        done = await load_user_tasks()
        user_done = done.get(str(interaction.user.id), [])

        class TaskButton(discord.ui.Button):
            def __init__(self, task_name, user_done):
                is_done = onko_tehtava_suoritettu_ajankohtaisesti(task_name, user_done)
                style = discord.ButtonStyle.secondary if is_done else discord.ButtonStyle.primary

                if task_name in DAILY_TASKS:
                    task_type = "📅 Päivittäinen"
                elif task_name in WEEKLY_TASKS:
                    task_type = "📆 Viikoittainen"
                elif task_name in MONTHLY_TASKS:
                    task_type = "🗓️ Kuukausittainen"
                else:
                    task_type = "Tehtävä"

                label = f"{task_type}" + (" ✅" if is_done else "")
                custom_id = f"{task_type[:3]}_{task_name.replace(' ', '_')}"

                super().__init__(label=label, style=style, disabled=is_done, custom_id=custom_id)

                self.task_name = task_name
                self.task_type = task_type
                self.user_done = user_done

            async def callback(self, interaction: discord.Interaction):
                if interaction.user != self.view.user:
                    await interaction.response.send_message("Et voi painaa toisen käyttäjän nappia!", ephemeral=True)
                    return

                if onko_tehtava_suoritettu_ajankohtaisesti(self.task_name, self.user_done):
                    await interaction.response.send_message(
                        f"Olet jo suorittanut tehtävän **{self.task_name}**. Odota seuraavaa tehtävää!",
                        ephemeral=True
                    )
                    return

                instruction = TASK_INSTRUCTIONS.get(self.task_name, "Seuraa ohjeita ja suorita tehtävä.")
                view = StartTaskView(interaction.user, self.task_name, self.task_type)

                await interaction.response.send_message(
                    f"**{self.task_type} tehtävä:** {self.task_name}\n📘 **Ohjeet:** {instruction}",
                    view=view,
                    ephemeral=True
                )

        class TaskButtons(discord.ui.View):
            def __init__(self, user, daily, weekly, monthly, user_done):
                super().__init__(timeout=300)
                self.user = user
                for task in daily:
                    self.add_item(TaskButton(task, user_done))
                for task in weekly:
                    self.add_item(TaskButton(task, user_done))
                for task in monthly:
                    self.add_item(TaskButton(task, user_done))

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

        view = TaskButtons(interaction.user, daily, weekly, monthly, user_done)
        await interaction.response.send_message(task_list, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Tasks(bot)
    await bot.add_cog(cog)
