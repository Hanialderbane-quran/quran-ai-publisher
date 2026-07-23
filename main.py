"""Quran AI Publisher - main orchestration."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from generator.brain import think
from generator.progress_engine import mark_segment_completed, record_segment_error
from generator.quality_engine import validate, validate_output
from generator.report_engine import create_report
from generator.safety import run_safety_check
from generator.tasks import run_tasks
from generator.uploader import upload_if_enabled
from generator.video_engine import build_video

MANIFEST_FILE = Path("output/manifest.json")


def load_config() -> dict:
    with Path("config.json").open("r", encoding="utf-8") as file:
        return json.load(file)


def env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_manifest() -> dict:
    if not MANIFEST_FILE.is_file():
        raise RuntimeError("Video manifest was not created.")
    with MANIFEST_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise RuntimeError("Video manifest is invalid.")
    return data


def start() -> None:
    print("========== Quran AI Publisher ==========")
    segment_id = None

    try:
        run_tasks()
        run_safety_check(raise_on_error=True)

        config = load_config()
        print("Channel:", config.get("channel_name", "Quran Channel"))
        print("UTC time:", datetime.now(timezone.utc).isoformat())

        result = think()
        if result is None:
            print("Nothing new to render.")
            return

        segment = result["segment"]
        seo = result["seo"]
        segment_id = str(segment["segment_id"])

        if not validate(segment, seo):
            raise RuntimeError("Pre-render quality check failed.")

        create_report(segment, seo, stage="selected")
        video_path = build_video(segment, seo)
        manifest = read_manifest()

        if not validate_output(video_path, manifest):
            raise RuntimeError("Generated video quality check failed.")

        upload_result = upload_if_enabled(
            video_path=video_path,
            seo=seo,
            manifest=manifest,
        )

        upload_enabled = env_true("YOUTUBE_UPLOAD_ENABLED", False)
        advance_after_render = env_true("ADVANCE_AFTER_RENDER", True)

        should_advance = (
            upload_result.get("status") == "uploaded"
            or (not upload_enabled and advance_after_render)
        )

        if should_advance:
            mark_segment_completed(segment_id)
            progress_status = "advanced"
        else:
            progress_status = "kept_pending"

        create_report(
            segment,
            seo,
            stage="completed",
            extra={
                "video_path": video_path,
                "upload": upload_result,
                "progress_status": progress_status,
                "manifest": manifest,
            },
        )

        print("\nVideo ready:", video_path)
        print("Upload:", upload_result.get("status"))
        print("Progress:", progress_status)
        print("Publisher finished successfully.")

    except Exception as error:
        if segment_id:
            record_segment_error(str(error))
        print("Publisher failed:", error)
        raise


if __name__ == "__main__":
    start()
