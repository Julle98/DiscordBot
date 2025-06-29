import discord
from discord.ext import commands

class MemberWelcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        tervetuloviesti = (
            "Tervetuloa 24G discord palvelimelle. Olen yksi palvelimen boteista ja minua voit ohjata erilaisilla `/` komennoilla."
            "Odota kuitenkin ensin rauhassa hyväksymistä palvelimelle. Manuaalinen verifiointi voi viedä aikaa. "
            "Hauska nähdä sinut täällä!\n\n(tämä viesti on lähetetty automaattisesti)"
        )

        try:
            await member.send(tervetuloviesti)
            print(f"Tervetuloviesti lähetetty käyttäjälle {member.name}")
        except discord.Forbidden:
            print(f"En voinut lähettää tervetuloviestiä käyttäjälle {member.name}")

async def setup(bot):
    await bot.add_cog(MemberWelcome(bot))
