"""
Quran AI Publisher
Audio Engine with exact ayah timing
Version 6.0
"""
from __future__ import annotations
import json, os, struct, subprocess, time, wave
from pathlib import Path
from typing import Any
import requests

RECITERS_FILE = Path("data/reciters.json")
AUDIO_FOLDER = Path("output/audio")
TEMP_FOLDER = AUDIO_FOLDER / "temporary"
TIMING_FOLDER = AUDIO_FOLDER / "timings"
TEST_MODE = True
REQUEST_TIMEOUT = 60
MAX_DOWNLOAD_ATTEMPTS = 3
MINIMUM_AUDIO_SIZE = 5000
SAMPLE_RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2


def load_json(path: Path, default: Any) -> Any:
    if not path.exists(): return default
    try:
        with path.open("r", encoding="utf-8") as f: return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not read JSON file: {path}. Error: {e}") from e


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def ensure_audio_folders() -> None:
    for p in (AUDIO_FOLDER, TEMP_FOLDER, TIMING_FOLDER): p.mkdir(parents=True, exist_ok=True)


def estimate_ayah_duration(ayah: dict) -> float:
    return max(2.5, len(str(ayah.get("text", "")).split()) * 0.55)


def create_silent_wav(output_path: Path, duration: float) -> Path:
    duration = max(1.0, float(duration))
    frames = int(SAMPLE_RATE * duration)
    sample = struct.pack("<h", 0)
    with wave.open(str(output_path), "wb") as f:
        f.setnchannels(CHANNELS); f.setsampwidth(SAMPLE_WIDTH); f.setframerate(SAMPLE_RATE)
        f.writeframes(sample * frames)
    return output_path


def create_test_audio_package(segment: dict) -> dict:
    ensure_audio_folders()
    segment_id = str(segment.get("segment_id", "test_segment")).strip() or "test_segment"
    ayahs = segment.get("ayahs", [])
    if not ayahs: raise RuntimeError("Segment does not contain ayahs.")
    timeline, current = [], 0.0
    for ayah in ayahs:
        d = estimate_ayah_duration(ayah)
        timeline.append({"ayah": ayah, "start": round(current,3), "end": round(current+d,3), "duration": round(d,3)})
        current += d
    output = AUDIO_FOLDER / f"{segment_id}_test_silence.wav"
    if not output.exists(): create_silent_wav(output, current)
    package = {"audio_path": str(output), "duration": round(current,3), "ayah_timeline": timeline, "reciter": "test_silence", "test_mode": True}
    save_json(TIMING_FOLDER / f"{segment_id}.json", package)
    return package


def validate_audio_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size >= MINIMUM_AUDIO_SIZE


def check_ffmpeg() -> None:
    for cmd in ("ffmpeg", "ffprobe"):
        try:
            r = subprocess.run([cmd, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError as e: raise RuntimeError(f"{cmd} is not installed.") from e
        if r.returncode != 0: raise RuntimeError(f"{cmd} is not working correctly.")


def get_audio_duration(path: Path) -> float:
    check_ffmpeg()
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(f"Could not read audio duration: {path}")
    d = float(r.stdout.strip())
    if d <= 0: raise RuntimeError(f"Audio duration is not positive: {path}")
    return d


def load_reciter_config() -> dict:
    data = load_json(RECITERS_FILE, {})
    selected = data.get("selected_reciter")
    reciters = data.get("reciters", {})
    if not selected or selected not in reciters: raise RuntimeError("Selected reciter is not configured.")
    reciter = dict(reciters[selected]); reciter["id"] = selected
    if reciter.get("approved") is not True or reciter.get("license_verified") is not True:
        raise RuntimeError("Audio blocked: reciter source is not approved and license-verified.")
    if "{global_number}" not in str(reciter.get("url_template", "")):
        raise RuntimeError("Audio URL template must contain {global_number}.")
    return reciter


def get_global_number(ayah: dict) -> int:
    for key in ("global_number","global_ayah","number"):
        try:
            n = int(ayah.get(key))
            if 1 <= n <= 6236: return n
        except (TypeError, ValueError): pass
    raise RuntimeError("Ayah does not contain a valid global number.")


def download_audio(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".download")
    last = None
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS+1):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={"User-Agent":"Quran-AI-Publisher/6.0"})
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if any(x in ctype for x in ("text/html","application/json","text/plain")):
                raise RuntimeError(f"Invalid audio content type: {ctype}")
            with tmp.open("wb") as f:
                for chunk in r.iter_content(65536):
                    if chunk: f.write(chunk)
            os.replace(tmp, destination)
            if not validate_audio_file(destination): raise RuntimeError("Downloaded audio is invalid.")
            return destination
        except Exception as e:
            last = e; tmp.unlink(missing_ok=True); destination.unlink(missing_ok=True)
            if attempt < MAX_DOWNLOAD_ATTEMPTS: time.sleep(attempt*2)
    raise RuntimeError(f"Failed to download Quran audio. Last error: {last}")


def get_ayah_audio(ayah: dict, reciter: dict) -> Path:
    n = get_global_number(ayah)
    path = AUDIO_FOLDER / "cache" / reciter["id"] / f"{n}.mp3"
    if validate_audio_file(path): return path
    return download_audio(reciter["url_template"].format(global_number=n), path)


def merge_audio_files(paths: list[Path], output: Path, segment_id: str) -> Path:
    check_ffmpeg()
    concat = TEMP_FOLDER / f"{segment_id}_files.txt"
    with concat.open("w", encoding="utf-8") as f:
        for p in paths: f.write(f"file '{p.resolve().as_posix()}'\n")
    temp = output.with_suffix(".temporary.mp3")
    r = subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-vn","-acodec","libmp3lame","-b:a","128k",str(temp)], capture_output=True, text=True)
    concat.unlink(missing_ok=True)
    if r.returncode != 0: raise RuntimeError("Could not merge Quran audio files.")
    os.replace(temp, output)
    return output


def get_real_audio_package(segment: dict) -> dict:
    ensure_audio_folders()
    ayahs = segment.get("ayahs", [])
    segment_id = str(segment.get("segment_id", "")).strip()
    if not segment_id or not ayahs: raise RuntimeError("Segment data is incomplete.")
    reciter = load_reciter_config()
    output = AUDIO_FOLDER / f"{segment_id}.mp3"
    paths, timeline, current = [], [], 0.0
    for ayah in ayahs:
        p = get_ayah_audio(ayah, reciter)
        d = get_audio_duration(p)
        paths.append(p)
        timeline.append({"ayah":ayah,"audio_path":str(p),"start":round(current,3),"end":round(current+d,3),"duration":round(d,3)})
        current += d
    if not validate_audio_file(output): merge_audio_files(paths, output, segment_id)
    merged = get_audio_duration(output)
    if abs(merged-current) > 1.0: raise RuntimeError("Merged audio duration does not match ayah timeline.")
    package = {"audio_path":str(output),"duration":round(merged,3),"ayah_timeline":timeline,"reciter":{"id":reciter["id"],"name":reciter.get("name",reciter["id"])},"test_mode":False}
    save_json(TIMING_FOLDER / f"{segment_id}.json", package)
    return package


def get_segment_audio_package(segment: dict) -> dict:
    return create_test_audio_package(segment) if TEST_MODE else get_real_audio_package(segment)


def get_segment_audio(segment: dict) -> str:
    return str(get_segment_audio_package(segment)["audio_path"])
