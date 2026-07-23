"""Pre-render and post-render quality checks."""
from __future__ import annotations

import subprocess
from pathlib import Path


def validate(segment: dict, seo: dict) -> bool:
    errors = []
    required_segment = [
        "segment_id", "surah", "start_ayah", "end_ayah",
        "start_global_number", "end_global_number", "ayahs", "text",
        "video_type",
    ]

    for field in required_segment:
        if field not in segment:
            errors.append(f"Missing segment field: {field}")

    ayahs = segment.get("ayahs", [])
    if not isinstance(ayahs, list) or not ayahs:
        errors.append("Segment has no ayahs.")
    else:
        globals_list = [
            int(item.get("global_number", -1)) for item in ayahs
        ]
        expected = list(
            range(globals_list[0], globals_list[0] + len(globals_list))
        )
        if globals_list != expected:
            errors.append("Ayahs are not consecutive.")
        if any(not str(item.get("text", "")).strip() for item in ayahs):
            errors.append("An ayah has empty Quran text.")
        surahs = {str(item.get("surah", "")) for item in ayahs}
        if len(surahs) != 1:
            errors.append("One segment cannot cross between surahs.")

    if not str(seo.get("title", "")).strip():
        errors.append("Missing title.")
    if not str(seo.get("description", "")).strip():
        errors.append("Missing description.")
    if not seo.get("tags"):
        errors.append("Missing tags.")
    if seo.get("privacy_status", "private") != "private":
        errors.append("Initial upload privacy must be private.")

    print("========== PRE-RENDER QUALITY ==========")
    if errors:
        for error in errors:
            print("-", error)
        print("Status: FAILED")
        return False

    print("Status: PASSED")
    return True


def has_stream(video_path: str, stream_type: str) -> bool:
    process = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", f"{stream_type}:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode == 0 and bool(process.stdout.strip())


def validate_output(video_path: str, manifest: dict) -> bool:
    errors = []
    path = Path(video_path)

    if not path.is_file() or path.stat().st_size < 10000:
        errors.append("Video file is missing or too small.")
    else:
        if not has_stream(video_path, "v"):
            errors.append("Video stream is missing.")
        if not has_stream(video_path, "a"):
            errors.append("Audio stream is missing.")

    if manifest.get("privacy_status") != "private":
        errors.append("Manifest privacy is not private.")
    if not manifest.get("segment_id"):
        errors.append("Manifest segment_id is missing.")

    print("========== POST-RENDER QUALITY ==========")
    if errors:
        for error in errors:
            print("-", error)
        print("Status: FAILED")
        return False

    print("Status: PASSED")
    return True
