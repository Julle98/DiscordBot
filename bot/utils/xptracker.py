from discord.ext import commands
from bot.utils.xp_utils import käsittele_viesti_xp

class XPTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        await käsittele_viesti_xp(self.bot, message)