"""
Quran AI Publisher
Background Engine
Version 1.0
"""

import os
import random

BACKGROUND_FOLDER = "assets/backgrounds"


def get_background():

    files = []

    for file in os.listdir(BACKGROUND_FOLDER):

        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            files.append(file)

    if len(files) == 0:

        print("No backgrounds found.")

        return None

    selected = random.choice(files)

    print()

    print("========== BACKGROUND ==========")
    print("Selected :", selected)
    print("================================")

    return os.path.join(BACKGROUND_FOLDER, selected)
