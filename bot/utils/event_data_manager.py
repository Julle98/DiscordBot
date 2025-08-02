import json
import os
from ..config import EVENT_DATA_FILE

class EventDataManager:
    def __init__(self):
        self.data = self._load_data()

    def _load_data(self):
        if not os.path.exists('data'):
            os.makedirs('data') 
        if os.path.exists(EVENT_DATA_FILE):
            with open(EVENT_DATA_FILE, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return self._default_data()
        return self._default_data()

    def _save_data(self):
        with open(EVENT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def _default_data(self):
        return {
            "current_round": {
                "topic": None,
                "active": False,
                "submissions": {} 
            },
            "voting_active": False,
            "votes": {} 
        }

    def reset_round(self):
        self.data["current_round"] = self._default_data()["current_round"]
        self.data["voting_active"] = False
        self.data["votes"] = {}
        self._save_data()

    def set_round_active(self, topic):
        self.reset_round() 
        self.data["current_round"]["topic"] = topic
        self.data["current_round"]["active"] = True
        self._save_data()

    def get_current_round_topic(self):
        return self.data["current_round"]["topic"]

    def is_round_active(self):
        return self.data["current_round"]["active"]

    def add_submission(self, user_id, username, content):
        self.data["current_round"]["submissions"][str(user_id)] = {
            "username": username,
            "content": content
        }
        self._save_data()

    def get_submissions(self):
        return self.data["current_round"]["submissions"]

    def end_round_submission(self):
        self.data["current_round"]["active"] = False
        self._save_data()

    def set_voting_active(self, active):
        self.data["voting_active"] = active
        self._save_data()

    def is_voting_active(self):
        return self.data["voting_active"]

    def add_vote(self, voter_id, voted_user_id):
        self.data["votes"][str(voter_id)] = str(voted_user_id)
        self._save_data()

    def get_votes(self):
        return self.data["votes"]

    def get_vote_counts(self):
        vote_counts = {}
        for voter_id, voted_user_id in self.data["votes"].items():
            if voted_user_id in vote_counts:
                vote_counts[voted_user_id] += 1
            else:
                vote_counts[voted_user_id] = 1
        return vote_counts

def get_random_joke():
    jokes = [
        "Miksi pörriäinen on aina myöhässä? Koska se pörrää!",
        "Mitä vesi sanoi purolle? En minä mikään pullo ole!",
        "Mitä tiikeri sanoi pojalleen, kun se söi hänet? Nyt sinulla on tiikeri vatsassasi."
    ]
    import random
    return random.choice(jokes)