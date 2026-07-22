"""
Quran AI Publisher
Safe Quran Segment Audio Engine
Version 4.0

Downloads and merges consecutive ayah audio files.
Blocks all unapproved reciters and unverified sources.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import requests


RECITERS_FILE = "data/reciters.json"

AUDIO_FOLDER = Path("output/audio")
TEMP_FOLDER = AUDIO_FOLDER / "temporary"

REQUEST_TIMEOUT = 60
MAX_DOWNLOAD_ATTEMPTS = 3
MINIMUM_AUDIO_SIZE = 5000


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not read JSON file: {path}. "
            f"Error: {error}"
        ) from error


def ensure_audio_folders() -> None:
    AUDIO_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    TEMP_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )


def load_reciter_config() -> dict:
    data = load_json(
        RECITERS_FILE,
        {}
    )

    if not isinstance(data, dict):
        raise RuntimeError(
            "data/reciters.json must contain an object."
        )

    selected_reciter = data.get(
        "selected_reciter"
    )

    reciters = data.get(
        "reciters",
        {}
    )

    if not selected_reciter:
        raise RuntimeError(
            "No selected_reciter was configured."
        )

    if selected_reciter not in reciters:
        raise RuntimeError(
            "The selected reciter does not exist "
            "inside data/reciters.json."
        )

    reciter = reciters[selected_reciter]

    validate_reciter(reciter)

    reciter["id"] = selected_reciter

    return reciter


def validate_reciter(reciter: dict) -> None:
    required_fields = [
        "name",
        "source_name",
        "url_template",
        "approved",
        "license_verified",
        "copyright_claim_history"
    ]

    for field in required_fields:
        if field not in reciter:
            raise RuntimeError(
                f"Reciter configuration is missing: {field}"
            )

    if reciter.get("approved") is not True:
        raise RuntimeError(
            "Audio blocked: this reciter has not been approved."
        )

    if reciter.get("license_verified") is not True:
        raise RuntimeError(
            "Audio blocked: the reuse license has not "
            "been verified."
        )

    claim_history = str(
        reciter.get(
            "copyright_claim_history",
            "unknown"
        )
    ).lower()

    if claim_history not in {
        "none",
        "clear"
    }:
        raise RuntimeError(
            "Audio blocked because its copyright-claim "
            "history is not clear."
        )

    url_template = str(
        reciter.get(
            "url_template",
            ""
        )
    )

    if "{global_number}" not in url_template:
        raise RuntimeError(
            "The audio URL template must contain "
            "{global_number}."
        )


def validate_audio_file(path: Path) -> bool:
    if not path.is_file():
        return False

    if path.stat().st_size < MINIMUM_AUDIO_SIZE:
        return False

    try:
        with path.open("rb") as file:
            first_bytes = file.read(20)
    except OSError:
        return False

    invalid_starts = (
        b"<",
        b"{",
        b"[",
        b"<!DOCTYPE",
        b"<?xml"
    )

    if first_bytes.startswith(invalid_starts):
        return False

    return True


def get_global_number(ayah: dict) -> int:
    possible_keys = [
        "global_number",
        "global_ayah",
        "number"
    ]

    for key in possible_keys:
        value = ayah.get(key)

        if value is None:
            continue

        try:
            number = int(value)
        except (TypeError, ValueError):
            continue

        if 1 <= number <= 6236:
            return number

    raise RuntimeError(
        "Ayah does not contain a valid global number."
    )


def create_audio_url(
    reciter: dict,
    global_number: int
) -> str:
    return reciter["url_template"].format(
        global_number=global_number
    )


def download_audio(
    url: str,
    destination: Path
) -> Path:
    temporary_path = destination.with_suffix(
        ".download"
    )

    headers = {
        "User-Agent": (
            "Quran-AI-Publisher/4.0 "
            "(GitHub Actions)"
        )
    }

    last_error = None

    for attempt in range(
        1,
        MAX_DOWNLOAD_ATTEMPTS + 1
    ):
        print(
            "Downloading audio:",
            destination.name,
            f"attempt {attempt}/"
            f"{MAX_DOWNLOAD_ATTEMPTS}"
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

            blocked_types = [
                "text/html",
                "application/json",
                "text/plain"
            ]

            if any(
                blocked in content_type
                for blocked in blocked_types
            ):
                raise RuntimeError(
                    "Audio server returned invalid type: "
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

            os.replace(
                temporary_path,
                destination
            )

            if not validate_audio_file(destination):
                destination.unlink(
                    missing_ok=True
                )

                raise RuntimeError(
                    "Downloaded audio is invalid or empty."
                )

            return destination

        except (
            requests.RequestException,
            RuntimeError,
            OSError
        ) as error:
            last_error = error

            temporary_path.unlink(
                missing_ok=True
            )

            destination.unlink(
                missing_ok=True
            )

            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                time.sleep(attempt * 2)

    raise RuntimeError(
        "Failed to download Quran audio. "
        f"Last error: {last_error}"
    )


def get_ayah_audio(
    ayah: dict,
    reciter: dict
) -> Path:
    global_number = get_global_number(
        ayah
    )

    reciter_folder = (
        AUDIO_FOLDER
        / "cache"
        / reciter["id"]
    )

    reciter_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    audio_path = reciter_folder / (
        f"{global_number}.mp3"
    )

    if validate_audio_file(audio_path):
        print(
            "Using cached ayah audio:",
            global_number
        )

        return audio_path

    url = create_audio_url(
        reciter,
        global_number
    )

    return download_audio(
        url,
        audio_path
    )


def check_ffmpeg() -> None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-version"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg is not installed."
        ) from error

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg is not working correctly."
        )


def create_concat_file(
    audio_paths: list[Path],
    segment_id: str
) -> Path:
    concat_path = TEMP_FOLDER / (
        f"{segment_id}_files.txt"
    )

    with concat_path.open(
        "w",
        encoding="utf-8"
    ) as file:
        for audio_path in audio_paths:
            absolute_path = (
                audio_path
                .resolve()
                .as_posix()
            )

            safe_path = absolute_path.replace(
                "'",
                "'\\''"
            )

            file.write(
                f"file '{safe_path}'\n"
            )

    return concat_path


def merge_audio_files(
    audio_paths: list[Path],
    output_path: Path,
    segment_id: str
) -> Path:
    if not audio_paths:
        raise RuntimeError(
            "No ayah audio files were supplied."
        )

    if len(audio_paths) == 1:
        source = audio_paths[0]

        output_path.write_bytes(
            source.read_bytes()
        )

        return output_path

    check_ffmpeg()

    concat_path = create_concat_file(
        audio_paths,
        segment_id
    )

    temporary_output = output_path.with_suffix(
        ".temporary.mp3"
    )

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "128k",
        str(temporary_output)
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False
    )

    concat_path.unlink(
        missing_ok=True
    )

    if process.returncode != 0:
        temporary_output.unlink(
            missing_ok=True
        )

        error_message = (
            process.stderr[-1500:]
            if process.stderr
            else "Unknown FFmpeg error."
        )

        raise RuntimeError(
            "Could not merge Quran audio files. "
            f"FFmpeg error: {error_message}"
        )

    os.replace(
        temporary_output,
        output_path
    )

    if not validate_audio_file(output_path):
        output_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "Merged Quran audio file is invalid."
        )

    return output_path


def get_segment_audio(
    segment: dict
) -> str:
    ensure_audio_folders()

    if not isinstance(segment, dict):
        raise RuntimeError(
            "Segment must be an object."
        )

    ayahs = segment.get(
        "ayahs",
        []
    )

    segment_id = str(
        segment.get(
            "segment_id",
            ""
        )
    ).strip()

    if not segment_id:
        raise RuntimeError(
            "Segment does not contain segment_id."
        )

    if not isinstance(ayahs, list) or not ayahs:
        raise RuntimeError(
            "Segment does not contain any ayahs."
        )

    reciter = load_reciter_config()

    output_path = AUDIO_FOLDER / (
        f"{segment_id}.mp3"
    )

    if validate_audio_file(output_path):
        print()
        print("========== AUDIO ==========")
        print("Using cached segment audio")
        print("Reciter:", reciter["name"])
        print("File:", output_path)
        print("===========================")

        return str(output_path)

    audio_paths = []

    print()
    print("========== AUDIO ==========")
    print("Reciter:", reciter["name"])
    print("Source:", reciter["source_name"])
    print("Ayah count:", len(ayahs))
    print("===========================")

    for index, ayah in enumerate(
        ayahs,
        start=1
    ):
        print(
            f"Preparing ayah "
            f"{index}/{len(ayahs)}"
        )

        audio_path = get_ayah_audio(
            ayah,
            reciter
        )

        audio_paths.append(
            audio_path
        )

    merged_path = merge_audio_files(
        audio_paths=audio_paths,
        output_path=output_path,
        segment_id=segment_id
    )

    print()
    print(
        "Segment audio ready:",
        merged_path
    )

    return str(merged_path)


def get_audio(content: dict) -> str:
    """
    Compatibility function.

    Accepts a Quran segment. A single ayah is also
    converted into a one-ayah segment.
    """

    if not isinstance(content, dict):
        raise RuntimeError(
            "Audio content must be an object."
        )

    if content.get("ayahs"):
        return get_segment_audio(content)

    global_number = get_global_number(
        content
    )

    single_segment = {
        "segment_id": f"single_{global_number}",
        "ayahs": [content]
    }

    return get_segment_audio(
        single_segment
    )


if __name__ == "__main__":
    print(
        "Audio Engine installed successfully. "
        "It must be called using a Quran segment."
    )
