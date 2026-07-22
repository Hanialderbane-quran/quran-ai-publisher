"""
Quran AI Publisher
Background Memory Engine
Version 1.0
"""

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path


BACKGROUND_DIR = Path("assets/backgrounds")
MEMORY_FILE = Path("data/background_memory.json")

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

RECENT_LIMIT = 30


def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {
            "recent_backgrounds": [],
            "history": []
        }

    try:
        with MEMORY_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):
        return {
            "recent_backgrounds": [],
            "history": []
        }

    if not isinstance(data, dict):
        return {
            "recent_backgrounds": [],
            "history": []
        }

    data.setdefault(
        "recent_backgrounds",
        []
    )

    data.setdefault(
        "history",
        []
    )

    return data


def save_memory(memory: dict) -> None:
    MEMORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = MEMORY_FILE.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            memory,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temporary_file,
        MEMORY_FILE
    )


def get_valid_backgrounds() -> list[Path]:
    if not BACKGROUND_DIR.exists():
        return []

    valid_files = []

    for path in BACKGROUND_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        if path.stat().st_size < 5000:
            print(
                "Blocked small background:",
                path
            )
            continue

        valid_files.append(
            path
        )

    return valid_files


def choose_background() -> Path | None:
    backgrounds = get_valid_backgrounds()

    if not backgrounds:
        print(
            "No background image available. "
            "Using automatic gradient."
        )

        return None

    memory = load_memory()

    recent = set(
        memory.get(
            "recent_backgrounds",
            []
        )
    )

    available = [
        path
        for path in backgrounds
        if path.name not in recent
    ]

    if not available:
        print(
            "All backgrounds were used recently. "
            "Resetting recent background memory."
        )

        memory[
            "recent_backgrounds"
        ] = []

        recent = set()
        available = backgrounds

    selected = random.choice(
        available
    )

    recent_list = memory.get(
        "recent_backgrounds",
        []
    )

    recent_list.append(
        selected.name
    )

    memory[
        "recent_backgrounds"
    ] = recent_list[
        -RECENT_LIMIT:
    ]

    history = memory.get(
        "history",
        []
    )

    history.append(
        {
            "background": selected.name,
            "used_at": datetime.now(
                timezone.utc
            ).isoformat(
                timespec="seconds"
            )
        }
    )

    memory["history"] = history[
        -500:
    ]

    save_memory(
        memory
    )

    print(
        "Selected background:",
        selected
    )

    return selected
