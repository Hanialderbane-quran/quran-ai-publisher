"""Keyless Quran recitation audio from Al Quran Cloud CDN.

Downloads one MP3 per ayah by global Quran number, merges the selected
segment, and builds exact ayah timing plus estimated word timing.
"""
from __future__ import annotations

import os
from pathlib import Path

from generator.audio_engine import (
    AUDIO_FOLDER,
    CACHE_FOLDER,
    TIMING_FOLDER,
    audio_duration,
    download,
    ensure_folders,
    env_true,
    estimated_word_timeline,
    merge_audio,
    save_json,
    valid_audio,
)

DEFAULT_CDN_BASE = "https://cdn.islamic.network/quran/audio"
DEFAULT_EDITION = "ar.alafasy"
DEFAULT_BITRATE = "128"
DEFAULT_RECITER_NAME = "مشاري راشد العفاسي"


def _safe_component(value: str, fallback: str) -> str:
    value = value.strip()
    if not value:
        return fallback
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    clean = "".join(char for char in value if char in allowed)
    return clean or fallback


def get_segment_audio_package(segment: dict) -> dict:
    """Return a real-audio package without requiring API credentials."""
    ensure_folders()

    segment_id = str(segment["segment_id"])
    edition = _safe_component(
        os.getenv("QURAN_CDN_EDITION", DEFAULT_EDITION),
        DEFAULT_EDITION,
    )
    bitrate = _safe_component(
        os.getenv("QURAN_CDN_BITRATE", DEFAULT_BITRATE),
        DEFAULT_BITRATE,
    )
    cdn_base = os.getenv("QURAN_CDN_BASE", DEFAULT_CDN_BASE).rstrip("/")
    reciter_name = os.getenv("QURAN_CDN_RECITER_NAME", DEFAULT_RECITER_NAME).strip()

    paths: list[Path] = []
    ayah_timeline: list[dict] = []
    word_timeline: list[dict] = []
    current = 0.0

    for ayah in segment["ayahs"]:
        global_number = int(ayah["global_number"])
        cache_path = (
            CACHE_FOLDER
            / "alquran-cloud"
            / edition
            / bitrate
            / f"{global_number}.mp3"
        )
        audio_url = f"{cdn_base}/{bitrate}/{edition}/{global_number}.mp3"
        path = download(audio_url, cache_path)

        if not valid_audio(path):
            raise RuntimeError(
                f"Downloaded recitation is missing or invalid for global ayah {global_number}."
            )

        duration = audio_duration(path)
        end = current + duration
        paths.append(path)
        ayah_timeline.append({
            "ayah": ayah,
            "start": round(current, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
        })
        word_timeline.extend(
            estimated_word_timeline(ayah, current, end)
        )
        current = end

    if not paths:
        raise RuntimeError("The selected Quran segment contains no ayahs for audio.")

    output = AUDIO_FOLDER / f"{segment_id}.mp3"
    if not valid_audio(output):
        merge_audio(paths, output, segment_id)

    if not valid_audio(output):
        raise RuntimeError("The merged Quran recitation audio is invalid.")

    package = {
        "audio_path": str(output),
        "duration": round(audio_duration(output), 3),
        "ayah_timeline": ayah_timeline,
        "word_timeline": word_timeline,
        "audio_mode": "cdn",
        "test_mode": False,
        "exact_ayah_sync": True,
        "exact_word_sync": False,
        "rights_confirmed": env_true("AUDIO_RIGHTS_CONFIRMED", False),
        "audio_source": "Al Quran Cloud CDN",
        "audio_edition": edition,
        "audio_bitrate_kbps": int(bitrate),
        "reciter": {
            "name": reciter_name,
            "edition": edition,
        },
    }

    save_json(TIMING_FOLDER / f"{segment_id}.json", package)
    return package
