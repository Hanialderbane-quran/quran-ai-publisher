import json
from datetime import datetime

from generator.safety import run_safety_check
from generator.tasks import run_tasks
from generator.brain import think
from generator.report_engine import create_report


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

    create_report(verse, seo)

    print()
    print("Everything is ready.")
    print("Preparing daily Quran video...")


if __name__ == "__main__":
    start()
