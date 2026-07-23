"""Approved background selection and memory engine."""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

CATALOG_FILE = Path("data/background_catalog.json")
MEMORY_FILE = Path("data/background_memory.json")
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".webm"
}
RECENT_LIMIT = 30


def _load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _approved_catalog_paths() -> list[Path]:
    catalog = _load_json(CATALOG_FILE, {"backgrounds": []})
    records = catalog.get("backgrounds", []) if isinstance(catalog, dict) else []
    approved: list[Path] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("approved") is not True:
            continue
        if record.get("contains_people") is not False:
            continue

        relative = str(record.get("path", "")).strip()
        if not relative:
            continue

        path = Path(relative)
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if path.stat().st_size < 5000:
            continue
        approved.append(path)

    return approved


def choose_background() -> Path | None:
    backgrounds = _approved_catalog_paths()
    if not backgrounds:
        print("No approved background found. Using procedural background.")
        return None

    memory = _load_json(
        MEMORY_FILE,
        {"recent_backgrounds": [], "history": []},
    )
    recent = set(memory.get("recent_backgrounds", []))
    available = [
        path for path in backgrounds if path.as_posix() not in recent
    ]

    if not available:
        memory["recent_backgrounds"] = []
        available = backgrounds

    selected = random.choice(available)
    recent_list = list(memory.get("recent_backgrounds", []))
    recent_list.append(selected.as_posix())
    memory["recent_backgrounds"] = recent_list[-RECENT_LIMIT:]

    history = list(memory.get("history", []))
    history.append({
        "background": selected.as_posix(),
        "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    memory["history"] = history[-500:]
    _save_json(MEMORY_FILE, memory)

    print("Selected approved background:", selected)
    return selected
