"""
Quran AI Publisher
Ordered Quran Segment Engine
Version 3.2

Rules:
- Quran is processed strictly in Mushaf order.
- Short and long publishing journeys keep independent progress.
- A segment never crosses from one surah into another.
- Short surahs are kept complete when they fit.
- Long surahs are divided into consecutive parts.
- A failed pending part is reused unchanged.
- A completed Quran journey starts a new counted cycle from Al-Fatihah.
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
    start_new_quran_cycle,
)
from generator.quran_dataset import ensure_quran_dataset

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
    data = ensure_quran_dataset()
    if not isinstance(data, list) or not data:
        raise RuntimeError("The Quran dataset contains no ayahs.")
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
    return max(MINIMUM_AYAH_SECONDS, len(str(ayah["text"]).split()) * DEFAULT_SECONDS_PER_WORD)


def get_duration_limits(video_type: str) -> tuple[float, float]:
    publishing = load_config().get("publishing", {})
    if video_type == "short":
        settings = publishing.get("shorts", {})
        return float(settings.get("minimum_duration_seconds", 8)), float(settings.get("maximum_duration_seconds", 60))
    if video_type == "long":
        settings = publishing.get("long_videos", {})
        return float(settings.get("minimum_duration_minutes", 10)) * 60, float(settings.get("maximum_duration_minutes", 25)) * 60
    raise ValueError("video_type must be 'short' or 'long'.")


def build_segment_id(start_global: int, end_global: int, video_type: str, cycle: int = 0) -> str:
    value = f"{cycle}|{start_global}|{end_global}|{video_type}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _same_surah(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if first.get("surah_number") is not None and second.get("surah_number") is not None:
        return first["surah_number"] == second["surah_number"]
    return first["surah"] == second["surah"]


def _surah_ayahs(quran: list[dict[str, Any]], reference: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in quran if _same_surah(reference, item)]


def _partition_surah(ayahs: list[dict[str, Any]], maximum: float) -> list[list[dict[str, Any]]]:
    parts: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_duration = 0.0
    for ayah in ayahs:
        duration = estimate_ayah_duration(ayah)
        if current and current_duration + duration > maximum:
            parts.append(current)
            current = []
            current_duration = 0.0
        current.append(ayah)
        current_duration += duration
    if current:
        parts.append(current)
    return parts


def _part_metadata(quran: list[dict[str, Any]], selected: list[dict[str, Any]], maximum: float) -> dict[str, Any]:
    entire_surah = _surah_ayahs(quran, selected[0])
    parts = _partition_surah(entire_surah, maximum)
    start_global = selected[0]["global_number"]
    part_index = next((i for i, part in enumerate(parts) if part[0]["global_number"] == start_global), 0)
    return {
        "part_number": part_index + 1,
        "total_parts": len(parts),
        "is_complete_surah": len(parts) == 1,
        "has_previous_part": part_index > 0,
        "has_next_part": part_index + 1 < len(parts),
    }


def _build_segment(
    ayahs: list[dict[str, Any]],
    video_type: str,
    quran: list[dict[str, Any]],
    maximum: float,
    cycle: int,
) -> dict[str, Any]:
    first, last = ayahs[0], ayahs[-1]
    duration = sum(estimate_ayah_duration(item) for item in ayahs)
    segment = {
        "segment_id": build_segment_id(first["global_number"], last["global_number"], video_type, cycle),
        "video_type": video_type,
        "quran_cycle": cycle + 1,
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
    segment.update(_part_metadata(quran, ayahs, maximum))
    segment["display_part"] = "السورة كاملة" if segment["is_complete_surah"] else f"الجزء {segment['part_number']} من {segment['total_parts']}"
    return segment


def _restore_pending_segment(pending: dict[str, Any], quran: list[dict[str, Any]]) -> dict[str, Any]:
    start = int(pending["start_global_number"])
    end = int(pending["end_global_number"])
    ayahs = [a for a in quran if start <= a["global_number"] <= end]
    if len(ayahs) != end - start + 1:
        raise RuntimeError("Pending segment cannot be restored.")
    video_type = str(pending.get("video_type", "long"))
    _, maximum = get_duration_limits(video_type)
    cycle = max(0, int(pending.get("quran_cycle", 1)) - 1)
    restored = _build_segment(ayahs, video_type, quran, maximum, cycle)
    if restored["segment_id"] != pending.get("segment_id"):
        raise RuntimeError("Pending segment does not match current Quran data.")
    return restored


def choose_segment(video_type: str = "long", save_selection: bool = True) -> dict[str, Any] | None:
    if video_type not in {"short", "long"}:
        raise RuntimeError("video_type must be short or long.")
    quran = load_quran()
    pending = get_pending_segment(video_type)
    if pending is not None:
        print(f"Reusing pending {video_type} Quran segment:", pending["segment_id"])
        return _restore_pending_segment(pending, quran)

    progress = load_progress(video_type)
    next_global = int(progress["last_completed_global_ayah"]) + 1
    by_global = {item["global_number"]: item for item in quran}
    first = by_global.get(next_global)

    if first is None and next_global > max(by_global):
        progress = start_new_quran_cycle(video_type)
        next_global = 1
        first = by_global.get(1)
        print(f"Started Quran cycle {int(progress['completed_quran_cycles']) + 1} for {video_type}.")

    if first is None:
        raise RuntimeError(
            f"Quran dataset is missing expected global ayah {next_global}; refusing to skip Quran text."
        )

    _, maximum = get_duration_limits(video_type)
    remaining_in_surah: list[dict[str, Any]] = []
    number = next_global
    while number in by_global:
        current = by_global[number]
        if not _same_surah(first, current):
            break
        remaining_in_surah.append(current)
        number += 1

    full_duration = sum(estimate_ayah_duration(a) for a in remaining_in_surah)
    if full_duration <= maximum:
        selected = remaining_in_surah
    else:
        selected = []
        total = 0.0
        for ayah in remaining_in_surah:
            duration = estimate_ayah_duration(ayah)
            if selected and total + duration > maximum:
                break
            selected.append(ayah)
            total += duration

    if not selected:
        selected = [first]
    cycle = int(progress.get("completed_quran_cycles", 0))
    segment = _build_segment(selected, video_type, quran, maximum, cycle)
    if save_selection:
        set_pending_segment(segment, video_type)
    return segment
