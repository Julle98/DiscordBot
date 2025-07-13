from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv
import discord

from bot.utils.tasks_utils import (
    load_tasks,
    load_user_tasks,
    onko_tehtava_suoritettu_ajankohtaisesti,
    DAILY_TASKS,
    WEEKLY_TASKS,
    MONTHLY_TASKS,
    TASK_INSTRUCTIONS,
    StartTaskView,
    load_streaks
)

load_dotenv()

REWARD_THRESHOLDS = {
    "daily": [7, 30],
    "weekly": [4, 12],
    "monthly": [3, 6]
}

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tehtävät", description="Näytä ja suorita päivittäisiä, viikottaisia tai kuukausittaisia tehtäviä.")
    @app_commands.checks.has_role("24G")
    async def tehtavat(self, interaction: discord.Interaction):
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
                super().__init__(label=label, style=style, disabled=is_done)
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

        def seuraava_palkinto(streak, rewards, tyyppi):
            for raja in REWARD_THRESHOLDS.get(tyyppi, []):
                reward_id = f"{raja}_{'day' if tyyppi == 'daily' else 'week' if tyyppi == 'weekly' else 'month'}"
                if reward_id not in rewards:
                    return max(0, raja - streak)
            return 0

        class TaskMenuDropdown(discord.ui.Select):
            def __init__(self, user, user_done, task_buttons, parent_view):
                self.user = user
                self.user_done = user_done
                self.task_buttons = task_buttons
                self.parent_view = parent_view
                options = [
                    discord.SelectOption(label="Tehtävävalikko", description="Avaa tehtävien napit", value="menu"),
                    discord.SelectOption(label="Stats", description="Näytä omat tilastot", value="stats"),
                ]
                super().__init__(placeholder="Valitse toiminto...", options=options)

            async def callback(self, interaction: discord.Interaction):
                if interaction.user != self.user:
                    await interaction.response.send_message("Et voi käyttää toisen valikkoa!", ephemeral=True)
                    return
                if self.values[0] == "menu":
                    uusi_nakyma = discord.ui.View(timeout=300)
                    for item in self.parent_view.task_buttons.children:
                        uusi_nakyma.add_item(item)
                    uusi_nakyma.add_item(TaskMenuDropdown(self.user, self.user_done, self.parent_view.task_buttons, self.parent_view))
                    await interaction.response.edit_message(
                        content=self.parent_view.task_list,
                        embed=None,
                        view=uusi_nakyma
                    )
                elif self.values[0] == "stats":
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
                        value=f"{daily.get('streak', 0)}\n🎯 Seuraava palkinto: {seuraava_palkinto(daily.get('streak', 0), daily.get('rewards', []), 'daily')} päivän päästä",
                        inline=False
                    )
                    embed.add_field(
                        name="📆 Viikoittainen streak",
                        value=f"{weekly.get('streak', 0)}\n🎯 Seuraava palkinto: {seuraava_palkinto(weekly.get('streak', 0), weekly.get('rewards', []), 'weekly')} viikon päästä",
                        inline=False
                    )
                    embed.add_field(
                        name="🗓️ Kuukausittainen streak",
                        value=f"{monthly.get('streak', 0)}\n🎯 Seuraava palkinto: {seuraava_palkinto(monthly.get('streak', 0), monthly.get('rewards', []), 'monthly')} kuukauden päästä",
                        inline=False
                    )
                    embed.set_footer(text="Pidä streak hengissä – tehtäväpäivitys päivittäin klo 00:00 UTC.")
                    await interaction.response.edit_message(content=None, embed=embed, view=self.view)

        class TaskSelectorView(discord.ui.View):
            def __init__(self, user, daily, weekly, monthly, user_done, task_list):
                super().__init__(timeout=300)
                self.user = user
                self.user_done = user_done
                self.task_buttons = TaskButtons(user, daily, weekly, monthly, user_done)
                self.task_list = task_list  
                self.add_item(TaskMenuDropdown(user, user_done, self.task_buttons, self))

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