import discord
from discord.ext import commands
from discord import app_commands
import random
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class MiinaharavaButton(discord.ui.Button):
    def __init__(self, x, y, is_bomb, board):
        super().__init__(label="⬜", style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y
        self.is_bomb = is_bomb
        self.board = board  

    def count_adjacent_bombs(self):
        count = 0
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                nx, ny = self.x + dx, self.y + dy
                if (nx, ny) in self.board and self.board[(nx, ny)]:
                    count +=1
        return count

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.owner_id:
            await interaction.response.send_message("❌ Et voi muuttaa tätä peliä!", ephemeral=True)
            return

        if self.is_bomb:
            self.label = "💥"  
            self.style = discord.ButtonStyle.red
            for child in self.view.children:
                if isinstance(child, MiinaharavaButton) and child.is_bomb and child.label == "⬜":
                    child.label = "💣"
                    child.style = discord.ButtonStyle.danger
                child.disabled = True
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(f"💣 Hävisit! Oikea peli päättyi.", ephemeral=True)
        else:
            self.label = str(self.count_adjacent_bombs())
            self.style = discord.ButtonStyle.success
            self.disabled = True
            await interaction.response.edit_message(view=self.view)

            if all(b.disabled or b.is_bomb for b in self.view.children):
                games_utils.add_win(interaction.user.id, "miinaharava")
                await interaction.followup.send(f"🎉 {interaction.user.mention} selvitti kentän! +1 voitto ja +10 XP", ephemeral=True)

class Miinaharava(discord.ui.View):
    def __init__(self, owner_id, size=5, bombs=5):
        super().__init__()
        self.owner_id = owner_id
        grid = [(x, y) for x in range(size) for y in range(size)]
        bomb_coords = random.sample(grid, bombs)
        board = { (x,y): (x,y) in bomb_coords for x,y in grid }

        for y in range(size):
            for x in range(size):
                self.add_item(MiinaharavaButton(x, y, is_bomb=board[(x,y)], board=board))

class MiinaharavaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_miinaharava", description="Pelaa miinaharavaa")
    async def peli_miinaharava(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_miinaharava")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_miinaharava_komento")
        await interaction.response.send_message("💣 Miinaharava!", view=Miinaharava(owner_id=interaction.user.id))

async def setup(bot):
    await bot.add_cog(MiinaharavaCog(bot))