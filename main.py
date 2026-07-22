import json
import os
from datetime import datetime

from generator.brain import think
from generator.progress_engine import mark_segment_completed, record_segment_error
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
    segment_id = None

    try:
        run_tasks()

        if not run_safety_check():
            raise RuntimeError("Safety check failed.")

        config = load_config()
        print("Channel:", config["channel_name"])
        print("Time:", datetime.now())
        print()

        result = think()
        if result is None:
            print("Nothing new to render.")
            return

        verse = result["verse"]
        seo = result["seo"]
        segment_id = verse["segment_id"]

        if not validate(verse, seo):
            raise RuntimeError("Quality check failed.")

        create_report(verse, seo)
        video_path = build_video(verse, seo)

        if not os.path.exists(video_path):
            raise RuntimeError("The video was not created.")

        # Temporary completion point. Move this call to after successful
        # PRIVATE YouTube upload when the uploader is connected.
        mark_segment_completed(segment_id)

        print("\nVideo ready:", video_path)
        print("Progress saved successfully.")
        print("Publisher finished successfully.")

    except Exception as error:
        if segment_id:
            record_segment_error(str(error))
        raise


if __name__ == "__main__":
    start()
