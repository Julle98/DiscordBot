import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class FlagToggleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚩 Liputustila: OFF", style=discord.ButtonStyle.primary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: Miinaharava = self.view
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("❌ Et voi muuttaa tätä peliä!", ephemeral=True)
            return

        view.flag_mode = not view.flag_mode
        self.label = f"🚩 Liputustila: {'ON' if view.flag_mode else 'OFF'}"
        await interaction.response.edit_message(view=view)

class MiinaharavaButton(discord.ui.Button):
    def __init__(self, x, y, is_bomb, board):
        super().__init__(label="⬜", style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y
        self.is_bomb = is_bomb
        self.board = board
        self.flagged = False

    def count_adjacent_bombs(self):
        return sum(
            self.board.get((self.x + dx, self.y + dy), False)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
        )

    async def callback(self, interaction: discord.Interaction):
        view: Miinaharava = self.view
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("❌ Et voi muuttaa tätä peliä!", ephemeral=True)
            return

        if view.flag_mode:
            self.flagged = not self.flagged
            self.label = "🚩" if self.flagged else "⬜"
            await interaction.response.edit_message(view=view)

            flagged_bombs = [b for b in view.children if isinstance(b, MiinaharavaButton) and b.flagged]
            actual_bombs = [b for b in view.children if isinstance(b, MiinaharavaButton) and b.is_bomb]
            if len(flagged_bombs) == len(actual_bombs) and all(b.is_bomb for b in flagged_bombs):
                for b in view.children:
                    b.disabled = True
                games_utils.add_win(interaction.user.id, "miinaharava")
                await interaction.followup.send(f"🎯 {interaction.user.mention} liputti kaikki pommit oikein! +1 voitto ja +10 XP", ephemeral=True)
            return

        if self.flagged:
            await interaction.response.send_message("⚠️ Tämä ruutu on merkitty lipulla. Poista lippu ennen avaamista.", ephemeral=True)
            return

        if self.is_bomb:
            self.label = "💥"
            self.style = discord.ButtonStyle.red
            for child in view.children:
                if isinstance(child, MiinaharavaButton):
                    child.disabled = True
                    if child.is_bomb and child.label == "⬜":
                        child.label = "💣"
                        child.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=view)
            await interaction.followup.send("💣 Hävisit! Oikea peli päättyi.", ephemeral=True)
        else:
            self.label = str(self.count_adjacent_bombs())
            self.style = discord.ButtonStyle.success
            self.disabled = True
            await interaction.response.edit_message(view=view)

            if all(b.disabled or b.is_bomb for b in view.children):
                games_utils.add_win(interaction.user.id, "miinaharava")
                await interaction.followup.send(f"🎉 {interaction.user.mention} selvitti kentän! +1 voitto ja +10 XP", ephemeral=True)

class Miinaharava(discord.ui.View):
    def __init__(self, owner_id, size=4, bombs=5):  
        super().__init__()
        self.owner_id = owner_id
        self.flag_mode = False
        grid = [(x, y) for x in range(size) for y in range(size)]
        bomb_coords = random.sample(grid, bombs)
        board = { (x, y): (x, y) in bomb_coords for x, y in grid }

        for y in range(size):
            for x in range(size):
                self.add_item(MiinaharavaButton(x, y, is_bomb=board[(x, y)], board=board))

        self.add_item(FlagToggleButton())

class MiinaharavaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_miinaharava", description="Pelaa miinaharavaa")
    async def peli_miinaharava(self, interaction: discord.Interaction):
        await interaction.response.send_message("💣 Miinaharava käynnistetty!", view=Miinaharava(owner_id=interaction.user.id))

        asyncio.create_task(kirjaa_komento_lokiin(self.bot, interaction, "/peli_miinaharava"))
        asyncio.create_task(kirjaa_ga_event(self.bot, interaction.user.id, "peli_miinaharava_komento"))

async def setup(bot):
    await bot.add_cog(MiinaharavaCog(bot))
