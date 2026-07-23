"""
Quran audio engine.

Modes:
- test: silent preview with estimated word timing.
- local: local ayah MP3 files with exact ayah timing.
- qf: Quran Foundation chapter audio with exact ayah and word timing.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

import requests

AUDIO_FOLDER = Path("output/audio")
CACHE_FOLDER = AUDIO_FOLDER / "cache"
TIMING_FOLDER = AUDIO_FOLDER / "timings"
TEMP_FOLDER = AUDIO_FOLDER / "temporary"
LOCAL_AUDIO_FOLDER = Path("assets/audio")

REQUEST_TIMEOUT = 90
MAX_ATTEMPTS = 3
MINIMUM_AUDIO_SIZE = 5000
SAMPLE_RATE = 44100

ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

SURAH_NAMES = [
    "الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام",
    "الأعراف", "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد",
    "إبراهيم", "الحجر", "النحل", "الإسراء", "الكهف", "مريم", "طه",
    "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان", "الشعراء",
    "النمل", "القصص", "العنكبوت", "الروم", "لقمان", "السجدة",
    "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر",
    "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف",
    "محمد", "الفتح", "الحجرات", "ق", "الذاريات", "الطور", "النجم",
    "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر",
    "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق",
    "التحريم", "الملك", "القلم", "الحاقة", "المعارج", "نوح", "الجن",
    "المزمل", "المدثر", "القيامة", "الإنسان", "المرسلات", "النبأ",
    "النازعات", "عبس", "التكوير", "الانفطار", "المطففين", "الانشقاق",
    "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد", "الشمس",
    "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة",
    "الزلزلة", "العاديات", "القارعة", "التكاثر", "العصر", "الهمزة",
    "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون", "النصر", "المسد",
    "الإخلاص", "الفلق", "الناس",
]


def env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_folders() -> None:
    for path in (
        AUDIO_FOLDER,
        CACHE_FOLDER,
        TIMING_FOLDER,
        TEMP_FOLDER,
    ):
        path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def run_command(
    command: list[str],
    error_message: str,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip()[-1000:]
        raise RuntimeError(f"{error_message} {detail}")
    return process


def check_media_tools() -> None:
    for command in ("ffmpeg", "ffprobe"):
        try:
            result = subprocess.run(
                [command, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"{command} is not installed."
            ) from error
        if result.returncode != 0:
            raise RuntimeError(f"{command} is not working.")


def audio_duration(path: Path) -> float:
    check_media_tools()
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        f"Could not inspect audio: {path}.",
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError(
            f"Invalid audio duration: {path}"
        ) from error
    if duration <= 0:
        raise RuntimeError(
            f"Audio duration is not positive: {path}"
        )
    return duration


def valid_audio(path: Path) -> bool:
    return (
        path.is_file()
        and path.stat().st_size >= MINIMUM_AUDIO_SIZE
    )


def words_of(text: str) -> list[str]:
    return [
        word for word in str(text).split()
        if word.strip()
    ]


def word_weight(word: str) -> float:
    clean = ARABIC_DIACRITICS.sub("", word)
    return max(1.0, len(clean) * 0.8)


def estimated_word_timeline(
    ayah: dict,
    start: float,
    end: float,
) -> list[dict]:
    words = words_of(ayah.get("text", ""))
    if not words:
        return []

    duration = max(0.01, end - start)
    weights = [word_weight(word) for word in words]
    total = sum(weights)
    current = start
    result = []

    for index, (word, weight) in enumerate(
        zip(words, weights)
    ):
        word_end = (
            end
            if index == len(words) - 1
            else current + duration * weight / total
        )
        result.append({
            "global_number": int(
                ayah["global_number"]
            ),
            "word_index": index,
            "word": word,
            "start": round(current, 3),
            "end": round(word_end, 3),
            "exact": False,
        })
        current = word_end

    return result


def create_silent_wav(
    path: Path,
    duration: float,
) -> None:
    frame_count = int(
        max(1.0, duration) * SAMPLE_RATE
    )
    silence = struct.pack("<h", 0)

    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(silence * frame_count)


def estimate_ayah_duration(ayah: dict) -> float:
    return max(
        2.5,
        len(words_of(ayah.get("text", ""))) * 0.55,
    )


def test_package(segment: dict) -> dict:
    ensure_folders()
    segment_id = str(segment["segment_id"])
    timeline = []
    word_timeline = []
    current = 0.0

    for ayah in segment["ayahs"]:
        duration = estimate_ayah_duration(ayah)
        end = current + duration
        timeline.append({
            "ayah": ayah,
            "start": current,
            "end": end,
            "duration": duration,
        })
        word_timeline.extend(
            estimated_word_timeline(
                ayah,
                current,
                end,
            )
        )
        current = end

    output = (
        AUDIO_FOLDER
        / f"{segment_id}_preview.wav"
    )
    if not output.is_file():
        create_silent_wav(output, current)

    package = {
        "audio_path": str(output),
        "duration": round(current, 3),
        "ayah_timeline": timeline,
        "word_timeline": word_timeline,
        "audio_mode": "test",
        "test_mode": True,
        "exact_ayah_sync": False,
        "exact_word_sync": False,
        "rights_confirmed": False,
        "reciter": {
            "name": "معاينة صامتة"
        },
    }
    save_json(
        TIMING_FOLDER / f"{segment_id}.json",
        package,
    )
    return package


def merge_audio(
    paths: list[Path],
    output: Path,
    segment_id: str,
) -> Path:
    check_media_tools()
    concat_file = (
        TEMP_FOLDER
        / f"{segment_id}_concat.txt"
    )

    with concat_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        for path in paths:
            safe = (
                path.resolve()
                .as_posix()
                .replace("'", "'\\''")
            )
            file.write(f"file '{safe}'\n")

    temporary = output.with_suffix(
        ".temporary.mp3"
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            "160k",
            str(temporary),
        ],
        "Could not merge ayah audio.",
    )

    concat_file.unlink(missing_ok=True)
    os.replace(temporary, output)
    return output


def local_package(segment: dict) -> dict:
    ensure_folders()
    segment_id = str(segment["segment_id"])
    paths = []
    timeline = []
    word_timeline = []
    current = 0.0

    for ayah in segment["ayahs"]:
        global_number = int(
            ayah["global_number"]
        )
        path = (
            LOCAL_AUDIO_FOLDER
            / f"{global_number}.mp3"
        )

        if not valid_audio(path):
            raise RuntimeError(
                f"Missing local audio: {path}"
            )

        duration = audio_duration(path)
        end = current + duration
        paths.append(path)
        timeline.append({
            "ayah": ayah,
            "start": current,
            "end": end,
            "duration": duration,
        })
        word_timeline.extend(
            estimated_word_timeline(
                ayah,
                current,
                end,
            )
        )
        current = end

    output = (
        AUDIO_FOLDER
        / f"{segment_id}.mp3"
    )
    if not valid_audio(output):
        merge_audio(
            paths,
            output,
            segment_id,
        )

    package = {
        "audio_path": str(output),
        "duration": audio_duration(output),
        "ayah_timeline": timeline,
        "word_timeline": word_timeline,
        "audio_mode": "local",
        "test_mode": False,
        "exact_ayah_sync": True,
        "exact_word_sync": False,
        "rights_confirmed": env_true(
            "AUDIO_RIGHTS_CONFIRMED",
            False,
        ),
        "reciter": {
            "name": os.getenv(
                "LOCAL_RECITER_NAME",
                "قارئ محلي",
            )
        },
    }
    save_json(
        TIMING_FOLDER / f"{segment_id}.json",
        package,
    )
    return package


def resolve_surah_number(
    segment: dict,
) -> int:
    value = segment.get("surah_number")
    if value is not None:
        number = int(value)
        if 1 <= number <= 114:
            return number

    name = (
        str(segment.get("surah", ""))
        .replace("سورة", "")
        .strip()
    )
    try:
        return SURAH_NAMES.index(name) + 1
    except ValueError as error:
        raise RuntimeError(
            f"Could not resolve surah number for: {name}"
        ) from error


def qf_urls() -> tuple[str, str]:
    environment = os.getenv(
        "QF_ENV",
        "production",
    ).strip().lower()

    if environment == "prelive":
        return (
            "https://prelive-oauth2.quran.foundation",
            "https://apis-prelive.quran.foundation",
        )

    return (
        "https://oauth2.quran.foundation",
        "https://apis.quran.foundation",
    )


def qf_access_token() -> tuple[str, str, str]:
    client_id = os.getenv(
        "QF_CLIENT_ID",
        "",
    ).strip()
    client_secret = os.getenv(
        "QF_CLIENT_SECRET",
        "",
    ).strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            "QF_CLIENT_ID and QF_CLIENT_SECRET "
            "are required for qf mode."
        )

    auth_base, api_base = qf_urls()
    response = requests.post(
        f"{auth_base}/oauth2/token",
        auth=(client_id, client_secret),
        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials",
            "scope": "content",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    token = response.json().get(
        "access_token"
    )
    if not token:
        raise RuntimeError(
            "Quran Foundation token response "
            "did not contain access_token."
        )

    return str(token), client_id, api_base


def qf_chapter_audio(
    reciter_id: int,
    chapter: int,
) -> dict:
    token, client_id, api_base = (
        qf_access_token()
    )
    response = requests.get(
        (
            f"{api_base}/content/api/v4/"
            f"chapter_recitations/"
            f"{reciter_id}/{chapter}"
        ),
        params={
            "segments": "true"
        },
        headers={
            "x-auth-token": token,
            "x-client-id": client_id,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    audio_file = response.json().get(
        "audio_file"
    )
    if not isinstance(audio_file, dict):
        raise RuntimeError(
            "Quran Foundation response did not "
            "contain audio_file."
        )
    return audio_file


def download(
    url: str,
    destination: Path,
) -> Path:
    if valid_audio(destination):
        return destination

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary = destination.with_suffix(
        destination.suffix + ".download"
    )
    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:
            with requests.get(
                url,
                stream=True,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                with temporary.open(
                    "wb"
                ) as file:
                    for chunk in response.iter_content(
                        1024 * 128
                    ):
                        if chunk:
                            file.write(chunk)

            os.replace(
                temporary,
                destination,
            )
            if not valid_audio(destination):
                raise RuntimeError(
                    "Downloaded audio is invalid."
                )
            return destination

        except Exception as error:
            last_error = error
            temporary.unlink(
                missing_ok=True
            )
            destination.unlink(
                missing_ok=True
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"Audio download failed: {last_error}"
    )


def trim_audio(
    source: Path,
    output: Path,
    start_ms: int,
    end_ms: int,
) -> Path:
    check_media_tools()
    duration = (
        max(1, end_ms - start_ms)
        / 1000.0
    )
    temporary = output.with_suffix(
        ".temporary.mp3"
    )

    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_ms / 1000.0:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            "160k",
            str(temporary),
        ],
        "Could not trim chapter audio.",
    )

    os.replace(temporary, output)
    return output


def normalize_segment_time(
    raw_ms: int,
    verse_from: int,
    verse_to: int,
) -> int:
    verse_duration = max(
        0,
        verse_to - verse_from,
    )
    if (
        raw_ms < verse_from - 1000
        and raw_ms <= verse_duration + 1000
    ):
        return verse_from + raw_ms
    return raw_ms


def qf_package(segment: dict) -> dict:
    ensure_folders()
    chapter = resolve_surah_number(
        segment
    )
    reciter_id = int(
        os.getenv(
            "QF_CHAPTER_RECITER_ID",
            "7",
        )
    )
    audio_file = qf_chapter_audio(
        reciter_id,
        chapter,
    )

    audio_url = str(
        audio_file.get("audio_url", "")
    ).strip()
    timestamps = audio_file.get(
        "timestamps",
        [],
    )

    if (
        not audio_url
        or not isinstance(timestamps, list)
        or not timestamps
    ):
        raise RuntimeError(
            "Chapter audio does not include "
            "timestamps and segments."
        )

    by_key = {
        str(item.get("verse_key")): item
        for item in timestamps
        if isinstance(item, dict)
    }

    selected = []
    for ayah in segment["ayahs"]:
        key = (
            f"{chapter}:"
            f"{int(ayah['ayah'])}"
        )
        timing = by_key.get(key)
        if timing is None:
            raise RuntimeError(
                f"Missing timing for verse {key}."
            )
        selected.append((ayah, timing))

    segment_start_ms = int(
        selected[0][1]["timestamp_from"]
    )
    segment_end_ms = int(
        selected[-1][1]["timestamp_to"]
    )
    if segment_end_ms <= segment_start_ms:
        raise RuntimeError(
            "Invalid chapter timing range."
        )

    chapter_cache = (
        CACHE_FOLDER
        / "qf"
        / str(reciter_id)
        / f"{chapter}.mp3"
    )
    chapter_audio = download(
        audio_url,
        chapter_cache,
    )

    output = (
        AUDIO_FOLDER
        / f"{segment['segment_id']}.mp3"
    )
    if not valid_audio(output):
        trim_audio(
            chapter_audio,
            output,
            segment_start_ms,
            segment_end_ms,
        )

    ayah_timeline = []
    word_timeline = []
    exact_word_sync = True

    for ayah, timing in selected:
        verse_from = int(
            timing["timestamp_from"]
        )
        verse_to = int(
            timing["timestamp_to"]
        )
        start = (
            verse_from - segment_start_ms
        ) / 1000.0
        end = (
            verse_to - segment_start_ms
        ) / 1000.0

        ayah_timeline.append({
            "ayah": ayah,
            "start": start,
            "end": end,
            "duration": end - start,
        })

        words = words_of(
            ayah.get("text", "")
        )
        segments = (
            timing.get("segments")
            or []
        )
        added = 0

        for part in segments:
            if (
                not isinstance(part, list)
                or len(part) < 3
            ):
                continue

            raw_index = int(part[0])
            raw_start = int(part[1])
            raw_end = int(part[2])
            index = (
                raw_index - 1
                if raw_index >= 1
                else raw_index
            )

            if not (
                0 <= index < len(words)
            ):
                continue

            absolute_start = (
                normalize_segment_time(
                    raw_start,
                    verse_from,
                    verse_to,
                )
            )
            absolute_end = (
                normalize_segment_time(
                    raw_end,
                    verse_from,
                    verse_to,
                )
            )

            word_timeline.append({
                "global_number": int(
                    ayah["global_number"]
                ),
                "word_index": index,
                "word": words[index],
                "start": round(
                    (
                        absolute_start
                        - segment_start_ms
                    ) / 1000.0,
                    3,
                ),
                "end": round(
                    (
                        absolute_end
                        - segment_start_ms
                    ) / 1000.0,
                    3,
                ),
                "exact": True,
            })
            added += 1

        if added == 0:
            exact_word_sync = False
            word_timeline.extend(
                estimated_word_timeline(
                    ayah,
                    start,
                    end,
                )
            )

    package = {
        "audio_path": str(output),
        "duration": audio_duration(output),
        "ayah_timeline": ayah_timeline,
        "word_timeline": sorted(
            word_timeline,
            key=lambda item: (
                item["start"],
                item["word_index"],
            ),
        ),
        "audio_mode": "qf",
        "test_mode": False,
        "exact_ayah_sync": True,
        "exact_word_sync": exact_word_sync,
        "rights_confirmed": env_true(
            "AUDIO_RIGHTS_CONFIRMED",
            False,
        ),
        "reciter": {
            "name": os.getenv(
                "QF_RECITER_NAME",
                f"Reciter {reciter_id}",
            ),
            "id": reciter_id,
        },
    }
    save_json(
        TIMING_FOLDER
        / f"{segment['segment_id']}.json",
        package,
    )
    return package


def get_segment_audio_package(
    segment: dict,
) -> dict:
    mode = os.getenv(
        "QURAN_AUDIO_MODE",
        "test",
    ).strip().lower()

    if mode == "test":
        return test_package(segment)
    if mode == "local":
        return local_package(segment)
    if mode == "qf":
        return qf_package(segment)

    raise RuntimeError(
        "QURAN_AUDIO_MODE must be "
        "test, local, or qf."
    )


def get_segment_audio(
    segment: dict,
) -> str:
    return str(
        get_segment_audio_package(
            segment
        )["audio_path"]
    )
