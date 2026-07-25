"""
Quran AI Publisher
Ordered Quran Segment Engine
Version 2.0

Never selects randomly during the complete-Quran journey.
Reuses the same pending segment after a failed run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from generator.progress_engine import (
    get_pending_segment,
    load_progress,
    set_pending_segment,
)

QURAN_FILE = Path("data/quran.json")
CONFIG_FILE = Path("config.json")
DEFAULT_SECONDS_PER_WORD = 0.55
MINIMUM_AYAH_SECONDS = 2.5


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read {path}: {error}") from error


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE, {})
    if not isinstance(config, dict):
        raise RuntimeError("config.json must contain a JSON object.")
    return config


def _to_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid {field_name}: {value}") from error


def normalize_ayah(raw: dict[str, Any]) -> dict[str, Any]:
    surah = raw.get("surah") or raw.get("surah_name") or raw.get("name")
    ayah_number = raw.get("ayah") or raw.get("ayah_number") or raw.get("number_in_surah")
    global_number = raw.get("global_number") or raw.get("global_ayah") or raw.get("number")
    surah_number = raw.get("surah_number") or raw.get("chapter") or raw.get("surah_id")
    text = raw.get("text") or raw.get("text_uthmani") or raw.get("arabic")

    if not surah or ayah_number is None or global_number is None or not str(text or "").strip():
        raise RuntimeError("Invalid Quran ayah data.")

    normalized = {
        "surah": str(surah).strip(),
        "ayah": _to_int(ayah_number, "ayah number"),
        "global_number": _to_int(global_number, "global number"),
        "text": str(text).strip(),
    }
    if surah_number is not None:
        normalized["surah_number"] = _to_int(surah_number, "surah number")
    return normalized


def load_quran() -> list[dict[str, Any]]:
    data = load_json(QURAN_FILE, [])
    if not isinstance(data, list) or not data:
        raise RuntimeError("data/quran.json must contain Quran ayahs.")

    quran = [normalize_ayah(item) for item in data]
    quran.sort(key=lambda item: item["global_number"])

    seen: set[int] = set()
    previous = 0
    for ayah in quran:
        number = ayah["global_number"]
        if number in seen:
            raise RuntimeError(f"Duplicate global Quran number: {number}")
        if number <= previous:
            raise RuntimeError("Quran data is not in the correct order.")
        seen.add(number)
        previous = number
    return quran


def estimate_ayah_duration(ayah: dict[str, Any]) -> float:
    return max(
        MINIMUM_AYAH_SECONDS,
        len(str(ayah["text"]).split()) * DEFAULT_SECONDS_PER_WORD,
    )


def get_duration_limits(video_type: str) -> tuple[float, float]:
    publishing = load_config().get("publishing", {})
    if video_type == "short":
        settings = publishing.get("shorts", {})
        return (
            float(settings.get("minimum_duration_seconds", 8)),
            float(settings.get("maximum_duration_seconds", 60)),
        )
    if video_type == "long":
        settings = publishing.get("long_videos", {})
        return (
            float(settings.get("minimum_duration_minutes", 10)) * 60,
            float(settings.get("maximum_duration_minutes", 25)) * 60,
        )
    raise ValueError("video_type must be 'short' or 'long'.")


def build_segment_id(start_global: int, end_global: int, video_type: str) -> str:
    raw = f"{start_global}|{end_global}|{video_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _same_surah(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if first.get("surah_number") is not None and second.get("surah_number") is not None:
        return first["surah_number"] == second["surah_number"]
    return first["surah"] == second["surah"]


def _build_segment(ayahs: list[dict[str, Any]], video_type: str) -> dict[str, Any]:
    first, last = ayahs[0], ayahs[-1]
    duration = sum(estimate_ayah_duration(item) for item in ayahs)
    return {
        "segment_id": build_segment_id(
            first["global_number"], last["global_number"], video_type
        ),
        "video_type": video_type,
        "surah": first["surah"],
        "surah_number": first.get("surah_number"),
        "start_ayah": first["ayah"],
        "end_ayah": last["ayah"],
        "start_global_number": first["global_number"],
        "end_global_number": last["global_number"],
        "ayah_count": len(ayahs),
        "estimated_duration_seconds": round(duration, 2),
        "text": "\n".join(item["text"] for item in ayahs),
        "ayahs": ayahs,
    }


def _restore_pending_segment(
    pending: dict[str, Any],
    quran: list[dict[str, Any]],
) -> dict[str, Any]:
    start = int(pending["start_global_number"])
    end = int(pending["end_global_number"])
    ayahs = [a for a in quran if start <= a["global_number"] <= end]

    if len(ayahs) != end - start + 1:
        raise RuntimeError("Pending segment cannot be restored.")

    restored = _build_segment(ayahs, str(pending.get("video_type", "short")))
    if restored["segment_id"] != pending.get("segment_id"):
        raise RuntimeError("Pending segment does not match current Quran data.")
    return restored


def choose_segment(
    video_type: str = "short",
    save_selection: bool = True,
) -> dict[str, Any] | None:
    quran = load_quran()

    pending = get_pending_segment()
    if pending is not None:
        print("Reusing pending Quran segment:", pending["segment_id"])
        return _restore_pending_segment(pending, quran)

    next_global = int(load_progress()["last_completed_global_ayah"]) + 1
    by_global = {item["global_number"]: item for item in quran}
    first = by_global.get(next_global)

    if first is None:
        print("The available Quran dataset has been completed.")
        return None

    minimum, maximum = get_duration_limits(video_type)
    same_surah_ayahs: list[dict[str, Any]] = []
    number = next_global

    while number in by_global:
        current = by_global[number]
        if not _same_surah(first, current):
            break
        same_surah_ayahs.append(current)
        number += 1

    full_duration = sum(estimate_ayah_duration(a) for a in same_surah_ayahs)

    if full_duration <= maximum:
        selected = same_surah_ayahs
    else:
        selected = []
        total = 0.0
        for ayah in same_surah_ayahs:
            duration = estimate_ayah_duration(ayah)
            if selected and total + duration > maximum:
                break
            selected.append(ayah)
            total += duration
            if total >= minimum:
                break

    if not selected:
        selected = [first]

    segment = _build_segment(selected, video_type)
    if save_selection:
        set_pending_segment(segment)
    return segment
