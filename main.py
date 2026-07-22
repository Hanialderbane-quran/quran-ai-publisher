import json
import os
from datetime import datetime

from generator.brain import think
from generator.quality_engine import validate
from generator.report_engine import create_report
from generator.safety import run_safety_check
from generator.tasks import run_tasks
from generator.video_engine import build_video


def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)


def start():
    print("========== Quran AI Publisher ==========")

    run_tasks()

    if not run_safety_check():
        raise RuntimeError("Safety check failed.")

    config = load_config()

    print("Channel:", config["channel_name"])
    print("Time:", datetime.now())
    print()

    result = think()

    if result is None:
        raise RuntimeError("No verse was selected.")

    verse = result["verse"]
    seo = result["seo"]

    if not validate(verse, seo):
        raise RuntimeError("Quality check failed.")

    create_report(verse, seo)

    video_path = build_video(verse, seo)

    if not os.path.exists(video_path):
        raise RuntimeError("The video was not created.")

    print()
    print("Video ready:", video_path)
    print("Publisher finished successfully.")


if __name__ == "__main__":
    start()
