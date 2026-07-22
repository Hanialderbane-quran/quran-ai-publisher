import json
from datetime import datetime

from generator.tasks import run_tasks
from generator.safety import run_safety_check
from generator.assets_manager import check_assets
from generator.brain import think
from generator.quality_engine import validate
from generator.report_engine import create_report
from generator.video_engine import build_video
from generator.youtube_engine import upload
from generator.state_manager import (
    increase_video_counter,
    update_last_publish
)


def load_config():

    with open("config.json", "r", encoding="utf-8") as file:

        return json.load(file)


def start():

    print("========== Quran AI Publisher ==========")

    run_tasks()

    if not run_safety_check():
        return

    if not check_assets():
        return

    config = load_config()

    print()

    print("Channel :", config["channel_name"])

    print("Time :", datetime.now())

    result = think()

    if result is None:
        return

    verse = result["verse"]

    seo = result["seo"]

    if not validate(verse, seo):
        return

    create_report(verse, seo)

    video = build_video(verse, seo)

    upload(video, seo)

    update_last_publish(

        verse["surah"],

        verse["ayah"]

    )

    increase_video_counter()

    print()

    print("Daily Publisher Finished Successfully")


if __name__ == "__main__":
    start()
