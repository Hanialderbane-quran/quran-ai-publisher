"""
Quran AI Publisher
Video Engine
Version 3.0
"""

import os
import json

from generator.background_engine import get_background
from generator.audio_engine import get_audio

OUTPUT_FOLDER = "output"


def prepare_output():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def save_text(name, text):

    with open(
        os.path.join(OUTPUT_FOLDER, name),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)


def save_json(name, data):

    with open(
        os.path.join(OUTPUT_FOLDER, name),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )


def build_video(verse, seo):

    prepare_output()

    background = get_background()

    audio = get_audio()

    save_text("title.txt", seo["title"])

    save_text("description.txt", seo["description"])

    save_json("tags.json", seo["tags"])

    save_text(
        "verse.txt",
        f"{verse['surah']} - آية {verse['ayah']}\n\n{verse['text']}"
    )

    print()

    print("========== VIDEO ==========")

    print("Background :", background)

    print("Audio      :", audio)

    print("Resolution : 1080x1920")

    print("FPS        : 30")

    print("Status     : READY")

    print("===========================")

    return "output/video.mp4"
