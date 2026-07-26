"""Pre-render and post-render quality checks."""
from __future__ import annotations

import subprocess
from pathlib import Path

EXPECTED_CHANNEL = "التجارة مع الله"
ALLOWED_ENGINES = {"local_background_library_6.0"}


def validate(segment: dict, seo: dict) -> bool:
    errors = []
    required = [
        "segment_id", "surah", "start_ayah", "end_ayah",
        "start_global_number", "end_global_number", "ayahs", "text", "video_type",
    ]
    for field in required:
        if field not in segment:
            errors.append(f"Missing segment field: {field}")

    ayahs = segment.get("ayahs", [])
    if not isinstance(ayahs, list) or not ayahs:
        errors.append("Segment has no ayahs.")
    else:
        globals_list = [int(item.get("global_number", -1)) for item in ayahs]
        expected = list(range(globals_list[0], globals_list[0] + len(globals_list)))
        if globals_list != expected:
            errors.append("Ayahs are not consecutive.")
        if any(not str(item.get("text", "")).strip() for item in ayahs):
            errors.append("An ayah has empty Quran text.")
        if len({str(item.get("surah", "")) for item in ayahs}) != 1:
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
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", f"{stream_type}:0",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", video_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def validate_output(video_path: str, manifest: dict) -> bool:
    errors = []
    path = Path(video_path)
    preview = Path(str(manifest.get("preview_path", "")))

    if not path.is_file() or path.stat().st_size < 100_000:
        errors.append("Video file is missing or too small.")
    else:
        if not has_stream(video_path, "v"):
            errors.append("Video stream is missing.")
        if not has_stream(video_path, "a"):
            errors.append("Audio stream is missing.")

    if not preview.is_file() or preview.stat().st_size < 1_000:
        errors.append("Preview image is missing or too small.")
    if manifest.get("privacy_status") != "private":
        errors.append("Manifest privacy is not private.")
    if not manifest.get("segment_id"):
        errors.append("Manifest segment_id is missing.")
    if manifest.get("visual_engine_version") not in ALLOWED_ENGINES:
        errors.append("Expected local animated background engine was not used.")
    if manifest.get("channel_name") != EXPECTED_CHANNEL:
        errors.append("Channel identity is missing or incorrect.")
    if manifest.get("watermark_enabled") is not True:
        errors.append("Channel watermark is not enabled.")
    if not str(manifest.get("background_theme", "")).startswith("royal_mosque_"):
        errors.append("Approved local mosque background was not used.")
    if manifest.get("background_source") != "generated-local":
        errors.append("Background source must be generated-local.")
    if manifest.get("audio_mode") != "cdn":
        errors.append("Production audio mode must be cdn.")
    if manifest.get("test_mode") is not False:
        errors.append("Silent test audio is not allowed.")
    if manifest.get("exact_ayah_sync") is not True:
        errors.append("Exact ayah synchronization is required.")
    if not str(manifest.get("reciter", {}).get("name", "")).strip():
        errors.append("Reciter name is missing.")

    print("========== POST-RENDER QUALITY ==========")
    if errors:
        for error in errors:
            print("-", error)
        print("Status: FAILED")
        return False
    print("Status: PASSED")
    return True
