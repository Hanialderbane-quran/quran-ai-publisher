"""
Quran AI Publisher
Audio Engine
Version 1.0
"""

import os
import random

AUDIO_FOLDER = "assets/audio"


def get_audio():

    files = []

    for file in os.listdir(AUDIO_FOLDER):

        if file.lower().endswith((".mp3", ".wav")):
            files.append(file)

    if len(files) == 0:

        print("No audio found.")

        return None

    selected = random.choice(files)

    print()

    print("========== AUDIO ==========")
    print("Selected :", selected)
    print("===========================")

    return os.path.join(AUDIO_FOLDER, selected)
