import json
from datetime import datetime

from generator.safety import run_safety_check
from generator.tasks import run_tasks
from generator.brain import think


def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)


def start():
    print("========== Quran AI Publisher ==========\n")

    run_tasks()

    if not run_safety_check():
        return

    config = load_config()

    print("Channel:", config["channel_name"])
    print("Time:", datetime.now())
    print()

    result = think()

    if result is None:
        return

    verse = result["verse"]
    seo = result["seo"]

    print("========== TODAY ==========")
    print(f"Surah : {verse['surah']}")
    print(f"Ayah  : {verse['ayah']}")
    print()

    print("Title:")
    print(seo["title"])
    print()

    print("Description:")
    print(seo["description"])
    print()

    print("Tags:")
    for tag in seo["tags"]:
        print("-", tag)

    print()
    print("Preparing daily Quran video...")


if __name__ == "__main__":
    start()
