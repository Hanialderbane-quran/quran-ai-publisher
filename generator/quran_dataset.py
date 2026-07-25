"""Download, validate, and cache the complete Quran text dataset."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

QURAN_FILE = Path("data/quran.json")
COMPLETE_QURAN_AYAH_COUNT = 6236
COMPLETE_QURAN_SURAH_COUNT = 114
QURAN_API_URL = "https://api.quran.com/api/v4/quran/verses/uthmani"
REQUEST_TIMEOUT = 120

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


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read {path}: {error}") from error


def atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def normalize_downloaded_verses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_verses = payload.get("verses")
    if not isinstance(raw_verses, list):
        raise RuntimeError("Quran API response does not contain a verses list.")

    result: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_verses, start=1):
        if not isinstance(raw, dict):
            raise RuntimeError("Quran API returned an invalid verse item.")
        verse_key = str(raw.get("verse_key", ""))
        try:
            chapter_text, ayah_text = verse_key.split(":", 1)
            chapter = int(chapter_text)
            ayah = int(ayah_text)
        except (ValueError, AttributeError) as error:
            raise RuntimeError(f"Invalid Quran verse key: {verse_key}") from error
        text = str(raw.get("text_uthmani", "")).strip()
        if not text:
            raise RuntimeError(f"Quran verse {verse_key} has no Uthmani text.")
        if chapter < 1 or chapter > COMPLETE_QURAN_SURAH_COUNT:
            raise RuntimeError(f"Invalid Quran chapter number: {chapter}")
        result.append({
            "number": int(raw.get("id") or index),
            "surah_number": chapter,
            "surah": SURAH_NAMES[chapter - 1],
            "ayah": ayah,
            "text": text,
        })
    return result


def validate_complete_quran(data: Any) -> tuple[bool, str]:
    if not isinstance(data, list):
        return False, "dataset is not a list"
    if len(data) != COMPLETE_QURAN_AYAH_COUNT:
        return False, f"expected {COMPLETE_QURAN_AYAH_COUNT} ayahs, found {len(data)}"

    global_numbers: list[int] = []
    chapters: set[int] = set()
    previous_chapter = 0
    previous_ayah = 0
    for expected_global, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            return False, f"ayah {expected_global} is not an object"
        try:
            global_number = int(item.get("global_number") or item.get("number"))
            chapter = int(item.get("surah_number"))
            ayah = int(item.get("ayah"))
        except (TypeError, ValueError):
            return False, f"ayah {expected_global} has invalid numbering"
        if global_number != expected_global:
            return False, f"global ayah order breaks at {expected_global}"
        if not str(item.get("text", "")).strip():
            return False, f"ayah {expected_global} has empty text"
        if chapter == previous_chapter:
            if ayah != previous_ayah + 1:
                return False, f"surah {chapter} ayah order breaks at {ayah}"
        else:
            if chapter != previous_chapter + 1 or ayah != 1:
                return False, f"surah order breaks at chapter {chapter}"
        global_numbers.append(global_number)
        chapters.add(chapter)
        previous_chapter = chapter
        previous_ayah = ayah

    if len(chapters) != COMPLETE_QURAN_SURAH_COUNT:
        return False, f"expected 114 surahs, found {len(chapters)}"
    if global_numbers[-1] != COMPLETE_QURAN_AYAH_COUNT:
        return False, "final global ayah number is invalid"
    return True, "complete Quran dataset verified"


def download_complete_quran() -> list[dict[str, Any]]:
    headers = {"Accept": "application/json", "User-Agent": "quran-ai-publisher/1.0"}
    response = requests.get(QURAN_API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Quran API returned an invalid JSON response.")
    data = normalize_downloaded_verses(payload)
    valid, reason = validate_complete_quran(data)
    if not valid:
        raise RuntimeError(f"Downloaded Quran dataset failed validation: {reason}")
    atomic_write(QURAN_FILE, data)
    print("Complete Quran dataset downloaded and verified:", len(data), "ayahs.")
    return data


def ensure_quran_dataset() -> list[dict[str, Any]]:
    existing = read_json(QURAN_FILE) if QURAN_FILE.is_file() else []
    valid, reason = validate_complete_quran(existing)
    if valid:
        print("Quran dataset:", reason)
        return existing

    test_mode = os.getenv("QURAN_AUDIO_MODE", "test").strip().lower() == "test"
    allow_sample = env_true("ALLOW_SAMPLE_QURAN_DATASET", test_mode)
    print("Quran dataset is incomplete:", reason)

    try:
        return download_complete_quran()
    except Exception as error:
        if allow_sample and isinstance(existing, list) and existing:
            print("WARNING: Using sample Quran data for render test only:", error)
            return existing
        raise RuntimeError(
            "A verified complete Quran dataset is required before publishing. "
            f"Automatic download failed: {error}"
        ) from error
