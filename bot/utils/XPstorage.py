import json
from pathlib import Path

class XPStorage:
    def __init__(self, xp_folder: Path, voice_data_path: Path):
        self.xp_file = xp_folder / "users_xp.json"
        self.voice_data_path = voice_data_path

    def load_xp_data(self):
        if self.xp_file.exists():
            with open(self.xp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_xp_data(self, data):
        self.xp_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.xp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_voice_activity(self):
        if self.voice_data_path.exists():
            with open(self.voice_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "temporary_flags": {},
            "total_voice_usage": {},
            "voice_channels": {}
        }

    def save_voice_activity(self, data):
        self.voice_data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.voice_data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
