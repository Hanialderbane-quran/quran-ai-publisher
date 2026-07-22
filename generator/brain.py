"""
Quran AI Publisher
Quran Channel Brain
Version 3.1

Chooses between Quran Shorts and long Quran videos,
then prepares a consecutive Quran segment.

Testing behavior:
- If the full Quran dataset is not available,
  the system prefers a short video.
- A manual VIDEO_TYPE environment variable
  can still force short or long.
"""

import json
import os
from datetime import datetime, timezone

from generator.segment_engine import choose_segment
from generator.seo import build_seo


CONFIG_FILE = "config.json"
QURAN_FILE = "data/quran.json"

DAY_NAMES = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday"
}


def load_json_file(
    path: str,
    error_name: str
) -> dict | list:
    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except FileNotFoundError as error:
        raise RuntimeError(
            f"{error_name} was not found: {path}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{error_name} contains invalid JSON: {path}"
        ) from error


def load_config() -> dict:
    config = load_json_file(
        CONFIG_FILE,
        "Configuration file"
    )

    if not isinstance(
        config,
        dict
    ):
        raise RuntimeError(
            "config.json must contain a JSON object."
        )

    return config


def get_quran_ayah_count() -> int:
    quran = load_json_file(
        QURAN_FILE,
        "Quran data file"
    )

    if not isinstance(
        quran,
        list
    ):
        raise RuntimeError(
            "data/quran.json must contain a list."
        )

    return len(quran)


def full_quran_dataset_is_available() -> bool:
    """
    The standard Quran contains 6236 numbered ayahs.

    During development, the repository may contain
    only a small test dataset. In that case, long
    videos are skipped automatically.
    """

    ayah_count = get_quran_ayah_count()

    print(
        "Quran ayahs available:",
        ayah_count
    )

    return ayah_count >= 6236


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

    print(
        "Current UTC day:",
        current_day
    )

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


def long_videos_are_enabled(
    config: dict
) -> bool:
    return (
        config
        .get("publishing", {})
        .get("long_videos", {})
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
        if (
            requested_type == "long"
            and not full_quran_dataset_is_available()
        ):
            print(
                "Requested long video cannot be created "
                "because the full Quran dataset is not "
                "available."
            )

            if shorts_are_enabled(
                config
            ):
                print(
                    "Falling back to short video."
                )
                return "short"

            raise RuntimeError(
                "Long video requested, but the Quran "
                "dataset is incomplete and Shorts are "
                "disabled."
            )

        return requested_type

    if (
        long_video_is_scheduled_today(
            config
        )
        and long_videos_are_enabled(
            config
        )
    ):
        if full_quran_dataset_is_available():
            return "long"

        print(
            "Long video skipped because "
            "data/quran.json is incomplete."
        )

    if shorts_are_enabled(
        config
    ):
        return "short"

    if (
        long_videos_are_enabled(
            config
        )
        and full_quran_dataset_is_available()
    ):
        return "long"

    raise RuntimeError(
        "No publishing type is available."
    )


def add_compatibility_fields(
    segment: dict
) -> dict:
    """
    Keeps older project files compatible while
    the system is being upgraded.
    """

    start_ayah = segment[
        "start_ayah"
    ]

    end_ayah = segment[
        "end_ayah"
    ]

    if start_ayah == end_ayah:
        ayah_label = str(
            start_ayah
        )
    else:
        ayah_label = (
            f"{start_ayah}–{end_ayah}"
        )

    segment["ayah"] = ayah_label

    segment["content_type"] = (
        segment["video_type"]
    )

    return segment


def select_segment_with_fallback(
    video_type: str,
    config: dict
) -> tuple[dict | None, str]:
    """
    Tries the selected type first.

    If a long segment is unavailable, it falls back
    to a short segment instead of stopping the
    workflow immediately.
    """

    segment = choose_segment(
        video_type=video_type,
        save_selection=True
    )

    if segment is not None:
        return segment, video_type

    if (
        video_type == "long"
        and shorts_are_enabled(
            config
        )
    ):
        print(
            "No long segment was available."
        )

        print(
            "Trying a short Quran segment instead."
        )

        segment = choose_segment(
            video_type="short",
            save_selection=True
        )

        if segment is not None:
            return segment, "short"

    return None, video_type


def think() -> dict | None:
    print()
    print(
        "========== QURAN BRAIN =========="
    )

    config = load_config()

    video_type = choose_video_type(
        config
    )

    print(
        "Selected video type:",
        video_type
    )

    segment, final_video_type = (
        select_segment_with_fallback(
            video_type=video_type,
            config=config
        )
    )

    if segment is None:
        print(
            "No unpublished Quran segment "
            "is available."
        )

        return None

    segment["video_type"] = (
        final_video_type
    )

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
        "video_type": final_video_type
    }
