import random
from datetime import datetime, date
from discord import Message

from bot.utils.xp_utils import (
    load_streaks,
    save_streaks,
    load_xp_data,
    save_xp_data,
    calculate_level
)

async def käsittele_xp_bonus(message: Message, user_id: int, nyt: datetime):
    uid_str = str(user_id)
    streaks = load_streaks()

    try:
        viime_streak_pvm = datetime.fromisoformat(streaks.get(uid_str, {}).get("pvm", "1970-01-01")).date()
    except ValueError:
        viime_streak_pvm = date(1970, 1, 1)

    viesti_pvm = nyt.date()
    ero = (viesti_pvm - viime_streak_pvm).days

    print(f"[DEBUG] Käyttäjä: {message.author}, Viime streak: {viime_streak_pvm}, Nykyinen päivä: {viesti_pvm}, Ero: {ero}")

    if ero < 5:
        return  # Ei bonusta

    bonus = 50
    xp_data = load_xp_data()
    tiedot = xp_data.get(uid_str, {"xp": 0, "level": 0})
    tiedot["xp"] += bonus
    tiedot["level"] = calculate_level(tiedot["xp"])
    xp_data[uid_str] = tiedot
    save_xp_data(xp_data)

    streaks[uid_str] = {"pvm": viesti_pvm.isoformat()}
    save_streaks(streaks)

    try:
        if ero > 20000:
            bonus_viestit = [
                f"{message.author.mention} on palannut viestimään... todella pitkän tauon jälkeen. Sait **{bonus} XP** bonuksen ja streakisi alkaa nyt! 🌟",
                f"{message.author.mention} on kuin myytti, joka astui jälleen esiin – aikojen takaa. Sait **{bonus} XP** bonuksen, uudet seikkailut alkavat nyt! 🧙‍♂️",
                f"{message.author.mention} ilmestyi kuin salama ikuisuuden takaa! Sait **{bonus} XP**, streakisi aktivoitu! ⚡"
            ]
            viesti = random.choice(bonus_viestit)
        elif ero > 10:
            bonus_viestit = [
                f"{message.author.mention} palasi viestimään **{ero} päivän** tauon jälkeen! Vanha legenda on taas täällä! Sait **{bonus} XP** bonuksen ja streakisi alkaa nyt! 🔥",
                f"{message.author.mention} ilmestyi takaisin kuin haamu menneisyydestä... Taukoa on takana **{ero} päivää**. Saat **{bonus} XP** paluubonuksen – uusi aikakausi alkaa! 🌒",
                f"{message.author.mention} löytyi kadonneiden viestittelijöiden arkistosta! **{ero} päivää** ilman viestiä? Saat **{bonus} XP** bonuksen paluusta! 😱",
                f"{message.author.mention} – yksi vanhoista 24G ryhmäläisistä palaa riveihin **{ero} päivän** jälkeen! Tervetuloa takaisin! Saat **{bonus} XP** bonuksen ja uusi streaki alkaa! 🛡️",
                f"{message.author.mention} palasi viestimään **{ero} päivän** jälkeen! Ihanaa nähdä sinut taas. Saat **{bonus} XP** bonuksen, ja streakisi on käynnissä! ✨"
            ]
            viesti = random.choice(bonus_viestit)
        else:
            viesti = (
                f"{message.author.mention} palasi viestimään **{ero} päivän** tauon jälkeen! "
                f"Sait **{bonus} XP** bonuksen ja streakisi on nyt käynnissä! 🔥"
            )

        await message.channel.send(viesti)
    except Exception as e:
        print(f"[ERROR] Bonusviestin lähetys epäonnistui: {e}")
