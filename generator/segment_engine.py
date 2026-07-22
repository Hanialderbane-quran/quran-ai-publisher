"""
Quran AI Publisher
Quran Segment Engine
Version 1.0

Builds consecutive Quran segments for Shorts and long videos.
Never cuts inside an ayah.
"""

import hashlib
import json
import os
import random
from datetime import datetime
from typing import Any


QURAN_FILE = "data/quran.json"
PUBLISHED_FILE = "data/published_segments.json"
CONFIG_FILE = "config.json"

SHORT_MIN_SECONDS = 30
SHORT_MAX_SECONDS = 60

LONG_MIN_SECONDS = 10 * 60
LONG_MAX_SECONDS = 25 * 60

DEFAULT_SECONDS_PER_WORD = 0.55
MINIMUM_AYAH_SECONDS = 2.5


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(
            f"Could not read JSON file: {path}. Error: {error}"
        ) from error


def save_json(path: str, data: Any) -> None:
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    temporary_path = f"{path}.tmp"

    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temporary_path, path)


def load_config() -> dict:
    return load_json(CONFIG_FILE, {})


def load_quran() -> list[dict]:
    quran = load_json(QURAN_FILE, [])

    if not isinstance(quran, list):
        raise RuntimeError(
            "data/quran.json must contain a list of ayahs."
        )

    if not quran:
        raise RuntimeError(
            "data/quran.json is empty."
        )

    return normalize_quran(quran)


def load_published_segments() -> list[dict]:
    published = load_json(PUBLISHED_FILE, [])

    if not isinstance(published, list):
        return []

    return published


def normalize_number(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid {field_name}: {value}"
        ) from error

    return number


def normalize_ayah(raw_ayah: dict) -> dict:
    if not isinstance(raw_ayah, dict):
        raise ValueError("Every Quran item must be an object.")

    surah_name = (
        raw_ayah.get("surah")
        or raw_ayah.get("surah_name")
        or raw_ayah.get("name")
    )

    ayah_number = (
        raw_ayah.get("ayah")
        or raw_ayah.get("ayah_number")
        or raw_ayah.get("number_in_surah")
    )

    global_number = (
        raw_ayah.get("global_ayah")
        or raw_ayah.get("global_number")
        or raw_ayah.get("number")
    )

    text = (
        raw_ayah.get("text")
        or raw_ayah.get("text_uthmani")
        or raw_ayah.get("arabic")
    )

    surah_number = (
        raw_ayah.get("surah_number")
        or raw_ayah.get("chapter")
        or raw_ayah.get("surah_id")
    )

    if not surah_name:
        raise ValueError("Ayah is missing the Surah name.")

    if ayah_number is None:
        raise ValueError("Ayah is missing its number.")

    if global_number is None:
        raise ValueError(
            "Ayah is missing its global Quran number."
        )

    if not text or not str(text).strip():
        raise ValueError("Ayah text is empty.")

    normalized = {
        "surah": str(surah_name).strip(),
        "ayah": normalize_number(
            ayah_number,
            "ayah number"
        ),
        "global_number": normalize_number(
            global_number,
            "global ayah number"
        ),
        "text": str(text).strip()
    }

    if surah_number is not None:
        normalized["surah_number"] = normalize_number(
            surah_number,
            "surah number"
        )

    return normalized


def normalize_quran(quran: list[dict]) -> list[dict]:
    normalized = []

    for raw_ayah in quran:
        try:
            normalized.append(normalize_ayah(raw_ayah))
        except ValueError as error:
            print("Blocked invalid Quran item:", error)

    if not normalized:
        raise RuntimeError(
            "No valid Quran ayahs were found."
        )

    normalized.sort(
        key=lambda ayah: ayah["global_number"]
    )

    validate_quran_order(normalized)

    return normalized


def validate_quran_order(quran: list[dict]) -> None:
    seen_global_numbers = set()

    for ayah in quran:
        global_number = ayah["global_number"]

        if global_number in seen_global_numbers:
            raise RuntimeError(
                "Duplicate global ayah number found: "
                f"{global_number}"
            )

        seen_global_numbers.add(global_number)

    for previous, current in zip(quran, quran[1:]):
        if current["global_number"] <= previous["global_number"]:
            raise RuntimeError(
                "Quran ayahs are not in the correct order."
            )


def estimate_ayah_duration(ayah: dict) -> float:
    text = ayah["text"]
    word_count = len(text.split())

    estimated = word_count * DEFAULT_SECONDS_PER_WORD

    return max(
        MINIMUM_AYAH_SECONDS,
        estimated
    )


