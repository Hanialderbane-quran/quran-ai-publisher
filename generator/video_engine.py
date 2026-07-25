"""Reliable Quran video renderer for MoviePy 2.x."""
from __future__ import annotations

import bisect
import json
import math
import os
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
ASSET_DIR = Path("assets")
FONT_DIR = ASSET_DIR / "fonts"
BG_DIR = ASSET_DIR / "backgrounds"
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
MINIMUM_VIDEO_SIZE = 10_000


def render_scale() -> float:
    try:
        return max(0.35, min(1.0, float(os.getenv("QURAN_RENDER_SCALE", "1"))))
    except ValueError:
        return 1.0


def dimensions(segment: dict) -> tuple[int, int]:
    base = (1920, 1080) if segment.get("video_type") == "long" else (1080, 1920)
    scale = render_scale()
    return max(320, int(base[0] * scale)), max(320, int(base[1] * scale))


def find_font() -> str:
    candidates = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        FONT_DIR / "arabic.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    raise RuntimeError("No Arabic font was found.")


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    size = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(size, Image.Resampling.LANCZOS)
    left = max(0, (size[0] - width) // 2)
    top = max(0, (size[1] - height) // 2)
    return image.crop((left, top, left + width, top + height))


def background_asset() -> Path | None:
    for name in ("golden_mihrab_scene.png", "quran_clean_sky.png"):
        path = BG_DIR / name
        if path.is_file():
            return path
    return None


class BackgroundSource:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        path = background_asset()
        self.image = Image.open(path).convert("RGB") if path else None

    def frame(self, t: float, duration: float) -> Image.Image:
        if self.image is None:
            return self._procedural(t)
        progress = t / max(duration, 0.01)
        zoom = 1.03 + 0.05 * progress
        w, h = int(self.width * zoom), int(self.height * zoom)
        image = cover(self.image, w, h)
        x = max(0, min(w - self.width, int((w - self.width) * (0.45 + 0.1 * math.sin(progress * math.pi)))))
        y = max(0, min(h - self.height, int((h - self.height) * 0.45)))
        return image.crop((x, y, x + self.width, y + self.height)).convert("RGBA")

    def _procedural(self, t: float) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height))
        pixels = image.load()
        for y in range(self.height):
            v = y / max(1, self.height - 1)
            top = (16, 62, 89)
            bottom = (2, 13, 27)
            pixels_row = tuple(int(top[i] * (1 - v) + bottom[i] * v) for i in range(3))
            for x in range(self.width):
                pixels[x, y] = pixels_row
        layer = image.convert("RGBA")
        draw = ImageDraw.Draw(layer, "RGBA")
        moon_x = int(self.width * 0.78)
        moon_y = int(self.height * 0.20)
        moon_r = max(18, int(min(self.width, self.height) * 0.055))
        draw.ellipse((moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r), fill=(248, 231, 184, 225))
        shift = int(math.sin(t * 0.25) * self.width * 0.02)
        draw.polygon([
            (0, int(self.height * 0.78)),
            (int(self.width * 0.25) + shift, int(self.height * 0.64)),
            (int(self.width * 0.55), int(self.height * 0.80)),
            (int(self.width * 0.82) - shift, int(self.height * 0.66)),
            (self.width, int(self.height * 0.78)),
            (self.width, self.height),
            (0, self.height),
        ], fill=(2, 20, 30, 245))
        return layer


def active_timeline_item(timeline: list[dict], starts: list[float], t: float) -> tuple[int, dict]:
    index = bisect.bisect_right(starts, t) - 1
    index = max(0, min(index, len(timeline) - 1))
    return index, timeline[index]


def active_word_index(words_timing: list[dict], t: float) -> int | None:
    for item in words_timing:
        if float(item["start"]) <= t <= float(item["end"]):
            return int(item["word_index"])
    return None


def wrap_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[list[str]]:
    words = [word for word in text.split() if word]
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        width = draw.textlength(candidate, font=font, direction="rtl", language="ar")
        if current and width > max_width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


