import discord
from discord.ext import commands
from discord import app_commands
from bot.utils import games_utils
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y, view):
        super().__init__(label="⬜", style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToe = self.view_ref

        if interaction.user.id not in [view.player_x.id, view.player_o.id]:
            await interaction.response.send_message("❌ Et voi painaa nappuloita tässä pelissä!", ephemeral=True)
            return

        if self.label != "⬜":
            await interaction.response.send_message("❌ Tämä ruutu on jo valittu!", ephemeral=True)
            return

        symbol = "❌" if view.turn == "X" else "⭕"
        self.label = symbol
        self.style = discord.ButtonStyle.danger if symbol=="❌" else discord.ButtonStyle.success
        self.disabled = True

        view.board[self.y][self.x] = symbol

        winner = None
        lines = view.board + [list(col) for col in zip(*view.board)]  
        lines.append([view.board[i][i] for i in range(3)])  
        lines.append([view.board[i][2-i] for i in range(3)])  

        for line in lines:
            if line.count("❌")==3:
                winner = view.player_x
            if line.count("⭕")==3:
                winner = view.player_o

        if winner:
            games_utils.add_win(winner.id, "ristinolla")
            for b in view.children:
                b.disabled = True
            await interaction.response.edit_message(view=view)
            await interaction.followup.send(f"🎉 {winner.mention} voitti ristinollan! +1 voitto ja +10 XP")
            return

        view.turn = "O" if view.turn=="X" else "X"
        await interaction.response.edit_message(view=view)

class TicTacToe(discord.ui.View):
    def __init__(self, player_x, player_o):
        super().__init__()
        self.player_x = player_x
        self.player_o = player_o
        self.turn = "X"
        self.board = [["" for _ in range(3)] for _ in range(3)]

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y, self))

class Ristinolla(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="peli_ristinolla", description="Pelaa ristinollaa kahdella pelaajalle")
    async def peli_ristinolla(self, interaction: discord.Interaction, opponent: discord.Member):
        await kirjaa_komento_lokiin(self.bot, interaction, "/peli_ristinolla")
        await kirjaa_ga_event(self.bot, interaction.user.id, "peli_ristinolla_komento")
        if opponent.bot or opponent == interaction.user:
            await interaction.response.send_message("❌ Valitse oikea pelaaja.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Ristinolla alkaa! X: {interaction.user.mention}, O: {opponent.mention}",
            view=TicTacToe(interaction.user, opponent)
        )

async def setup(bot):
    await bot.add_cog(Ristinolla(bot))

