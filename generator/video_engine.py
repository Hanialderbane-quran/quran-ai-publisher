"""
Quran AI Publisher
Video Engine
Version: 1.0
"""

import os
import json


OUTPUT_FOLDER = "output"


def prepare_output():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)


def save_seo_files(seo):
    prepare_output()

    with open("output/title.txt", "w", encoding="utf-8") as file:
        file.write(seo["title"])

    with open("output/description.txt", "w", encoding="utf-8") as file:
        file.write(seo["description"])

    with open("output/tags.json", "w", encoding="utf-8") as file:
        json.dump(seo["tags"], file, ensure_ascii=False, indent=4)

    print("SEO files created successfully.")


def build_video(verse, seo):
    prepare_output()

    save_seo_files(seo)

    print("===================================")
    print("Video Engine")
    print("-----------------------------------")
    print("Video Size : 1080x1920")
    print("FPS        : 30")
    print("Status     : READY")
    print("===================================")

    return True
