import os
from dotenv import load_dotenv

REQUIRED_KEYS = [
    "APPLICATION_ID",
    "DISCORD_BOT_TOKEN",
    "GA_MEASUREMENT_ID",
    "GA_API_SECRET",
    "SERVICE_ACCOUNT_FILE",
    "FFMPEG_EXECUTABLE",
    "LOG_CHANNEL_ID",
    "MODLOG_CHANNEL_ID",
    "XP_CHANNEL_ID",
    "IGNORED_VOICE_CHANNEL_ID",
    "GUILD_ID",
    "SLOWMODE_CHANNEL_ID",
    "AKTIIVISIMMAT_KANAVA_ID",
    "AKTIIVISIMMAT_ROOLI_ID",
    "HELP_CHANNEL_ID",
    "TASK_CHANNEL_ID",
    "TASK_LOG_CHANNEL_ID",
    "TASK_DATA_CHANNEL_ID",
    "OSTOSLOKI_KANAVA_ID",
    "ALERT_CHANNEL_ID",
    "VOICE_CHANNEL_ID",
    "MEME_CHANNEL_ID",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "REDIRECT_URI",
    "SESSION_SECRET"
]

def load_env_and_validate():
    load_dotenv()

    missing = []
    for key in REQUIRED_KEYS:
        value = os.getenv(key)
        if not value or value.strip() == "" or value.strip().lower() == "placeholder":
            missing.append(key)

    if missing:
        warning = (
            "\n ⚠️ Seuraavat .env-muuttujat puuttuvat tai ovat tyhjiä:\n"
            + "\n".join(f"- {key}" for key in missing)
            + "\n\nVarmista, että `.env` on oikein asetettu, tai kopioi `example.env` pohjaksi.\n"
        )
        print(warning)
    else:
        print("✅ Kaikki ympäristömuuttujat ladattu onnistuneesti.")
