"""Cinematic Quran video renderer with elegant mosque-and-nature scenes."""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
FONT_DIR = Path("assets/fonts")
MEMORY_PATH = Path("data/background_memory.json")
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
CHANNEL_NAME = os.getenv("QURAN_CHANNEL_NAME", "التجارة مع الله").strip() or "التجارة مع الله"
VISUAL_ENGINE_VERSION = "cinematic_mosque_5.0"
THEMES = (
    "mosque_sunset",
    "mosque_moonlight",
    "mosque_mountains",
    "mosque_lake",
    "mosque_clouds",
    "mosque_garden",
)


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
    options = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        FONT_DIR / "arabic.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in options:
        if path.is_file():
            return str(path)
    raise RuntimeError("No Arabic font was found.")


def read_memory() -> dict:
    try:
        value = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def choose_theme(segment: dict) -> str:
    recent = set(read_memory().get("recent_backgrounds", [])[-3:])
    choices = [item for item in THEMES if item not in recent] or list(THEMES)
    seed = f"{segment.get('segment_id')}:{segment.get('surah')}:{segment.get('start_ayah')}"
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(choices)
    return choices[index]


def save_theme(theme: str, segment_id: str) -> None:
    data = read_memory()
    recent = [item for item in data.get("recent_backgrounds", []) if item != theme]
    recent.append(theme)
    history = list(data.get("history", []))
    history.append({"background": theme, "segment_id": segment_id})
    data.update(recent_backgrounds=recent[-4:], history=history[-100:])
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def gradient(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    array = np.empty((height, width, 3), dtype=np.uint8)
    for y in range(height):
        amount = y / max(1, height - 1)
        array[y, :, :] = [int(top[i] * (1 - amount) + bottom[i] * amount) for i in range(3)]
    return Image.fromarray(array, "RGB").convert("RGBA")


def soft_glow(image: Image.Image, x: int, y: int, radius: int, color: tuple[int, int, int], alpha: int = 75) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(14, radius // 2))))


def draw_clouds(image: Image.Image, t: float, opacity: int = 52) -> None:
    width, height = image.size
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    for i in range(9):
        shift = (t * (5 + i % 3) + i * width * 0.19) % (width * 1.4) - width * 0.2
        y = height * (0.13 + (i % 4) * 0.09)
        scale = width * (0.08 + (i % 3) * 0.018)
        color = (244, 238, 225, max(12, opacity - i * 3))
        draw.ellipse((shift - scale, y - scale * 0.35, shift + scale, y + scale * 0.35), fill=color)
        draw.ellipse((shift - scale * 0.35, y - scale * 0.58, shift + scale * 0.55, y + scale * 0.32), fill=color)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(8, int(width * 0.008)))))


def draw_stars(image: Image.Image, t: float) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(150):
        x = (i * 149 + 37) % width
        y = (i * 83 + 19) % max(1, int(height * 0.55))
        pulse = 45 + int(45 * (0.5 + 0.5 * math.sin(t * 0.8 + i * 0.37)))
        radius = 1 + (i % 3 == 0)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(248, 235, 198, pulse))


def draw_mountains(image: Image.Image, t: float, warm: bool = False) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    drift = math.sin(t * 0.12) * width * 0.008
    far = (77, 76, 83, 150) if warm else (23, 58, 72, 175)
    near = (43, 42, 49, 220) if warm else (10, 39, 51, 225)
    draw.polygon(
        [(0, height), (0, height * 0.61), (width * 0.18 + drift, height * 0.46),
         (width * 0.34, height * 0.65), (width * 0.56 - drift, height * 0.40),
         (width * 0.74, height * 0.60), (width, height * 0.45), (width, height)],
        fill=far,
    )
    draw.polygon(
        [(0, height), (0, height * 0.76), (width * 0.25 - drift, height * 0.58),
         (width * 0.50, height * 0.80), (width * 0.79 + drift, height * 0.55),
         (width, height * 0.70), (width, height)],
        fill=near,
    )


