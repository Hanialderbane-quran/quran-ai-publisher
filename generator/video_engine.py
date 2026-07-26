"""Quran video renderer using real licensed moving background videos."""
from __future__ import annotations

import bisect
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import requests
from moviepy import AudioFileClip, VideoClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
FONT_DIR = Path("assets/fonts")
VIDEO_LIBRARY = Path("data/background_videos.json")
MEMORY_PATH = Path("data/background_memory.json")
CACHE_DIR = OUTPUT_DIR / "background_cache"
CHANNEL_NAME = os.getenv("QURAN_CHANNEL_NAME", "التجارة مع الله").strip() or "التجارة مع الله"
VISUAL_ENGINE_VERSION = "cinematic_mosque_5.0"
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
WIDTH = int(os.getenv("QURAN_VIDEO_WIDTH", "1920"))
HEIGHT = int(os.getenv("QURAN_VIDEO_HEIGHT", "1080"))


def find_font() -> str:
    choices = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for item in choices:
        if item.is_file():
            return str(item)
    raise RuntimeError("No Arabic font was found.")


def load_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_background(segment: dict) -> dict:
    library = load_json(VIDEO_LIBRARY, [])
    if not isinstance(library, list) or not library:
        raise RuntimeError("data/background_videos.json has no background videos.")
    memory = load_json(MEMORY_PATH, {})
    recent = set(memory.get("recent_backgrounds", [])[-2:])
    available = [item for item in library if item.get("id") not in recent] or library
    seed = sum(ord(ch) for ch in f"{segment.get('segment_id')}:{segment.get('surah')}")
    return available[seed % len(available)]


def remember_background(item: dict, segment_id: str) -> None:
    memory = load_json(MEMORY_PATH, {})
    recent = [x for x in memory.get("recent_backgrounds", []) if x != item["id"]]
    recent.append(item["id"])
    history = list(memory.get("history", []))
    history.append({"background": item["id"], "segment_id": segment_id})
    memory.update(recent_backgrounds=recent[-3:], history=history[-100:])
    save_json(MEMORY_PATH, memory)


