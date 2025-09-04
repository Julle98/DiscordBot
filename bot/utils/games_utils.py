import os
import json
from dotenv import load_dotenv

load_dotenv()
GAMES_JSON_PATH = os.getenv("GAMES_JSON_PATH")

def load_scores():
    try:
        if not GAMES_JSON_PATH or not os.path.exists(GAMES_JSON_PATH):
            return {}
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"load_scores error: {e}")
        return {}

def save_scores(data):
    try:
        if not GAMES_JSON_PATH:
            print("save_scores error: GAMES_JSON_PATH is None")
            return
        with open(GAMES_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"save_scores error: {e}")

def add_win(user_id: int, game: str, xp_amount: int = 10):
    try:
        data = load_scores()
        user_id = str(user_id)

        if user_id not in data:
            data[user_id] = {
                "total_wins": 0,
                "total_xp": 0
            }

        if game not in data[user_id]:
            data[user_id][game] = 0

        data[user_id][game] += 1
        data[user_id]["total_wins"] += 1
        data[user_id]["total_xp"] += xp_amount
        save_scores(data)
    except Exception as e:
        print(f"add_win error: {e}")

def get_user_stats(user_id: int):
    try:
        data = load_scores()
        stats = data.get(str(user_id), {"total_wins": 0, "total_xp": 0})
        xp = stats.get("total_xp", 0)
        return stats, xp
    except Exception as e:
        print(f"get_user_stats error: {e}")
        return {"total_wins": 0, "total_xp": 0}, 0

def get_global_stats():
    try:
        data = load_scores()
        ranking = []

        for uid, stats in data.items():
            xp = stats.get("total_xp", 0)
            ranking.append((int(uid), xp))

        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking[:10]
    except Exception as e:
        print(f"get_global_stats error: {e}")
        return []
    
def add_xp(user_id: int, xp_amount: int):
    try:
        data = load_scores()
        user_id = str(user_id)

        if user_id not in data:
            data[user_id] = {
                "total_wins": 0,
                "total_xp": 0
            }

        data[user_id]["total_xp"] += xp_amount
        save_scores(data)
    except Exception as e:
        print(f"add_xp error: {e}")