def draw_water(image: Image.Image, t: float) -> None:
    width, height = image.size
    horizon = int(height * 0.64)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, horizon, width, height), fill=(7, 32, 48, 210))
    for i in range(42):
        y = horizon + i * max(2, int(height * 0.0065))
        wave = math.sin(t * 0.9 + i * 0.52) * width * 0.025
        left = width * 0.22 + wave
        right = width * 0.78 - wave
        alpha = max(4, 54 - i)
        draw.line((left, y, right, y), fill=(236, 216, 163, alpha), width=2)


def draw_garden(image: Image.Image, t: float) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    base_y = int(height * 0.72)
    draw.rectangle((0, base_y, width, height), fill=(10, 44, 38, 230))
    for i in range(90):
        x = (i * 97 + 11) % width
        sway = math.sin(t * 0.8 + i * 0.41) * width * 0.004
        stem_h = height * (0.045 + (i % 5) * 0.006)
        draw.line((x, base_y + height * 0.15, x + sway, base_y + height * 0.15 - stem_h), fill=(63, 102, 67, 150), width=2)
        if i % 7 == 0:
            draw.ellipse((x - 3, base_y + height * 0.15 - stem_h - 3, x + 3, base_y + height * 0.15 - stem_h + 3), fill=(231, 201, 137, 120))


