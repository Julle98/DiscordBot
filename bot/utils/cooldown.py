from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
import os

komento_ajastukset: dict[int, dict[str, datetime]] = defaultdict(dict)

DEFAULT_COOLDOWN = 10
NOPEA_COOLDOWN = 5
NOPEA_ROOLIT = ["VIP", "Mestari", "Moderaattori", "Admin", "Sannamaija tester"]
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

# Not in use currently
def cooldown(komento_nimi: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction, *args, **kwargs):
            try:
                nyt = datetime.now()
                user_id = interaction.user.id

                member = interaction.guild.get_member(user_id)
                nopea = any(role.name in NOPEA_ROOLIT for role in member.roles) if member else False
                raja = timedelta(seconds=NOPEA_COOLDOWN if nopea else DEFAULT_COOLDOWN)

                viimeinen = komento_ajastukset[user_id].get(komento_nimi)
                if viimeinen and nyt - viimeinen < raja:
                    erotus = int((raja - (nyt - viimeinen)).total_seconds())

                    await interaction.response.send_message(
                        f"⏳ Odota {erotus} sekuntia ennen kuin käytät komentoa uudelleen.",
                        ephemeral=True
                    )

                    parametrit = ", ".join(
                        f"{k}={v}" for k, v in getattr(interaction, "namespace", {}).items() if v is not None
                    ) or "ei parametreja"

                    logikanava = interaction.client.get_channel(MOD_LOG_CHANNEL_ID)
                    if logikanava:
                        await logikanava.send(
                            f"⚠️ Käyttäjä {interaction.user.mention} käytti komentoa **/{komento_nimi}** liian nopeasti ({erotus}s jäljellä).\n"
                            f"📦 Parametrit: `{parametrit}`\n"
                            f"📍 Kanava: {interaction.channel.mention} | 🕒 {nyt.strftime('%H:%M:%S')}"
                        )

                    return

                komento_ajastukset[user_id][komento_nimi] = nyt

                if not interaction.response.is_done():
                    await interaction.response.defer(thinking=True)

                await func(interaction, *args, **kwargs)

            except Exception as e:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"⚠️ Virhe komennossa: {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ Virhe komennossa: {e}", ephemeral=True)

        return wrapper
    return decorator
