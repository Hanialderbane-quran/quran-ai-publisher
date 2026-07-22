"""
Quran AI Publisher
Progress Engine
Version 1.0

Keeps the Quran journey in order.
A segment becomes pending when selected.
Progress advances only after mark_segment_completed() is called.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRESS_FILE = Path("data/progress.json")

DEFAULT_PROGRESS: dict[str, Any] = {
    "schema_version": 1,
    "mode": "complete_quran",
    "last_completed_global_ayah": 0,
    "pending_segment": None,
    "completed_quran_cycles": 0,
    "last_completed_at": None,
    "last_error": None,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    os.replace(temporary_path, path)


def load_progress() -> dict[str, Any]:
    if not PROGRESS_FILE.exists():
        progress = deepcopy(DEFAULT_PROGRESS)
        _atomic_write_json(PROGRESS_FILE, progress)
        return progress

    try:
        with PROGRESS_FILE.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read {PROGRESS_FILE}: {error}") from error

    if not isinstance(loaded, dict):
        raise RuntimeError("data/progress.json must contain a JSON object.")

    progress = deepcopy(DEFAULT_PROGRESS)
    progress.update(loaded)

    try:
        progress["last_completed_global_ayah"] = int(
            progress.get("last_completed_global_ayah", 0)
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "last_completed_global_ayah must be an integer."
        ) from error

    pending = progress.get("pending_segment")
    if pending is not None and not isinstance(pending, dict):
        raise RuntimeError("pending_segment must be an object or null.")

    return progress


def save_progress(progress: dict[str, Any]) -> None:
    _atomic_write_json(PROGRESS_FILE, progress)


def get_pending_segment() -> dict[str, Any] | None:
    pending = load_progress().get("pending_segment")
    return deepcopy(pending) if isinstance(pending, dict) else None


def set_pending_segment(segment: dict[str, Any]) -> None:
    required = {
        "segment_id",
        "start_global_number",
        "end_global_number",
        "surah",
        "start_ayah",
        "end_ayah",
    }
    missing = sorted(required.difference(segment))
    if missing:
        raise RuntimeError(
            "Pending segment is missing fields: " + ", ".join(missing)
        )

    progress = load_progress()
    current_pending = progress.get("pending_segment")

    if isinstance(current_pending, dict):
        current_id = str(current_pending.get("segment_id", ""))
        incoming_id = str(segment.get("segment_id", ""))
        if current_id and current_id != incoming_id:
            raise RuntimeError(
                "A different Quran segment is already pending."
            )

    progress["pending_segment"] = deepcopy(segment)
    progress["last_error"] = None
    save_progress(progress)


def record_segment_error(message: str) -> None:
    progress = load_progress()
    pending = progress.get("pending_segment") or {}
    progress["last_error"] = {
        "message": str(message),
        "recorded_at": utc_now(),
        "segment_id": pending.get("segment_id"),
    }
    save_progress(progress)


def mark_segment_completed(segment_id: str) -> dict[str, Any]:
    progress = load_progress()
    pending = progress.get("pending_segment")

    if not isinstance(pending, dict):
        raise RuntimeError("There is no pending segment to complete.")

    if str(pending.get("segment_id", "")) != str(segment_id):
        raise RuntimeError(
            "The completed segment does not match the pending segment."
        )

    end_global = int(pending["end_global_number"])
    start_global = int(pending["start_global_number"])
    last_completed = int(progress["last_completed_global_ayah"])
    expected_start = last_completed + 1

    if start_global != expected_start:
        raise RuntimeError(
            f"Progress order error: expected global ayah {expected_start}, "
            f"but segment starts at {start_global}."
        )

    progress["last_completed_global_ayah"] = end_global
    progress["pending_segment"] = None
    progress["last_completed_at"] = utc_now()
    progress["last_error"] = None
    save_progress(progress)
    return progress
