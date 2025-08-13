import os
from dotenv import load_dotenv

load_dotenv()

PREFIX = "!"

EVENT_CHANNEL_ID = int(os.getenv("EVENT_CHANNEL_ID"))
PRESENTATION_CHANNEL_ID = int(os.getenv("PRESENTATION_CHANNEL_ID"))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_EVENT_CHANNEL_ID"))
EVENT_WINNER_ROLE_ID = int(os.getenv("EVENT_WINNER_ROLE_ID"))
EVENT_PARTICIPANT_ROLE_ID = int(os.getenv("EVENT_PARTICIPANT_ROLE_ID"))

EVENT_DATA_FILE = os.getenv("EVENT_DATA_FILE")