def draw_mosque_silhouette(image: Image.Image, t: float, foreground: bool = True) -> None:
    width, height = image.size
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    base_y = int(height * (0.76 if foreground else 0.70))
    center = width // 2
    body_w = int(width * (0.42 if foreground else 0.34))
    body_h = int(height * (0.17 if foreground else 0.14))
    body_left = center - body_w // 2
    body_right = center + body_w // 2
    color = (8, 20, 28, 242) if foreground else (13, 34, 43, 210)
    draw.rounded_rectangle((body_left, base_y - body_h, body_right, base_y), radius=int(width * 0.015), fill=color)
    dome_w = int(body_w * 0.50)
    dome_h = int(body_h * 1.05)
    draw.pieslice((center - dome_w // 2, base_y - body_h - dome_h * 0.62,
                   center + dome_w // 2, base_y - body_h + dome_h * 0.38), 180, 360, fill=color)
    draw.rectangle((center - dome_w // 2, base_y - body_h - dome_h * 0.12,
                    center + dome_w // 2, base_y - body_h), fill=color)
    minaret_w = int(width * 0.035)
    minaret_h = int(height * 0.31)
    for side in (-1, 1):
        x = center + side * int(body_w * 0.62)
        draw.rectangle((x - minaret_w // 2, base_y - minaret_h, x + minaret_w // 2, base_y), fill=color)
        draw.polygon([(x - minaret_w, base_y - minaret_h), (x, base_y - minaret_h - minaret_w * 1.4),
                      (x + minaret_w, base_y - minaret_h)], fill=color)
        draw.ellipse((x - 2, base_y - minaret_h - minaret_w * 1.72, x + 2, base_y - minaret_h - minaret_w * 1.48), fill=(227, 196, 118, 180))
    window_y = base_y - int(body_h * 0.55)
    for i in range(5):
        x = body_left + int(body_w * (0.14 + i * 0.18))
        draw.rounded_rectangle((x - width * 0.012, window_y - height * 0.025,
                                x + width * 0.012, window_y + height * 0.025),
                               radius=int(width * 0.007), fill=(242, 201, 120, 95))
    shadow = layer.filter(ImageFilter.GaussianBlur(max(2, int(width * 0.002))))
    image.alpha_composite(shadow)
    image.alpha_composite(layer)


def scene(theme: str, width: int, height: int, t: float) -> Image.Image:
    palettes = {
        "mosque_sunset": ((70, 82, 120), (233, 148, 96)),
        "mosque_moonlight": ((18, 55, 87), (3, 19, 35)),
        "mosque_mountains": ((53, 95, 112), (10, 32, 43)),
        "mosque_lake": ((28, 81, 108), (5, 29, 46)),
        "mosque_clouds": ((102, 135, 159), (224, 174, 121)),
        "mosque_garden": ((35, 96, 89), (8, 34, 38)),
    }
    image = gradient(width, height, *palettes[theme])

    if theme in {"mosque_sunset", "mosque_clouds"}:
        soft_glow(image, int(width * 0.74), int(height * 0.22), int(min(width, height) * 0.18), (255, 222, 172), 90)
        draw_clouds(image, t, 56)
    elif theme == "mosque_moonlight":
        draw_stars(image, t)
        soft_glow(image, int(width * 0.76), int(height * 0.17), int(min(width, height) * 0.17), (249, 236, 198), 82)
        draw = ImageDraw.Draw(image, "RGBA")
        radius = int(min(width, height) * 0.055)
        x, y = int(width * 0.76), int(height * 0.17)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(248, 235, 198, 230))
    elif theme == "mosque_lake":
        draw_stars(image, t)
        soft_glow(image, int(width * 0.72), int(height * 0.16), int(min(width, height) * 0.15), (247, 232, 190), 72)
        draw_water(image, t)
    elif theme == "mosque_mountains":
        draw_clouds(image, t, 32)
        draw_mountains(image, t)
    elif theme == "mosque_garden":
        draw_stars(image, t)
        draw_garden(image, t)

    if theme in {"mosque_sunset", "mosque_clouds"}:
        draw_mountains(image, t, warm=True)
    elif theme == "mosque_lake":
        draw_mountains(image, t)

    draw_mosque_silhouette(image, t, foreground=True)

    vignette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette, "RGBA")
    for i in range(9):
        inset_x = int(width * i * 0.018)
        inset_y = int(height * i * 0.014)
        alpha = 8 + i * 7
        draw.rounded_rectangle((inset_x, inset_y, width - inset_x, height - inset_y),
                               radius=int(min(width, height) * 0.04), outline=(0, 0, 0, alpha), width=max(2, int(width * 0.01)))
    image.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(max(8, int(width * 0.007)))))
    return image


def cover_crop(image: Image.Image, width: int, height: int, zoom: float, t: float, duration: float) -> Image.Image:
    target_w = max(width, int(width * zoom))
    target_h = max(height, int(height * zoom))
    resized = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
    extra_x = max(0, target_w - width)
    extra_y = max(0, target_h - height)
    progress = t / max(duration, 0.01)
    offset_x = int(extra_x * (0.5 + 0.16 * math.sin(progress * math.pi * 1.3)))
    offset_y = int(extra_y * (0.46 + 0.10 * math.cos(progress * math.pi)))
    return resized.crop((offset_x, offset_y, offset_x + width, offset_y + height))


def words(text: str) -> list[str]:
    return [item for item in str(text).split() if item.strip()]


def layout_words(items: list[str], font_path: str, max_width: int, max_height: int, max_size: int, min_size: int):
    probe = ImageDraw.Draw(Image.new("RGBA", (32, 32)))
    fallback = None
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(font_path, size)
        spacing = max(8, int(size * 0.20))
        lines = []
        current = []
        current_width = 0.0
        for index, word in enumerate(items):
            advance = float(probe.textlength(word, font=font, direction="rtl", language="ar"))
            if current and current_width + advance + spacing > max_width:
                lines.append(current)
                current = []
                current_width = 0.0
            current.append((index, word, advance))
            current_width += advance if len(current) == 1 else advance + spacing
        if current:
            lines.append(current)
        line_height = int(size * 1.50)
        fallback = (font, spacing, lines, line_height)
        if len(lines) <= 4 and len(lines) * line_height <= max_height:
            return fallback
    if fallback is None:
        raise RuntimeError("Could not build Arabic text layout.")
    return fallback


def active_word(items: list[dict], t: float):
    if not items:
        return None
    starts = [float(item["start"]) for item in items]
    index = bisect.bisect_right(starts, t) - 1
    if index < 0:
        return None
    item = items[min(index, len(items) - 1)]
    return int(item["word_index"]) if float(item["start"]) <= t <= float(item["end"]) else None


def text_renderer(segment: dict, audio: dict, width: int, height: int, font_path: str):
    scale = render_scale()
    portrait = height > width
    title_font = ImageFont.truetype(font_path, max(24, int((43 if portrait else 46) * scale)))
    info_font = ImageFont.truetype(font_path, max(19, int((29 if portrait else 31) * scale)))
    footer_font = ImageFont.truetype(font_path, max(17, int(25 * scale)))
    watermark_font = ImageFont.truetype(font_path, max(16, int(24 * scale)))

    if portrait:
        panel = (int(width * 0.07), int(height * 0.57), int(width * 0.93), int(height * 0.84))
        title_y = int(height * 0.095)
    else:
        panel = (int(width * 0.12), int(height * 0.58), int(width * 0.88), int(height * 0.85))
        title_y = int(height * 0.10)

    panel_width = panel[2] - panel[0]
    panel_height = panel[3] - panel[1]
    layouts = [
        layout_words(words(ayah.get("text", "")), font_path, int(panel_width * 0.84), int(panel_height * 0.58),
                     max(30, int((68 if portrait else 62) * scale)), max(22, int(37 * scale)))
        for ayah in segment["ayahs"]
    ]
    timings: dict[int, list[dict]] = {}
    for item in audio.get("word_timeline", []):
        timings.setdefault(int(item["global_number"]), []).append(item)

    @lru_cache(maxsize=96)
    def render(index: int, highlighted: int | None, reciter: str):
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")

        title = f"سورة {segment['surah']}"
        title_bbox = draw.textbbox((0, 0), title, font=title_font, direction="rtl", language="ar")
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_rect = (width // 2 - title_width // 2 - int(width * 0.055),
                      title_y - title_height // 2 - int(height * 0.012),
                      width // 2 + title_width // 2 + int(width * 0.055),
                      title_y + title_height // 2 + int(height * 0.012))
        draw.rounded_rectangle(title_rect, radius=int(min(width, height) * 0.018),
                               fill=(8, 19, 27, 135), outline=(232, 207, 148, 130), width=max(1, int(2 * scale)))
        draw.text((width // 2, title_y), title, font=title_font, fill=(249, 241, 216, 255),
                  anchor="mm", direction="rtl", language="ar", stroke_width=max(1, int(scale)), stroke_fill=(0, 0, 0, 80))

        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow, "RGBA")
        shadow_draw.rounded_rectangle((panel[0] + 10, panel[1] + 12, panel[2] + 10, panel[3] + 12),
                                      radius=int(min(width, height) * 0.024), fill=(0, 0, 0, 95))
        layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(12, int(width * 0.012)))))
        draw = ImageDraw.Draw(layer, "RGBA")
        draw.rounded_rectangle(panel, radius=int(min(width, height) * 0.025),
                               fill=(6, 15, 22, 150), outline=(235, 216, 172, 115), width=max(1, int(2 * scale)))

        ayah = segment["ayahs"][index]
        badge = f"الآية {ayah['ayah']}"
        badge_y = panel[1] + int(panel_height * 0.12)
        draw.text((width // 2, badge_y), badge, font=info_font, fill=(231, 215, 173, 235),
                  anchor="mm", direction="rtl", language="ar")

        font, spacing, lines, line_height = layouts[index]
        total_height = len(lines) * line_height
        y = panel[1] + int(panel_height * 0.52) - total_height // 2
        for line in lines:
            line_width = sum(item[2] for item in line) + spacing * max(0, len(line) - 1)
            x = width / 2 + line_width / 2
            for word_index, word, advance in line:
                fill = (241, 204, 112, 255) if highlighted == word_index else (249, 247, 239, 255)
                stroke = (40, 27, 6, 150) if highlighted == word_index else (0, 0, 0, 145)
                draw.text((x, y), word, font=font, fill=fill, anchor="ra", direction="rtl", language="ar",
                          stroke_width=max(1, int(1.5 * scale)), stroke_fill=stroke)
                x -= advance + spacing
            y += line_height

        draw.text((width // 2, panel[3] - int(panel_height * 0.10)), reciter, font=footer_font,
                  fill=(230, 232, 227, 220), anchor="mm", direction="rtl", language="ar")
        draw.text((int(width * 0.965), int(height * 0.965)), CHANNEL_NAME, font=watermark_font,
                  fill=(240, 221, 169, 145), anchor="rs", direction="rtl", language="ar",
                  stroke_width=max(1, int(scale)), stroke_fill=(0, 0, 0, 90))
        return layer

    return render, timings


def save_metadata(segment: dict, seo: dict, audio: dict, video: Path, preview: Path, theme: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "title.txt").write_text(str(seo.get("title", "")), encoding="utf-8")
    (OUTPUT_DIR / "description.txt").write_text(str(seo.get("description", "")), encoding="utf-8")
    (OUTPUT_DIR / "tags.json").write_text(json.dumps(seo.get("tags", []), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "segment_id": segment["segment_id"],
        "video_type": segment["video_type"],
        "surah": segment["surah"],
        "start_ayah": segment["start_ayah"],
        "end_ayah": segment["end_ayah"],
        "video_path": str(video),
        "preview_path": str(preview),
        "privacy_status": str(seo.get("privacy_status", "private")),
        "audio_mode": audio.get("audio_mode"),
        "test_mode": bool(audio.get("test_mode")),
        "exact_ayah_sync": bool(audio.get("exact_ayah_sync")),
        "exact_word_sync": bool(audio.get("exact_word_sync")),
        "rights_confirmed": bool(audio.get("rights_confirmed")),
        "reciter": audio.get("reciter", {}),
        "channel_name": CHANNEL_NAME,
        "watermark_enabled": True,
        "background_theme": theme,
        "visual_engine_version": VISUAL_ENGINE_VERSION,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def build_video(segment: dict, seo: dict) -> str:
    for key in ("segment_id", "video_type", "surah", "start_ayah", "end_ayah", "ayahs", "text"):
        if key not in segment:
            raise RuntimeError(f"Video segment is missing: {key}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    width, height = dimensions(segment)
    font_path = find_font()
    package = get_segment_audio_package(segment)
    duration = float(package["duration"])
    timeline = package.get("ayah_timeline", [])
    if duration <= 0 or not timeline:
        raise RuntimeError("Audio timeline is invalid.")

    theme = choose_theme(segment)
    audio = AudioFileClip(str(package["audio_path"]))
    render_text, timings = text_renderer(segment, package, width, height, font_path)
    starts = [float(item["start"]) for item in timeline]
    reciter = str(package.get("reciter", {}).get("name", "")).strip() or "تلاوة القرآن الكريم"

    def frame(t: float):
        generated = scene(theme, width, height, t)
        zoom = 1.018 + 0.025 * (t / max(duration, 0.01))
        image = cover_crop(generated, width, height, zoom, t, duration)
        index = max(0, min(bisect.bisect_right(starts, t) - 1, len(timeline) - 1))
        ayah = segment["ayahs"][index]
        global_number = int(ayah.get("global_number", index + 1))
        image.alpha_composite(render_text(index, active_word(timings.get(global_number, []), t), reciter).copy())
        return np.asarray(image.convert("RGB"), dtype=np.uint8)

    video_path = OUTPUT_DIR / f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR / f"{segment['segment_id']}_preview.png"
    preview_time = min(max(duration * 0.22, 0.10), max(0.10, duration - 0.05))
    Image.fromarray(frame(preview_time)).save(preview_path)

    clip = VideoClip(frame_function=frame, duration=duration).with_audio(audio)
    try:
        clip.write_videofile(
            str(video_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="6500k" if segment.get("video_type") == "short" else "8000k",
            preset=os.getenv("QURAN_FFMPEG_PRESET", "medium"),
            threads=2,
            pixel_format="yuv420p",
            logger="bar",
        )
    finally:
        clip.close()
        audio.close()

    if not video_path.is_file() or video_path.stat().st_size < 10_000:
        raise RuntimeError("Generated video is missing or empty.")

    save_metadata(segment, seo, package, video_path, preview_path, theme)
    save_theme(theme, str(segment["segment_id"]))
    print("Video ready:", video_path, "theme:", theme, "channel:", CHANNEL_NAME)
    return str(video_path)
