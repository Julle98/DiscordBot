import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.bot_setup import bot

@bot.event
async def on_member_join(member): 
    tervetuloviesti = (
        "Tervetuloa 24G discord palvelimelle. Olen yksi palvelimen boteista ja minua voit ohjata erilaisilla `/` komennoilla. "
        "Odota kuitenkin ensin rauhassa hyväksymistä palvelimelle. Manuaalinen verifiointi voi viedä aikaa. "
        "Hauska nähdä sinut täällä!\n\n(tämä viesti on lähetetty automaattisesti)"
    )

    try:
        await member.send(tervetuloviesti)
        print(f"Tervetuloviesti lähetetty käyttäjälle {member.name}")
    except discord.Forbidden:
        print(f"En voinut lähettää tervetuloviestiä käyttäjälle {member.name}") 