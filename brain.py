"""Quran AI Publisher - Quran Channel Brain - Version 4.0"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from generator.segment_engine import choose_segment
from generator.seo import build_seo

CONFIG_FILE = Path("config.json")


def load_config() -> dict[str, Any]:
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError as error:
        raise RuntimeError("config.json was not found.") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("config.json contains invalid JSON.") from error

    if not isinstance(config, dict):
        raise RuntimeError("config.json must contain a JSON object.")
    return config


def choose_video_type(config: dict[str, Any]) -> str:
    requested = os.getenv("VIDEO_TYPE", "").strip().lower()
    if requested:
        if requested not in {"short", "long"}:
            raise RuntimeError("VIDEO_TYPE must be short or long.")
        return requested

    publishing = config.get("publishing", {})
    if publishing.get("shorts", {}).get("enabled", False) is True:
        return "short"
    if publishing.get("long_videos", {}).get("enabled", False) is True:
        return "long"
    raise RuntimeError("No publishing type is enabled in config.json.")


def add_compatibility_fields(segment: dict[str, Any]) -> dict[str, Any]:
    start = int(segment["start_ayah"])
    end = int(segment["end_ayah"])
    segment["ayah"] = str(start) if start == end else f"{start}–{end}"
    segment["content_type"] = segment["video_type"]
    return segment


def think() -> dict[str, Any] | None:
    print("\n========== QURAN BRAIN ==========")
    config = load_config()
    video_type = choose_video_type(config)
    segment = choose_segment(video_type=video_type, save_selection=True)

    if segment is None:
        print("No new ordered Quran segment is available.")
        return None

    segment = add_compatibility_fields(segment)
    seo = build_seo(segment)

    print("Surah:", segment["surah"])
    print("Ayahs:", segment["ayah"])
    print("Global range:", segment["start_global_number"], "-", segment["end_global_number"])
    print("Video type:", segment["video_type"])
    print("=================================")

    return {
        "verse": segment,
        "segment": segment,
        "seo": seo,
        "video_type": segment["video_type"],
    }
