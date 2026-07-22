"""
Quran AI Publisher
Automatic Quran Audio Engine
Version 3.0

Automatically downloads the exact selected ayah recitation.
No manual audio upload is required.
"""

import os
import time
from pathlib import Path

import requests


AUDIO_FOLDER = Path("output/audio")

# Mishary Rashid Alafasy
RECITER = "ar.alafasy"

AUDIO_QUALITY = 128

REQUEST_TIMEOUT = 60
MAX_DOWNLOAD_ATTEMPTS = 3


def ensure_audio_folder():
    AUDIO_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )


def get_global_ayah_number(verse):

    possible_keys = [
        "global_ayah",
        "global_number",
        "number"
    ]

    for key in possible_keys:

        value = verse.get(key)

        if value is not None:

            try:
                value = int(value)

                if 1 <= value <= 6236:
                    return value

            except (TypeError, ValueError):
                pass

    raise KeyError(
        "The selected verse does not contain a valid "
        "global Quran ayah number."
    )


def create_audio_url(global_ayah_number):

    return (
        "https://cdn.islamic.network/quran/audio/"
        f"{AUDIO_QUALITY}/"
        f"{RECITER}/"
        f"{global_ayah_number}.mp3"
    )


def validate_downloaded_audio(audio_path):

    if not audio_path.is_file():
        return False

    file_size = audio_path.stat().st_size

    if file_size < 5000:
        return False

    with audio_path.open("rb") as file:
        first_bytes = file.read(16)

    if (
        first_bytes.startswith(b"<")
        or first_bytes.startswith(b"{")
        or first_bytes.startswith(b"[")
    ):
        return False

    return True


def download_audio(url, audio_path):

    temporary_path = audio_path.with_suffix(
        ".download"
    )

    headers = {
        "User-Agent": (
            "Quran-AI-Publisher/1.0 "
            "(GitHub Actions)"
        )
    }

    last_error = None

    for attempt in range(
        1,
        MAX_DOWNLOAD_ATTEMPTS + 1
    ):

        print(
            f"Downloading recitation "
            f"attempt {attempt}/"
            f"{MAX_DOWNLOAD_ATTEMPTS}..."
        )

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                stream=True
            )

            response.raise_for_status()

            content_type = (
                response.headers
                .get("content-type", "")
                .lower()
            )

            if (
                "text/html" in content_type
                or "application/json" in content_type
            ):
                raise RuntimeError(
                    "The audio server returned "
                    f"an invalid content type: "
                    f"{content_type}"
                )

            with temporary_path.open(
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 64
                ):

                    if chunk:
                        file.write(chunk)

            temporary_path.replace(
                audio_path
            )

            if validate_downloaded_audio(
                audio_path
            ):
                return audio_path

            audio_path.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                "The downloaded audio file "
                "is invalid or empty."
            )

        except (
            requests.RequestException,
            RuntimeError,
            OSError
        ) as error:

            last_error = error

            temporary_path.unlink(
                missing_ok=True
            )

            audio_path.unlink(
                missing_ok=True
            )

            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                time.sleep(attempt * 2)

    raise RuntimeError(
        "Failed to download the Quran "
        f"recitation after "
        f"{MAX_DOWNLOAD_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )


def get_audio(verse):

    ensure_audio_folder()

    global_ayah_number = (
        get_global_ayah_number(verse)
    )

    audio_path = AUDIO_FOLDER / (
        f"{global_ayah_number}.mp3"
    )

    if validate_downloaded_audio(
        audio_path
    ):

        print()
        print("========== AUDIO ==========")
        print("Using cached recitation")
        print("Ayah:", global_ayah_number)
        print("File:", audio_path)
        print("===========================")

        return str(audio_path)

    audio_url = create_audio_url(
        global_ayah_number
    )

    print()
    print("========== AUDIO ==========")
    print("Reciter:", RECITER)
    print(
        "Global ayah:",
        global_ayah_number
    )
    print("===========================")

    download_audio(
        audio_url,
        audio_path
    )

    print(
        "Recitation downloaded:",
        audio_path
    )

    return str(audio_path)