def group_by_surah(quran: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current_group: list[dict] = []
    current_surah = None

    for ayah in quran:
        surah_key = (
            ayah.get("surah_number"),
            ayah["surah"]
        )

        if current_surah is None:
            current_surah = surah_key

        if surah_key != current_surah:
            if current_group:
                groups.append(current_group)

            current_group = []
            current_surah = surah_key

        current_group.append(ayah)

    if current_group:
        groups.append(current_group)

    return groups


def get_duration_limits(video_type: str) -> tuple[int, int]:
    config = load_config()
    publishing = config.get("publishing", {})

    if video_type == "short":
        short_config = publishing.get("shorts", {})

        minimum = int(
            short_config.get(
                "minimum_duration_seconds",
                SHORT_MIN_SECONDS
            )
        )

        maximum = int(
            short_config.get(
                "maximum_duration_seconds",
                SHORT_MAX_SECONDS
            )
        )

        return minimum, maximum

    if video_type == "long":
        long_config = publishing.get(
            "long_videos",
            {}
        )

        minimum_minutes = int(
            long_config.get(
                "minimum_duration_minutes",
                10
            )
        )

        maximum_minutes = int(
            long_config.get(
                "maximum_duration_minutes",
                25
            )
        )

        return (
            minimum_minutes * 60,
            maximum_minutes * 60
        )

    raise ValueError(
        "video_type must be 'short' or 'long'."
    )


def build_segment_id(
    surah: str,
    start_ayah: int,
    end_ayah: int,
    video_type: str
) -> str:
    raw_value = (
        f"{surah}|{start_ayah}|"
        f"{end_ayah}|{video_type}"
    )

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()[:20]


def build_candidate(
    ayahs: list[dict],
    video_type: str
) -> dict:
    first = ayahs[0]
    last = ayahs[-1]

    duration = sum(
        estimate_ayah_duration(ayah)
        for ayah in ayahs
    )

    combined_text = "\n".join(
        ayah["text"]
        for ayah in ayahs
    )

    segment_id = build_segment_id(
        first["surah"],
        first["ayah"],
        last["ayah"],
        video_type
    )

    return {
        "segment_id": segment_id,
        "video_type": video_type,
        "surah": first["surah"],
        "surah_number": first.get("surah_number"),
        "start_ayah": first["ayah"],
        "end_ayah": last["ayah"],
        "start_global_number": first["global_number"],
        "end_global_number": last["global_number"],
        "estimated_duration_seconds": round(
            duration,
            2
        ),
        "ayah_count": len(ayahs),
        "text": combined_text,
        "ayahs": ayahs
    }


def build_surah_candidates(
    surah_ayahs: list[dict],
    video_type: str,
    minimum_duration: int,
    maximum_duration: int
) -> list[dict]:
    candidates = []

    for start_index in range(len(surah_ayahs)):
        selected = []
        total_duration = 0.0

        for index in range(
            start_index,
            len(surah_ayahs)
        ):
            ayah = surah_ayahs[index]
            ayah_duration = estimate_ayah_duration(
                ayah
            )

            if (
                selected
                and total_duration + ayah_duration
                > maximum_duration
            ):
                break

            selected.append(ayah)
            total_duration += ayah_duration

            if (
                minimum_duration
                <= total_duration
                <= maximum_duration
            ):
                candidates.append(
                    build_candidate(
                        selected.copy(),
                        video_type
                    )
                )

        if not candidates and selected:
            first_ayah_duration = (
                estimate_ayah_duration(selected[0])
            )

            if (
                video_type == "short"
                and first_ayah_duration
                > maximum_duration
            ):
                candidates.append(
                    build_candidate(
                        [selected[0]],
                        video_type
                    )
                )

    return candidates


def published_segment_ids(
    published: list[dict]
) -> set[str]:
    ids = set()

    for item in published:
        if isinstance(item, dict):
            segment_id = item.get("segment_id")

            if segment_id:
                ids.add(str(segment_id))

    return ids


def choose_segment(
    video_type: str = "short",
    save_selection: bool = True
) -> dict | None:
    minimum_duration, maximum_duration = (
        get_duration_limits(video_type)
    )

    quran = load_quran()
    published = load_published_segments()
    used_ids = published_segment_ids(published)

    all_candidates = []

    for surah_ayahs in group_by_surah(quran):
        candidates = build_surah_candidates(
            surah_ayahs=surah_ayahs,
            video_type=video_type,
            minimum_duration=minimum_duration,
            maximum_duration=maximum_duration
        )

        for candidate in candidates:
            if candidate["segment_id"] not in used_ids:
                all_candidates.append(candidate)

    if not all_candidates:
        print(
            "No unpublished Quran segment is available "
            f"for video type: {video_type}"
        )
        return None

    selected = random.choice(all_candidates)

    if save_selection:
        published.append(
            {
                "segment_id": selected["segment_id"],
                "video_type": selected["video_type"],
                "surah": selected["surah"],
                "start_ayah": selected["start_ayah"],
                "end_ayah": selected["end_ayah"],
                "selected_at": datetime.utcnow().isoformat(
                    timespec="seconds"
                ) + "Z",
                "status": "selected_not_published"
            }
        )

        save_json(
            PUBLISHED_FILE,
            published
        )

    print()
    print("========== SEGMENT ==========")
    print("Type:", selected["video_type"])
    print("Surah:", selected["surah"])
    print(
        "Ayahs:",
        f"{selected['start_ayah']}"
        f"-{selected['end_ayah']}"
    )
    print(
        "Estimated duration:",
        selected["estimated_duration_seconds"],
        "seconds"
    )
    print(
        "Segment ID:",
        selected["segment_id"]
    )
    print("=============================")

    return selected


def choose_short_segment() -> dict | None:
    return choose_segment("short")


def choose_long_segment() -> dict | None:
    return choose_segment("long")


if __name__ == "__main__":
    test_segment = choose_short_segment()

    if test_segment:
        print()
        print(test_segment)
