"""Ordered progress tracking for short and long Quran journeys."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")

DEFAULT_PROGRESS: dict[str, Any] = {
    "schema_version": 2,
    "mode": "complete_quran",
    "last_completed_global_ayah": 0,
    "pending_segment": None,
    "completed_quran_cycles": 0,
    "last_completed_at": None,
    "last_cycle_completed_at": None,
    "last_error": None,
}


def normalize_video_type(video_type: str | None = None) -> str:
    value = (video_type or os.getenv("VIDEO_TYPE", "short")).strip().lower()
    if value not in {"short", "long"}:
        raise RuntimeError("video_type must be short or long.")
    return value


def progress_file(video_type: str | None = None) -> Path:
    return DATA_DIR / f"progress_{normalize_video_type(video_type)}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary_path, path)


def load_progress(video_type: str | None = None) -> dict[str, Any]:
    kind = normalize_video_type(video_type)
    path = progress_file(kind)
    if not path.exists():
        progress = deepcopy(DEFAULT_PROGRESS)
        progress["video_type"] = kind
        _atomic_write_json(path, progress)
        return progress

    try:
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read {path}: {error}") from error

    if not isinstance(loaded, dict):
        raise RuntimeError(f"{path} must contain a JSON object.")

    progress = deepcopy(DEFAULT_PROGRESS)
    progress.update(loaded)
    progress["video_type"] = kind
    try:
        progress["last_completed_global_ayah"] = max(
            0, int(progress.get("last_completed_global_ayah", 0))
        )
        progress["completed_quran_cycles"] = max(
            0, int(progress.get("completed_quran_cycles", 0))
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid numeric progress in {path}.") from error
    pending = progress.get("pending_segment")
    if pending is not None and not isinstance(pending, dict):
        raise RuntimeError("pending_segment must be an object or null.")
    return progress


def save_progress(progress: dict[str, Any], video_type: str | None = None) -> None:
    kind = normalize_video_type(video_type or progress.get("video_type"))
    progress["video_type"] = kind
    _atomic_write_json(progress_file(kind), progress)


def get_pending_segment(video_type: str | None = None) -> dict[str, Any] | None:
    pending = load_progress(video_type).get("pending_segment")
    return deepcopy(pending) if isinstance(pending, dict) else None


def set_pending_segment(segment: dict[str, Any], video_type: str | None = None) -> None:
    kind = normalize_video_type(video_type or segment.get("video_type"))
    required = {
        "segment_id", "start_global_number", "end_global_number",
        "surah", "start_ayah", "end_ayah",
    }
    missing = sorted(required.difference(segment))
    if missing:
        raise RuntimeError("Pending segment is missing fields: " + ", ".join(missing))

    progress = load_progress(kind)
    current_pending = progress.get("pending_segment")
    if isinstance(current_pending, dict):
        current_id = str(current_pending.get("segment_id", ""))
        incoming_id = str(segment.get("segment_id", ""))
        if current_id and current_id != incoming_id:
            raise RuntimeError(f"A different {kind} Quran segment is already pending.")

    progress["pending_segment"] = deepcopy(segment)
    progress["last_error"] = None
    save_progress(progress, kind)


def record_segment_error(message: str, video_type: str | None = None) -> None:
    kind = normalize_video_type(video_type)
    progress = load_progress(kind)
    pending = progress.get("pending_segment") or {}
    progress["last_error"] = {
        "message": str(message),
        "recorded_at": utc_now(),
        "segment_id": pending.get("segment_id"),
    }
    save_progress(progress, kind)


def start_new_quran_cycle(video_type: str | None = None) -> dict[str, Any]:
    """Start again from Al-Fatihah after a completed dataset journey."""
    kind = normalize_video_type(video_type)
    progress = load_progress(kind)
    if progress.get("pending_segment") is not None:
        raise RuntimeError(f"Cannot start a new {kind} cycle while a segment is pending.")
    progress["completed_quran_cycles"] = int(progress.get("completed_quran_cycles", 0)) + 1
    progress["last_completed_global_ayah"] = 0
    progress["last_cycle_completed_at"] = utc_now()
    progress["last_error"] = None
    save_progress(progress, kind)
    return progress


def mark_segment_completed(segment_id: str, video_type: str | None = None) -> dict[str, Any]:
    kind = normalize_video_type(video_type)
    progress = load_progress(kind)
    pending = progress.get("pending_segment")
    if not isinstance(pending, dict):
        raise RuntimeError(f"There is no pending {kind} segment to complete.")
    if str(pending.get("segment_id", "")) != str(segment_id):
        raise RuntimeError("The completed segment does not match the pending segment.")

    end_global = int(pending["end_global_number"])
    start_global = int(pending["start_global_number"])
    expected_start = int(progress["last_completed_global_ayah"]) + 1
    if start_global != expected_start:
        raise RuntimeError(
            f"Progress order error for {kind}: expected global ayah {expected_start}, "
            f"but segment starts at {start_global}."
        )

    progress["last_completed_global_ayah"] = end_global
    progress["pending_segment"] = None
    progress["last_completed_at"] = utc_now()
    progress["last_error"] = None
    save_progress(progress, kind)
    return progress
