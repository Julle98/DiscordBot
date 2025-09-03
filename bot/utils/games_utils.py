import os
import json
from dotenv import load_dotenv

load_dotenv()
GAMES_JSON_PATH = os.getenv("GAMES_JSON_PATH")

def load_scores():
    if not os.path.exists(GAMES_JSON_PATH):
        return {}
    with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_scores(data):
    with open(GAMES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_win(user_id: int, game: str):
    data = load_scores()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"total_wins": 0}

    if game not in data[user_id]:
        data[user_id][game] = 0

    data[user_id][game] += 1
    data[user_id]["total_wins"] += 1
    save_scores(data)

def get_user_stats(user_id: int):
    data = load_scores()
    stats = data.get(str(user_id), {"total_wins": 0})
    wins_total = stats.get("total_wins", 0)
    xp = wins_total * 10
    return stats, xp

def get_global_stats():
    data = load_scores()
    ranking = []

    for uid, stats in data.items():
        wins_total = stats.get("total_wins", 0)
        xp = wins_total * 10
        ranking.append((int(uid), xp))

    ranking.sort(key=lambda x: x[1], reverse=True)
    return ranking[:10]
