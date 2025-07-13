import os
from dotenv import load_dotenv

PREFIX = "!" 

load_dotenv()
EVENT_CHANNEL_ID = os.getenv("EVENT_CHANNEL_ID")
PRESENTATION_CHANNEL_ID = os.getenv("PRESENTATION_CHANNEL_ID")
VOICE_CHANNEL_ID = os.getenv("VOICE_CHANNEL_ID")

EVENT_DATA_FILE = os.getenv("EVENT_DATA_FILE")