def download_background(item: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{item['id']}.webm"
    if path.is_file() and path.stat().st_size > 100_000:
        return path
    temp = path.with_suffix(".download")
    with requests.get(str(item["url"]), stream=True, timeout=120, allow_redirects=True) as response:
        response.raise_for_status()
        with temp.open("wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                if chunk:
                    handle.write(chunk)
    if temp.stat().st_size < 100_000:
        temp.unlink(missing_ok=True)
        raise RuntimeError("Downloaded background video is too small.")
    os.replace(temp, path)
    return path


def cover_frame(array: np.ndarray, width: int, height: int, t: float, duration: float) -> Image.Image:
    image = Image.fromarray(array).convert("RGB")
    ratio = max(width / image.width, height / image.height)
    zoom = 1.04 + 0.025 * (0.5 + 0.5 * math.sin((t / max(duration, .1)) * math.pi))
    size = (max(width, int(image.width * ratio * zoom)), max(height, int(image.height * ratio * zoom)))
    image = image.resize(size, Image.Resampling.LANCZOS)
    extra_x, extra_y = image.width - width, image.height - height
    x = int(extra_x * (0.50 + 0.10 * math.sin(t * 0.07)))
    y = int(extra_y * (0.48 + 0.06 * math.cos(t * 0.05)))
    return image.crop((x, y, x + width, y + height)).convert("RGBA")


def words(text: str) -> list[str]:
    return [word for word in str(text).split() if word.strip()]


def build_lines(items: list[str], font_path: str, max_width: int, max_height: int):
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for size in range(76, 35, -2):
        font = ImageFont.truetype(font_path, size)
        spacing = max(10, int(size * .18))
        lines, current, current_width = [], [], 0.0
        for index, word in enumerate(items):
            advance = float(probe.textlength(word, font=font, direction="rtl", language="ar"))
            needed = advance if not current else advance + spacing
            if current and current_width + needed > max_width:
                lines.append(current)
                current, current_width = [], 0.0
            current.append((index, word, advance))
            current_width += advance if len(current) == 1 else advance + spacing
        if current:
            lines.append(current)
        line_height = int(size * 1.50)
        if len(lines) <= 4 and len(lines) * line_height <= max_height:
            return font, spacing, lines, line_height
    raise RuntimeError("Ayah text cannot fit safely in the video frame.")


def active_word(items: list[dict], t: float):
    if not items:
        return None
    starts = [float(item["start"]) for item in items]
    index = bisect.bisect_right(starts, t) - 1
    if index < 0:
        return None
    item = items[min(index, len(items) - 1)]
    return int(item["word_index"]) if float(item["start"]) <= t <= float(item["end"]) else None


def ornamental_overlay(width: int, height: int) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    gold = (224, 190, 103, 235)
    dark = (35, 3, 35, 150)
    draw.rectangle((0, 0, width, height), fill=(16, 0, 25, 70))
    draw.rounded_rectangle((40, 34, width - 40, height - 34), radius=34, outline=gold, width=4)
    draw.arc((width * .16, -height * .24, width * .84, height * .64), 180, 360, fill=gold, width=8)
    draw.line((width * .16, height * .20, width * .16, height * .70), fill=gold, width=5)
    draw.line((width * .84, height * .20, width * .84, height * .70), fill=gold, width=5)
    for x in (.08, .92):
        draw.rounded_rectangle((int(width*x)-38, 100, int(width*x)+38, height-100), radius=22, fill=dark, outline=gold, width=3)
    return layer


def text_renderer(segment: dict, audio: dict, font_path: str):
    panel = (180, 690, WIDTH - 180, HEIGHT - 95)
    panel_width, panel_height = panel[2] - panel[0], panel[3] - panel[1]
    title_font = ImageFont.truetype(font_path, 52)
    badge_font = ImageFont.truetype(font_path, 30)
    footer_font = ImageFont.truetype(font_path, 27)
    watermark_font = ImageFont.truetype(font_path, 24)
    layouts = [build_lines(words(a.get("text", "")), font_path, int(panel_width*.84), int(panel_height*.62)) for a in segment["ayahs"]]
    timings: dict[int, list[dict]] = {}
    for item in audio.get("word_timeline", []):
        timings.setdefault(int(item["global_number"]), []).append(item)

    @lru_cache(maxsize=96)
    def render(index: int, highlighted: int | None, reciter: str):
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        title_rect = (WIDTH//2-235, 62, WIDTH//2+235, 142)
        draw.rounded_rectangle(title_rect, radius=26, fill=(40, 5, 42, 205), outline=(229, 194, 106, 235), width=3)
        draw.text((WIDTH//2, 101), f"سورة {segment['surah']}", font=title_font, fill=(255, 243, 212, 255), anchor="mm", direction="rtl", language="ar")
        draw.rounded_rectangle(panel, radius=34, fill=(24, 3, 28, 205), outline=(229, 194, 106, 230), width=4)
        ayah = segment["ayahs"][index]
        draw.text((WIDTH//2, panel[1]+45), f"الآية {ayah['ayah']}", font=badge_font, fill=(236, 215, 164, 255), anchor="mm", direction="rtl", language="ar")
        font, spacing, lines, line_height = layouts[index]
        y = panel[1] + 90 + (panel_height-150-len(lines)*line_height)//2
        for line in lines:
            line_width = sum(part[2] for part in line) + spacing*max(0, len(line)-1)
            x = WIDTH/2 + line_width/2
            for word_index, word, advance in line:
                selected = highlighted == word_index
                draw.text((x, y), word, font=font, fill=(246, 202, 89, 255) if selected else (255, 250, 237, 255), anchor="ra", direction="rtl", language="ar", stroke_width=2, stroke_fill=(30, 5, 20, 190))
                x -= advance + spacing
            y += line_height
        draw.text((WIDTH//2, panel[3]-35), reciter, font=footer_font, fill=(237, 226, 205, 235), anchor="mm", direction="rtl", language="ar")
        draw.text((WIDTH-62, HEIGHT-42), CHANNEL_NAME, font=watermark_font, fill=(239, 211, 138, 190), anchor="rs", direction="rtl", language="ar")
        return layer
    return render, timings


def save_metadata(segment: dict, seo: dict, audio: dict, video: Path, preview: Path, background: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "title.txt").write_text(str(seo.get("title", "")), encoding="utf-8")
    (OUTPUT_DIR / "description.txt").write_text(str(seo.get("description", "")), encoding="utf-8")
    (OUTPUT_DIR / "tags.json").write_text(json.dumps(seo.get("tags", []), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "segment_id": segment["segment_id"], "video_type": "long", "surah": segment["surah"],
        "start_ayah": segment["start_ayah"], "end_ayah": segment["end_ayah"],
        "video_path": str(video), "preview_path": str(preview), "privacy_status": str(seo.get("privacy_status", "private")),
        "audio_mode": audio.get("audio_mode"), "test_mode": bool(audio.get("test_mode")),
        "exact_ayah_sync": bool(audio.get("exact_ayah_sync")), "exact_word_sync": bool(audio.get("exact_word_sync")),
        "rights_confirmed": bool(audio.get("rights_confirmed")), "reciter": audio.get("reciter", {}),
        "channel_name": CHANNEL_NAME, "watermark_enabled": True, "background_theme": background["id"],
        "background_source": background.get("source"), "background_license": background.get("license"),
        "visual_engine_version": VISUAL_ENGINE_VERSION,
    }
    save_json(OUTPUT_DIR / "manifest.json", manifest)


def build_video(segment: dict, seo: dict) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    package = get_segment_audio_package(segment)
    duration = float(package["duration"])
    timeline = package.get("ayah_timeline", [])
    if duration <= 0 or not timeline:
        raise RuntimeError("Audio timeline is invalid.")

    background = choose_background(segment)
    background_path = download_background(background)
    background_clip = VideoFileClip(str(background_path), audio=False)
    if not background_clip.duration or background_clip.duration <= 0:
        raise RuntimeError("Background video duration is invalid.")
    audio = AudioFileClip(str(package["audio_path"]))
    render_text, timings = text_renderer(segment, package, font_path)
    starts = [float(item["start"]) for item in timeline]
    ornament = ornamental_overlay(WIDTH, HEIGHT)
    reciter = str(package.get("reciter", {}).get("name", "")).strip() or "تلاوة القرآن الكريم"

    def frame(t: float):
        source = background_clip.get_frame(t % background_clip.duration)
        image = cover_frame(source, WIDTH, HEIGHT, t, duration)
        shade = Image.new("RGBA", (WIDTH, HEIGHT), (14, 0, 20, 75))
        image.alpha_composite(shade)
        image.alpha_composite(ornament)
        index = max(0, min(bisect.bisect_right(starts, t) - 1, len(timeline) - 1))
        ayah = segment["ayahs"][index]
        global_number = int(ayah.get("global_number", index + 1))
        image.alpha_composite(render_text(index, active_word(timings.get(global_number, []), t), reciter).copy())
        return np.asarray(image.convert("RGB"), dtype=np.uint8)

    video_path = OUTPUT_DIR / f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR / f"{segment['segment_id']}_preview.png"
    Image.fromarray(frame(min(max(duration*.2, .1), max(.1, duration-.05)))).save(preview_path)
    clip = VideoClip(frame_function=frame, duration=duration).with_audio(audio)
    try:
        clip.write_videofile(str(video_path), fps=FPS, codec="libx264", audio_codec="aac", audio_bitrate="192k", bitrate="8000k", preset=os.getenv("QURAN_FFMPEG_PRESET", "medium"), threads=2, pixel_format="yuv420p", logger="bar")
    finally:
        clip.close(); audio.close(); background_clip.close()
    if not video_path.is_file() or video_path.stat().st_size < 100_000:
        raise RuntimeError("Generated video is missing or empty.")
    save_metadata(segment, seo, package, video_path, preview_path, background)
    remember_background(background, str(segment["segment_id"]))
    print("Video ready:", video_path, "background:", background["id"])
    return str(video_path)
