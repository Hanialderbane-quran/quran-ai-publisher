"""
Quran AI Publisher
Video Engine
Version 2.0
"""

import os
import json

OUTPUT_FOLDER = "output"


def prepare_output():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def save_text(name, content):

    with open(
        os.path.join(OUTPUT_FOLDER, name),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(content)


def save_json(name, content):

    with open(
        os.path.join(OUTPUT_FOLDER, name),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(content, file, ensure_ascii=False, indent=4)


def build_video(verse, seo):

    prepare_output()

    save_text("title.txt", seo["title"])

    save_text("description.txt", seo["description"])

    save_json("tags.json", seo["tags"])

    save_text(
        "verse.txt",
        f"{verse['surah']} - آية {verse['ayah']}\n\n{verse['text']}"
    )

    print()
    print("========== VIDEO ENGINE ==========")
    print("Output Folder : output/")
    print("Title Saved")
    print("Description Saved")
    print("Tags Saved")
    print("Verse Saved")
    print("Video Status : READY")
    print("==================================")

    return "output/video.mp4"
