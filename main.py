import json
from datetime import datetime
from generator.verse_selector import choose_verse


def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)


def start():
    config = load_config()

    print("Quran AI Publisher Started")
    print("Channel:", config["channel_name"])
    print("Time:", datetime.now())

    print("Selecting daily verse...")

    verse = choose_verse()

    if verse:
    print("Selected verse:")
    print("Surah:", verse["surah"])
    print("Ayah:", verse["ayah"])
    print("Text:", verse["text"])

    print("Verse saved to memory")

    print("Preparing daily Quran video...")