def make_text_layer(
    segment: dict,
    ayah_index: int,
    active_word: int | None,
    reciter_name: str,
    width: int,
    height: int,
    font_path: str,
) -> Image.Image:
    scale = render_scale()
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")

    title_font = ImageFont.truetype(font_path, max(24, int(48 * scale)))
    body_font = ImageFont.truetype(font_path, max(28, int((66 if height > width else 54) * scale)))
    info_font = ImageFont.truetype(font_path, max(18, int(30 * scale)))

    header = (int(width * 0.22), int(height * 0.05), int(width * 0.78), int(height * 0.12))
    draw.rounded_rectangle(header, radius=max(16, int(22 * scale)), fill=(5, 22, 36, 220), outline=(220, 188, 100, 255), width=max(2, int(3 * scale)))
    draw.text((width // 2, (header[1] + header[3]) // 2), f"سورة {segment['surah']}", font=title_font, fill=(246, 231, 187, 255), anchor="mm", direction="rtl", language="ar")

    panel = (int(width * 0.07), int(height * 0.63), int(width * 0.93), int(height * 0.90)) if height > width else (int(width * 0.08), int(height * 0.64), int(width * 0.92), int(height * 0.91))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((panel[0] + 10, panel[1] + 10, panel[2] + 10, panel[3] + 10), radius=28, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, shadow)
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.rounded_rectangle(panel, radius=max(20, int(28 * scale)), fill=(3, 16, 28, 218), outline=(220, 188, 100, 255), width=max(2, int(3 * scale)))

    ayah = segment["ayahs"][ayah_index]
    text = str(ayah.get("text", ""))
    lines = wrap_words(draw, text, body_font, int((panel[2] - panel[0]) * 0.84))
    while len(lines) > 5 and body_font.size > max(22, int(34 * scale)):
        body_font = ImageFont.truetype(font_path, body_font.size - 2)
        lines = wrap_words(draw, text, body_font, int((panel[2] - panel[0]) * 0.84))

    line_height = int(body_font.size * 1.55)
    y = panel[1] + int((panel[3] - panel[1]) * 0.20)
    global_word_index = 0
    for line in lines:
        line_text = " ".join(line)
        line_width = draw.textlength(line_text, font=body_font, direction="rtl", language="ar")
        x = width / 2 + line_width / 2
        for word in line:
            word_width = draw.textlength(word, font=body_font, direction="rtl", language="ar")
            fill = (231, 195, 105, 255) if active_word == global_word_index else (245, 244, 235, 255)
            draw.text((x, y), word, font=body_font, fill=fill, anchor="ra", direction="rtl", language="ar", stroke_width=1, stroke_fill=(0, 0, 0, 130))
            x -= word_width + body_font.size * 0.20
            global_word_index += 1
        y += line_height

    ayah_label = f"الآية {ayah['ayah']}"
    footer = reciter_name or "القرآن الكريم"
    draw.text((width // 2, panel[3] - int((panel[3] - panel[1]) * 0.14)), f"{ayah_label}  •  {footer}", font=info_font, fill=(221, 228, 226, 245), anchor="mm", direction="rtl", language="ar")
    return layer


def draw_frame_base(background: Image.Image, width: int, height: int) -> Image.Image:
    frame = background.copy()
    draw = ImageDraw.Draw(frame, "RGBA")
    margin_x = int(width * (0.15 if height > width else 0.25))
    top = int(height * 0.14)
    bottom = int(height * 0.58)
    draw.rounded_rectangle((margin_x, top, width - margin_x, bottom), radius=max(30, int(width * 0.06)), outline=(220, 188, 100, 255), width=max(4, int(width * 0.007)))
    draw.rounded_rectangle((margin_x + 14, top + 14, width - margin_x - 14, bottom - 14), radius=max(24, int(width * 0.05)), outline=(246, 226, 166, 120), width=max(2, int(width * 0.003)))
    return frame


def save_metadata(segment: dict, seo: dict, audio_package: dict, video_path: Path, preview_path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "title.txt").write_text(str(seo.get("title", "")), encoding="utf-8")
    (OUTPUT_DIR / "description.txt").write_text(str(seo.get("description", "")), encoding="utf-8")
    (OUTPUT_DIR / "segment_text.txt").write_text(str(segment.get("text", "")), encoding="utf-8")
    (OUTPUT_DIR / "tags.json").write_text(json.dumps(seo.get("tags", []), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "segment_id": segment["segment_id"],
        "video_type": segment["video_type"],
        "surah": segment["surah"],
        "start_ayah": segment["start_ayah"],
        "end_ayah": segment["end_ayah"],
        "video_path": str(video_path),
        "preview_path": str(preview_path),
        "privacy_status": str(seo.get("privacy_status", "private")),
        "audio_mode": audio_package.get("audio_mode"),
        "test_mode": bool(audio_package.get("test_mode")),
        "exact_ayah_sync": bool(audio_package.get("exact_ayah_sync")),
        "exact_word_sync": bool(audio_package.get("exact_word_sync")),
        "rights_confirmed": bool(audio_package.get("rights_confirmed")),
        "reciter": audio_package.get("reciter", {}),
        "visual_engine_version": "golden_mihrab_2.0",
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def build_video(segment: dict, seo: dict) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    required = ["segment_id", "video_type", "surah", "start_ayah", "end_ayah", "ayahs", "text"]
    for key in required:
        if key not in segment:
            raise RuntimeError(f"Video segment is missing: {key}")

    width, height = dimensions(segment)
    font_path = find_font()
    audio_package = get_segment_audio_package(segment)
    audio_path = str(audio_package["audio_path"])
    duration = float(audio_package["duration"])
    timeline = audio_package.get("ayah_timeline", [])
    if duration <= 0:
        raise RuntimeError("Audio duration is invalid.")
    if not timeline:
        raise RuntimeError("Audio package has no ayah timeline.")

    audio = AudioFileClip(audio_path)
    source = BackgroundSource(width, height)
    timeline_starts = [float(item["start"]) for item in timeline]
    word_timings: dict[int, list[dict]] = {}
    for item in audio_package.get("word_timeline", []):
        word_timings.setdefault(int(item["global_number"]), []).append(item)
    reciter_name = str(audio_package.get("reciter", {}).get("name", "")).strip() or "القرآن الكريم"

    def make_frame(t: float) -> np.ndarray:
        frame = draw_frame_base(source.frame(t, duration), width, height)
        ayah_index, _ = active_timeline_item(timeline, timeline_starts, t)
        ayah = segment["ayahs"][ayah_index]
        global_number = int(ayah.get("global_number", ayah_index + 1))
        active_word = active_word_index(word_timings.get(global_number, []), t)
        frame.alpha_composite(make_text_layer(segment, ayah_index, active_word, reciter_name, width, height, font_path))
        return np.asarray(frame.convert("RGB"), dtype=np.uint8)

    video_path = OUTPUT_DIR / f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR / f"{segment['segment_id']}_preview.png"
    preview_t = min(max(duration * 0.22, 0.10), max(0.10, duration - 0.05))
    Image.fromarray(make_frame(preview_t)).save(preview_path)

    video = VideoClip(frame_function=make_frame, duration=duration).with_audio(audio)
    try:
        video.write_videofile(
            str(video_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="6000k" if segment.get("video_type") == "short" else "7500k",
            preset=os.getenv("QURAN_FFMPEG_PRESET", "medium"),
            threads=2,
            pixel_format="yuv420p",
            logger="bar",
        )
    finally:
        video.close()
        audio.close()

    if not video_path.is_file() or video_path.stat().st_size < MINIMUM_VIDEO_SIZE:
        raise RuntimeError("Generated video is missing or empty.")

    save_metadata(segment, seo, audio_package, video_path, preview_path)
    print("\n========== QURAN VIDEO READY ==========")
    print("Resolution:", f"{width}x{height}")
    print("Surah:", segment["surah"])
    print("Ayahs:", f"{segment['start_ayah']}-{segment['end_ayah']}")
    print("Video:", video_path)
    print("Preview:", preview_path)
    print("=======================================")
    return str(video_path)
