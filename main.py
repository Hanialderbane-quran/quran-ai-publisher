import json
from datetime import datetime

from generator.safety import run_safety_check
from generator.verse_selector import choose_verse


def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)


def start():
    print("========== Quran AI Publisher ==========")

    if not run_safety_check():
        return

    config = load_config()

    print("Channel:", config["channel_name"])
    print("Time:", datetime.now())

    print("Selecting daily verse...")

    verse = choose_verse()

    if verse is None:
        print("No new verses available.")
        return

    print("Selected verse")
    print("------------------------")
    print("Surah :", verse["surah"])
    print("Ayah  :", verse["ayah"])
    print("Text  :", verse["text"])
    print("------------------------")

    print("Preparing daily Quran video...")


if __name__ == "__main__":
    start()
