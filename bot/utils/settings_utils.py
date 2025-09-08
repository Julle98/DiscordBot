import os
import json
from dotenv import load_dotenv

load_dotenv()
SETTINGS_PATH = os.getenv("SETTINGS_DATA_FILE")

USER_SETTINGS = {}

def load_user_settings():
    global USER_SETTINGS
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            USER_SETTINGS = json.load(f)
    except FileNotFoundError:
        USER_SETTINGS = {}
    except json.JSONDecodeError:
        USER_SETTINGS = {}

def save_user_settings():
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(USER_SETTINGS, f, indent=4, ensure_ascii=False)

def get_user_settings(user_id: int):
    if str(user_id) not in USER_SETTINGS:
        USER_SETTINGS[str(user_id)] = {
            "xp_viestit": True,
            "xp_puhe": True,
            "xp_komennot": True,
            "xp_epaaktiivisuus": True
        }
        save_user_settings()
    return USER_SETTINGS[str(user_id)]
