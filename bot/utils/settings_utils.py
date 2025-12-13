import os
import json
from dotenv import load_dotenv

load_dotenv()
SETTINGS_PATH = os.getenv("SETTINGS_DATA_FILE")
MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 0))

USER_SETTINGS: dict = {}

DEFAULT_SETTINGS = {
    "xp_viestit": True,
    "xp_puhe": True,
    "xp_komennot": True,
    "xp_epaaktiivisuus": True
}

async def log_to_mod_channel(bot, message: str):
    channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"📝 **Asetusviestit**: {message}")

def load_user_settings():
    global USER_SETTINGS
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            USER_SETTINGS = json.load(f)
        print(f"[Asetukset] Käyttäjäasetukset ladattu: {len(USER_SETTINGS)} käyttäjää.")
    except FileNotFoundError:
        print(f"[Asetukset] Tiedostoa ei löytynyt: {SETTINGS_PATH}. Luodaan tyhjä asetusrakenne.")
        USER_SETTINGS = {}
    except json.JSONDecodeError as e:
        print(f"[Asetukset] JSONDecodeError tiedostossa {SETTINGS_PATH}: {e}")
        USER_SETTINGS = {}

def save_user_settings():
    try:
        print(f"[Asetukset] Tallennetaan: {os.path.abspath(SETTINGS_PATH)}")
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(USER_SETTINGS, f, indent=4, ensure_ascii=False)
        print(f"[Asetukset] Käyttäjäasetukset tallennettu: {SETTINGS_PATH}")
    except Exception as e:
        print(f"[Asetukset] Tallennus epäonnistui: {e}")

def get_user_settings(user_id: int):
    if not USER_SETTINGS:
        load_user_settings()

    user_id_str = str(user_id)

    if user_id_str not in USER_SETTINGS:
        print(f"[Asetukset] Luodaan oletusasetukset käyttäjälle {user_id_str}")
        USER_SETTINGS[user_id_str] = DEFAULT_SETTINGS.copy()
        save_user_settings()
        return USER_SETTINGS[user_id_str]

    for key, value in DEFAULT_SETTINGS.items():
        USER_SETTINGS[user_id_str].setdefault(key, value)

    return USER_SETTINGS[user_id_str]
