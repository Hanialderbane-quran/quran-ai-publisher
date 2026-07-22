"""
Quran AI Publisher
Assets Manager
Version 1.0
"""

import os

BACKGROUND_FOLDER = "assets/backgrounds"
FONT_FOLDER = "assets/fonts"
AUDIO_FOLDER = "assets/audio"
LOGO_FOLDER = "assets/logo"


def check_assets():

    folders = [
        BACKGROUND_FOLDER,
        FONT_FOLDER,
        AUDIO_FOLDER,
        LOGO_FOLDER
    ]

    for folder in folders:
        os.makedirs(folder, exist_ok=True)

    print()
    print("========== ASSETS ==========")
    print("Assets folders verified.")
    print("============================")

    return True
