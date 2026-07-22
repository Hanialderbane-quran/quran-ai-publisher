"""
Quran AI Publisher
Quran Channel Brain
Version 3.0

Chooses between Quran Shorts and long Quran videos,
then prepares a consecutive Quran segment.
"""

import json
import os
from datetime import datetime, timezone

from generator.segment_engine import choose_segment
from generator.seo import build_seo


CONFIG_FILE = "config.json"

DAY_NAMES = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday"
}


def load_config() -> dict:
    try:
        with open(
            CONFIG_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except FileNotFoundError as error:
        raise RuntimeError(
            "config.json was not found."
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "config.json contains invalid JSON."
        ) from error


def get_requested_video_type() -> str | None:
    """
    Allows GitHub Actions to request a specific type:

    VIDEO_TYPE=short
    VIDEO_TYPE=long
    """

    requested = os.getenv(
        "VIDEO_TYPE",
        ""
    ).strip().lower()

    if not requested:
        return None

    if requested not in {
        "short",
        "long"
    }:
        raise RuntimeError(
            "VIDEO_TYPE must be short or long."
        )

    return requested


def long_video_is_scheduled_today(
    config: dict
) -> bool:
    publishing = config.get(
        "publishing",
        {}
    )

    long_config = publishing.get(
        "long_videos",
        {}
    )

    if long_config.get(
        "enabled",
        False
    ) is not True:
        return False

    publish_days = long_config.get(
        "publish_days",
        []
    )

    normalized_days = {
        str(day).strip().lower()
        for day in publish_days
    }

    current_day = DAY_NAMES[
        datetime.now(
            timezone.utc
        ).weekday()
    ]

    return current_day in normalized_days


def shorts_are_enabled(
    config: dict
) -> bool:
    return (
        config
        .get("publishing", {})
        .get("shorts", {})
        .get("enabled", False)
        is True
    )


def choose_video_type(
    config: dict
) -> str:
    requested_type = (
        get_requested_video_type()
    )

    if requested_type:
        return requested_type

    if long_video_is_scheduled_today(
        config
    ):
        return "long"

    if shorts_are_enabled(
        config
    ):
        return "short"

    raise RuntimeError(
        "No publishing type is enabled today."
    )


def add_compatibility_fields(
    segment: dict
) -> dict:
    """
    Keeps the old video engine working while
    the project is being upgraded.
    """

    start_ayah = segment[
        "start_ayah"
    ]

    end_ayah = segment[
        "end_ayah"
    ]

    if start_ayah == end_ayah:
        ayah_label = str(start_ayah)
    else:
        ayah_label = (
            f"{start_ayah}–{end_ayah}"
        )

    segment["ayah"] = ayah_label
    segment["content_type"] = (
        segment["video_type"]
    )

    return segment


def think() -> dict | None:
    print()
    print("========== QURAN BRAIN ==========")

    config = load_config()

    video_type = choose_video_type(
        config
    )

    print(
        "Selected video type:",
        video_type
    )

    segment = choose_segment(
        video_type=video_type,
        save_selection=True
    )

    if segment is None:
        print(
            "No unpublished Quran segment "
            "is available."
        )
        return None

    segment = add_compatibility_fields(
        segment
    )

    seo = build_seo(
        segment
    )

    print(
        "Quran segment selected successfully."
    )

    print(
        "Surah:",
        segment["surah"]
    )

    print(
        "Ayahs:",
        segment["ayah"]
    )

    print(
        "Video type:",
        segment["video_type"]
    )

    print(
        "================================="
    )

    return {
        "verse": segment,
        "segment": segment,
        "seo": seo,
        "video_type": video_type
        }
