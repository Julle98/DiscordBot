import discord, asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import random

from bot.utils.bot_setup import bot
from bot.utils.xp_utils import (
    käsittele_viesti_xp,
    tarkkaile_kanavan_aktiivisuutta,
    load_xp_data,
    save_xp_data,
    calculate_level,
    make_xp_content,
    load_streaks,
    save_streaks,
)

komento_ajastukset = defaultdict(dict)  # {user_id: {command_name: viimeinen_aika}}
viestit_ja_ajat = {}  # {message_id: (user_id, timestamp)}
viime_viestit = {}    # {user_id: datetime}

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slowmode_watcher.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return

        user_id = message.author.id
        komento_nimi = "xp_viesti"
        nyt = datetime.now(timezone.utc)

        member = message.guild.get_member(user_id)
        nopea_roolit = ["Mestari", "Admin", "Moderaattori"]
        nopea = any(r.name in nopea_roolit for r in member.roles) if member else False
        raja = timedelta(seconds=5 if nopea else 10)

        viimeinen = komento_ajastukset[user_id].get(komento_nimi)
        if viimeinen and nyt - viimeinen < raja:
            return

        streaks = load_streaks()
        uid_str = str(user_id)
        viime_streak_pvm = datetime.fromisoformat(streaks.get(uid_str, {}).get("pvm", "1970-01-01")).date()
        viesti_pvm = nyt.date()
        ero = (viesti_pvm - viime_streak_pvm).days

        if ero >= 5:
            bonus = 50
            xp_data = load_xp_data()
            tiedot = xp_data.get(uid_str, {"xp": 0, "level": 0})
            tiedot["xp"] += bonus
            tiedot["level"] = calculate_level(tiedot["xp"])
            xp_data[uid_str] = tiedot
            save_xp_data(xp_data)

            try:
                if ero > 20000:
                    bonus_viestit = [
                        f"{message.author.mention} on palannut viestimään... todella pitkän tauon jälkeen. Sait **{bonus} XP** bonuksen ja streakisi alkaa nyt! 🌟",
                        f"{message.author.mention} on kuin myytti, joka astui jälleen esiin – aikojen takaa. Sait **{bonus} XP** bonuksen, uudet seikkailut alkavat nyt! 🧙‍♂️",
                        f"{message.author.mention} ilmestyi kuin salama ikuisuuden takaa! Sait **{bonus} XP**, streakisi aktivoitu! ⚡"
                    ]
                    viesti = random.choice(bonus_viestit)
                    await message.channel.send(viesti)

                if ero > 10:
                    bonus_viestit = [
                        f"{message.author.mention} palasi viestimään **{ero} päivän** tauon jälkeen! Vanha legenda on taas täällä! Sait **{bonus} XP** bonuksen ja streakisi alkaa nyt! 🔥",
                        f"{message.author.mention} ilmestyi takaisin kuin haamu menneisyydestä... Taukoa on takana **{ero} päivää**. Saat **{bonus} XP** paluubonuksen – uusi aikakausi alkaa! 🌒",
                        f"{message.author.mention} löytyi kadonneiden viestittelijöiden arkistosta! **{ero} päivää** ilman viestiä? Joko unohdit salasanan vai eksyit? Saat **{bonus} XP** bonuksen paluusta! 😱 ",
                        f"{message.author.mention} – yksi vanhoista 24G ryhmäläisistä palaa riveihin **{ero} päivän** jälkeen! Tervetuloa takaisin! Saat **{bonus} XP** bonuksen ja uusi streaki alkaa! 🛡️",
                        f"{message.author.mention} palasi viestimään **{ero} päivän** jälkeen! Ihanaa nähdä sinut taas. Saat **{bonus} XP** bonuksen, ja streakisi on käynnissä! ✨"
                    ]
                    viesti = random.choice(bonus_viestit)
                    await message.channel.send(viesti)

                else:
                    await message.channel.send(
                        f"{message.author.mention} palasi viestimään **{ero} päivän** tauon jälkeen! "
                        f"Sait **{bonus} XP** bonuksen ja streakisi on nyt käynnissä! 🔥"
                    )
            except:
                pass

        viime_viestit[user_id] = nyt
        komento_ajastukset[user_id][komento_nimi] = nyt
        viestit_ja_ajat[message.id] = (user_id, nyt)

        await käsittele_viesti_xp(self.bot, message)
        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        tiedot = viestit_ja_ajat.pop(message.id, None)
        if tiedot:
            user_id, aika = tiedot
            nyt = datetime.now(timezone.utc)
            if nyt - aika < timedelta(seconds=10):
                komento_ajastukset[user_id].pop("xp_viesti", None)

    @tasks.loop(seconds=30)
    async def slowmode_watcher(self):
        await tarkkaile_kanavan_aktiivisuutta()

    @slowmode_watcher.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(XPSystem(bot))