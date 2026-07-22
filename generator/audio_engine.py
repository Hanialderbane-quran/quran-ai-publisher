"""
Quran AI Publisher
Audio Engine
Version 2.0

Audio files must be named like:

001_001.mp3
001_002.mp3
001_003.mp3

First three digits: Surah number
Last three digits: Ayah number
"""

import os


AUDIO_FOLDER = "assets/audio"

SUPPORTED_EXTENSIONS = (
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg"
)


def build_audio_filename(surah_number, ayah_number):

    surah_part = str(int(surah_number)).zfill(3)
    ayah_part = str(int(ayah_number)).zfill(3)

    return f"{surah_part}_{ayah_part}"


def find_audio_file(verse):

    if "surah_number" not in verse:
        raise KeyError(
            "The verse is missing 'surah_number' in data/quran.json."
        )

    if "ayah" not in verse:
        raise KeyError(
            "The verse is missing 'ayah' in data/quran.json."
        )

    base_name = build_audio_filename(
        verse["surah_number"],
        verse["ayah"]
    )

    for extension in SUPPORTED_EXTENSIONS:

        audio_path = os.path.join(
            AUDIO_FOLDER,
            base_name + extension
        )

        if os.path.isfile(audio_path):
            return audio_path

    expected = os.path.join(
        AUDIO_FOLDER,
        base_name + ".mp3"
    )

    raise FileNotFoundError(
        "\nAudio file was not found.\n"
        f"Upload the correct recitation to:\n{expected}\n"
        "The system will not use random audio because that could "
        "attach the wrong recitation to the verse."
    )


def get_audio(verse):

    os.makedirs(AUDIO_FOLDER, exist_ok=True)

    audio_path = find_audio_file(verse)

    print()
    print("========== AUDIO ==========")
    print("Audio:", audio_path)
    print("===========================")

    return audio_path
