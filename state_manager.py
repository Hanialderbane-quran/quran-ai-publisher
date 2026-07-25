"""
Quran AI Publisher
State Manager
Version 1.0
"""

import json

STATE_FILE = "data/state.json"


def load_state():

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=4)


def increase_video_counter():

    state = load_state()

    state["videos_published"] += 1

    save_state(state)


def update_last_publish(surah, ayah):

    state = load_state()

    state["last_published_surah"] = surah
    state["last_published_ayah"] = ayah

    save_state(state)
