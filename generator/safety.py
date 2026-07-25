"""Project safety and required-file checks."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FILES = [
    Path("config.json"),
    Path("data/quran.json"),
    Path("data/progress.json"),
    Path("generator/brain.py"),
    Path("generator/segment_engine.py"),
    Path("generator/progress_engine.py"),
    Path("generator/video_engine.py"),
    Path("generator/audio_engine.py"),
]


def check_required_files() -> list[str]:
    return [str(path) for path in REQUIRED_FILES if not path.is_file()]


def run_safety_check(raise_on_error: bool = False) -> bool:
    errors = check_required_files()
    quran_path = Path("data/quran.json")

    if quran_path.is_file():
        try:
            with quran_path.open("r", encoding="utf-8") as file:
                quran = json.load(file)
            if not isinstance(quran, list) or not quran:
                errors.append("data/quran.json has no ayahs")
        except (OSError, json.JSONDecodeError):
            errors.append("data/quran.json is invalid JSON")

    if errors:
        print("Safety Check Failed")
        for error in errors:
            print("-", error)
        if raise_on_error:
            raise RuntimeError("Safety check failed: " + "; ".join(errors))
        return False

    print("Safety Check Passed")
    return True
