"""
Quran AI Publisher
Golden Mihrab video engine

This renderer creates a premium Quran layout inspired by TV/live Quran
presentation styles while keeping an original design:
- dark navy Islamic background
- gold mihrab frame in the center
- scenic moving panel inside the mihrab
- surah/ayah plaque at the top
- wide ayah strip at the bottom
- active word highlighted in gold with audio sync when available
"""

from __future__ import annotations

import bisect
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
ASSET_DIR = Path("assets")
BG_DIR = ASSET_DIR / "backgrounds"
FONT_DIR = ASSET_DIR / "fonts"
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
MINIMUM_VIDEO_SIZE = 10000


def render_scale() -> float:
    try:
        return max(0.35, min(1.0, float(os.getenv("QURAN_RENDER_SCALE", "1"))))
    except ValueError:
        return 1.0


def dimensions(segment: dict) -> tuple[int, int]:
    if segment.get("video_type") == "long":
        base = (1920, 1080)
    else:
        base = (1080, 1920)
    scale = render_scale()
    return (max(320, int(base[0] * scale)), max(320, int(base[1] * scale)))


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
    target = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(target, Image.Resampling.LANCZOS)
    left = max(0, (target[0] - width) // 2)
    top = max(0, (target[1] - height) // 2)
    return image.crop((left, top, left + width, top + height))


def scenic_asset() -> Path | None:
    candidates = [
        BG_DIR / "golden_mihrab_scene.png",
        BG_DIR / "quran_clean_sky.png",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def procedural_scene(width: int, height: int, t: float) -> Image.Image:
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        v = y / max(1, height - 1)
        if v < 0.65:
            u = v / 0.65
            a = (39, 106, 131)
            b = (18, 65, 98)
        else:
            u = (v - 0.65) / 0.35
            a = (18, 65, 98)
            b = (8, 31, 50)
        color = tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))
        for x in range(width):
            px[x, y] = color

    draw = ImageDraw.Draw(img, "RGBA")
    moon_x = int(width * 0.78)
    moon_y = int(height * 0.18)
    glow_r = int(min(width, height) * 0.17)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((moon_x - glow_r, moon_y - glow_r, moon_x + glow_r, moon_y + glow_r), fill=(248, 226, 164, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(max(25, glow_r // 2)))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    draw = ImageDraw.Draw(img, "RGBA")
    moon_r = int(min(width, height) * 0.055)
    draw.ellipse((moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r), fill=(248, 231, 184, 225))

    for i in range(120):
        sx = int((i * 137 + 23) % width)
        sy = int((i * 71 + 11) % int(height * 0.45))
        rr = 1 + (i % 3)
        draw.ellipse((sx - rr, sy - rr, sx + rr, sy + rr), fill=(244, 225, 180, 45 + (i % 60)))

    shift = math.sin(t * 0.24) * width * 0.02
    base_y = int(height * 0.79)
    p1 = [
        (0, base_y),
        (int(width * 0.12 + shift * 0.4), int(height * 0.68)),
        (int(width * 0.28 + shift * 0.3), int(height * 0.78)),
        (int(width * 0.48 + shift * 0.2), int(height * 0.60)),
        (int(width * 0.68 + shift * 0.15), int(height * 0.77)),
        (int(width * 0.86 + shift * 0.12), int(height * 0.64)),
        (width, int(height * 0.74)),
        (width, height),
        (0, height),
    ]
    p2 = [
        (0, int(height * 0.87)),
        (int(width * 0.18 - shift * 0.15), int(height * 0.78)),
        (int(width * 0.38 - shift * 0.1), int(height * 0.86)),
        (int(width * 0.57 - shift * 0.07), int(height * 0.73)),
        (int(width * 0.78 - shift * 0.05), int(height * 0.84)),
        (width, int(height * 0.80)),
        (width, height),
        (0, height),
    ]
    draw.polygon(p1, fill=(4, 29, 38, 245))
    draw.polygon(p2, fill=(2, 19, 28, 252))
    draw.rectangle((0, int(height * 0.88), width, height), fill=(3, 20, 30, 232))
    for i in range(35):
        yy = int(height * 0.89) + i * 2
        hw = max(10, int(width * (0.18 - i * 0.003)))
        cx = int(width * 0.76 + math.sin(i * 0.42 + t * 0.35) * width * 0.01)
        draw.line((cx - hw, yy, cx + hw, yy), fill=(228, 199, 128, max(4, 28 - i // 2)), width=2)
    return img.convert("RGBA")


class SceneSource:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.source = None
        path = scenic_asset()
        if path is not None:
            self.source = Image.open(path).convert("RGB")
            self.source = ImageEnhance.Brightness(self.source).enhance(0.92)
            self.source = ImageEnhance.Contrast(self.source).enhance(1.04)
            self.source = ImageEnhance.Color(self.source).enhance(0.92)

    def frame(self, t: float, duration: float) -> Image.Image:
        if self.source is None:
            return procedural_scene(self.width, self.height, t)
        progress = t / max(0.01, duration)
        zoom = 1.03 + progress * 0.05
        target_w = int(self.width * zoom)
        target_h = int(self.height * zoom)
        img = cover(self.source, target_w, target_h)
        available_x = max(0, target_w - self.width)
        available_y = max(0, target_h - self.height)
        ox = int(available_x * (0.5 + 0.10 * math.sin(progress * math.pi)))
        oy = int(available_y * (0.48 + 0.08 * math.cos(progress * math.pi)))
        return img.crop((ox, oy, ox + self.width, oy + self.height)).convert("RGBA")


def make_canvas_bg(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        v = y / max(1, height - 1)
        if v < 0.55:
            u = v / 0.55
            a = (8, 37, 56)
            b = (6, 27, 44)
        else:
            u = (v - 0.55) / 0.45
            a = (6, 27, 44)
            b = (2, 12, 24)
        row = tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))
        for x in range(width):
            px[x, y] = row
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    for i in range(7):
        r = int(min(width, height) * (0.18 + i * 0.06))
        a = max(6, 22 - i * 2)
        cx, cy = width // 2, int(height * 0.32)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(211, 178, 95, a), width=2)
    for ix in range(5):
        for iy in range(7):
            cx = int((ix + 0.5) * width / 5)
            cy = int((iy + 0.8) * height / 7)
            rr = max(7, int(min(width, height) * 0.006))
            draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(205, 173, 95, 10), width=1)
            draw.line((cx - rr * 2, cy, cx + rr * 2, cy), fill=(205, 173, 95, 8), width=1)
            draw.line((cx, cy - rr * 2, cx, cy + rr * 2), fill=(205, 173, 95, 8), width=1)
    return Image.alpha_composite(base, overlay)


def mihrab_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        left = int(width * 0.16)
        right = int(width * 0.84)
        top = int(height * 0.14)
        bottom = int(height * 0.58)
    else:
        left = int(width * 0.23)
        right = int(width * 0.77)
        top = int(height * 0.12)
        bottom = int(height * 0.61)
    return left, top, right, bottom


def text_panel_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        return (int(width * 0.07), int(height * 0.63), int(width * 0.93), int(height * 0.88))
    return (int(width * 0.09), int(height * 0.67), int(width * 0.91), int(height * 0.90))


def header_panel_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        return (int(width * 0.20), int(height * 0.06), int(width * 0.80), int(height * 0.115))
    return (int(width * 0.33), int(height * 0.05), int(width * 0.67), int(height * 0.12))


def words_of(text: str) -> list[str]:
    return [w for w in str(text).split() if w.strip()]


def text_advance(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return float(draw.textlength(text, font=font, direction="rtl", language="ar"))


def build_lines(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont, max_width: int, spacing: int):
    lines = []
    current = []
    current_w = 0.0
    for idx, word in enumerate(words):
        adv = text_advance(draw, word, font)
        need = adv if not current else adv + spacing
        if current and current_w + need > max_width:
            lines.append(current)
            current = []
            current_w = 0.0
        current.append((idx, word, adv))
        current_w += adv if len(current) == 1 else adv + spacing
    if current:
        lines.append(current)
    return lines


def fit_text_layout(words: list[str], font_path: str, max_width: int, max_height: int, max_size: int, min_size: int):
    probe = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(font_path, size)
        spacing = max(8, int(size * 0.20))
        lines = build_lines(draw, words, font, max_width, spacing)
        line_h = int(size * 1.55)
        if len(lines) <= 5 and len(lines) * line_h <= max_height:
            return font, spacing, lines, line_h
    font = ImageFont.truetype(font_path, min_size)
    spacing = max(8, int(min_size * 0.20))
    lines = build_lines(draw, words, font, max_width, spacing)
    return font, spacing, lines, int(min_size * 1.55)


def active_timeline_item(timeline: list[dict], starts: list[float], t: float):
    index = bisect.bisect_right(starts, t) - 1
    index = max(0, min(index, len(timeline) - 1))
    return index, timeline[index]


def active_word_index(words_timing: list[dict], t: float):
    if not words_timing:
        return None
    starts = [float(item["start"]) for item in words_timing]
    idx = bisect.bisect_right(starts, t) - 1
    if idx < 0:
        return None
    idx = min(idx, len(words_timing) - 1)
    item = words_timing[idx]
    if float(item["start"]) <= t <= float(item["end"]):
        return int(item["word_index"])
    return None


def rounded_panel(draw: ImageDraw.ImageDraw, rect, fill, outline, radius, width=2):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)


def ease_out(v: float) -> float:
    v = max(0.0, min(1.0, v))
    return 1.0 - (1.0 - v) ** 3


def draw_mihrab_mask(width: int, height: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    base_h = int(height * 0.77)
    radius = int(width * 0.18)
    draw.rounded_rectangle((0, int(height * 0.18), width, base_h), radius=int(width * 0.05), fill=255)
    draw.pieslice((int(width * 0.18), 0, int(width * 0.82), int(height * 0.52)), start=180, end=360, fill=255)
    draw.rectangle((0, int(height * 0.26), width, base_h), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0))


def draw_mihrab_frame(width: int, height: int, scene: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mask = draw_mihrab_mask(width, height)
    clipped = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    clipped.paste(scene.resize((width, height), Image.Resampling.LANCZOS), (0, 0), mask)
    layer = Image.alpha_composite(layer, clipped)

    draw = ImageDraw.Draw(layer, "RGBA")

    # inner shadow
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((int(width*0.02), int(height*0.22), int(width*0.98), int(height*0.78)), radius=int(width*0.05), outline=(0,0,0,120), width=8)
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    layer = Image.alpha_composite(layer, shadow)

    # outer gold lines
    line1 = (214, 182, 96, 255)
    line2 = (244, 223, 165, 170)
    w1 = max(2, int(width * 0.009))
    w2 = max(1, int(width * 0.004))
    # arch
    draw.arc((int(width*0.18), int(height*0.02), int(width*0.82), int(height*0.56)), start=180, end=360, fill=line1, width=w1)
    draw.arc((int(width*0.205), int(height*0.05), int(width*0.795), int(height*0.53)), start=180, end=360, fill=line2, width=w2)
    # columns/sides
    draw.line((int(width*0.10), int(height*0.27), int(width*0.10), int(height*0.90)), fill=line1, width=w1)
    draw.line((int(width*0.90), int(height*0.27), int(width*0.90), int(height*0.90)), fill=line1, width=w1)
    draw.line((int(width*0.125), int(height*0.29), int(width*0.125), int(height*0.875)), fill=line2, width=w2)
    draw.line((int(width*0.875), int(height*0.29), int(width*0.875), int(height*0.875)), fill=line2, width=w2)
    # base
    draw.rounded_rectangle((int(width*0.08), int(height*0.86), int(width*0.92), int(height*0.96)), radius=int(width*0.04), fill=(6, 19, 29, 150), outline=line1, width=max(2, int(width*0.008)))
    draw.rounded_rectangle((int(width*0.11), int(height*0.885), int(width*0.89), int(height*0.945)), radius=int(width*0.03), outline=line2, width=max(1, int(width*0.003)))
    return layer


def build_text_renderer(segment: dict, audio_package: dict, width: int, height: int, font_path: str):
    text_rect = text_panel_rect(width, height)
    panel_w = text_rect[2] - text_rect[0]
    panel_h = text_rect[3] - text_rect[1]
    scale = render_scale()
    title_font = ImageFont.truetype(font_path, max(22, int(46 * scale)))
    info_font = ImageFont.truetype(font_path, max(18, int(32 * scale)))
    footer_font = ImageFont.truetype(font_path, max(17, int(28 * scale)))

    layouts = []
    for ayah in segment["ayahs"]:
        words = words_of(ayah.get("text", ""))
        font, spacing, lines, line_h = fit_text_layout(
            words=words,
            font_path=font_path,
            max_width=int(panel_w * 0.86),
            max_height=int(panel_h * 0.55),
            max_size=max(28, int(70 * scale)),
            min_size=max(20, int(38 * scale)),
        )
        layouts.append({"words": words, "font": font, "spacing": spacing, "lines": lines, "line_height": line_h})

    word_timings_by_ayah = {}
    for item in audio_package.get("word_timeline", []):
        gnum = int(item["global_number"])
        word_timings_by_ayah.setdefault(gnum, []).append(item)
    for items in word_timings_by_ayah.values():
        items.sort(key=lambda item: float(item["start"]))

    @lru_cache(maxsize=64)
    def render(ayah_index: int, active_word: int | None, reciter_name: str):
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")

        # header plaque
        head = header_panel_rect(width, height)
        rounded_panel(draw, head, (9, 25, 38, 210), (214, 182, 96, 255), max(18, int(min(width, height) * 0.018)), width=max(2, int(3 * scale)))
        title = f"سورة {segment['surah']}"
        draw.text(((head[0] + head[2]) // 2, int((head[1] + head[3]) / 2) - int(title_font.size * 0.10)), title, font=title_font, fill=(246, 230, 185, 255), anchor="mm", direction="rtl", language="ar")

        ayah = segment["ayahs"][ayah_index]
        badge_text = f"الآية {ayah['ayah']}"
        badge_w = int(width * 0.22) if height > width else int(width * 0.15)
        badge_h = int(height * 0.045)
        badge_x = width // 2 - badge_w // 2
        badge_y = head[3] + int(height * 0.012)
        rounded_panel(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), (16, 34, 47, 200), (216, 185, 100, 210), int(badge_h * 0.45), width=max(1, int(2 * scale)))
        draw.text((width // 2, badge_y + badge_h // 2), badge_text, font=info_font, fill=(233, 236, 233, 255), anchor="mm", direction="rtl", language="ar")

        # bottom text panel
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow, "RGBA")
        shadow_rect = (text_rect[0] + 10, text_rect[1] + 10, text_rect[2] + 10, text_rect[3] + 10)
        sd.rounded_rectangle(shadow_rect, radius=max(18, int(min(width, height) * 0.022)), fill=(0, 0, 0, 115))
        shadow = shadow.filter(ImageFilter.GaussianBlur(16))
        layer = Image.alpha_composite(layer, shadow)
        draw = ImageDraw.Draw(layer, "RGBA")
        rounded_panel(draw, text_rect, (4, 18, 29, 196), (214, 182, 96, 255), max(22, int(min(width, height) * 0.025)), width=max(2, int(3 * scale)))
        inner = 12
        draw.rounded_rectangle((text_rect[0] + inner, text_rect[1] + inner, text_rect[2] - inner, text_rect[3] - inner), radius=max(16, int(min(width, height) * 0.018)), outline=(245, 227, 170, 90), width=max(1, int(2 * scale)))

        layout = layouts[ayah_index]
        font = layout["font"]
        lines = layout["lines"]
        spacing = layout["spacing"]
        line_h = layout["line_height"]
        total_h = len(lines) * line_h
        text_center_y = text_rect[1] + int(panel_h * 0.45)
        y = text_center_y - total_h // 2

        for line in lines:
            line_w = sum(item[2] for item in line)
            if len(line) > 1:
                line_w += spacing * (len(line) - 1)
            x = width / 2 + line_w / 2
            for word_index, word, adv in line:
                fill = (242, 241, 232, 255)
                stroke_fill = (0, 0, 0, 120)
                stroke_width = max(1, int(1 * scale))
                if active_word == word_index:
                    fill = (230, 196, 108, 255)
                    stroke_fill = (33, 21, 5, 150)
                    stroke_width = max(1, int(2 * scale))
                    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    gd = ImageDraw.Draw(glow, "RGBA")
                    bbox = gd.textbbox((x, y), word, font=font, anchor="ra", direction="rtl", language="ar")
                    pad = max(4, int(font.size * 0.10))
                    gd.rounded_rectangle((bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad), radius=max(8, int(font.size * 0.10)), fill=(214, 182, 96, 32))
                    glow = glow.filter(ImageFilter.GaussianBlur(max(6, int(font.size * 0.06))))
                    layer.alpha_composite(glow)
                    draw = ImageDraw.Draw(layer, "RGBA")
                draw.text((x, y), word, font=font, fill=fill, anchor="ra", direction="rtl", language="ar", stroke_width=stroke_width, stroke_fill=stroke_fill)
                x -= adv + spacing
            y += line_h

        # footer info row
        foot_y = text_rect[3] - int(panel_h * 0.12)
        reciter_label = reciter_name if reciter_name else "القرآن الكريم"
        draw.text((width // 2, foot_y), reciter_label, font=footer_font, fill=(221, 228, 226, 245), anchor="mm", direction="rtl", language="ar")
        return layer

    return render, word_timings_by_ayah


def save_metadata(segment: dict, seo: dict, audio_package: dict, video_path: Path, preview_path: Path):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "title.txt").write_text(str(seo.get("title", "")), encoding="utf-8")
    (OUTPUT_DIR / "description.txt").write_text(str(seo.get("description", "")), encoding="utf-8")
    (OUTPUT_DIR / "segment_text.txt").write_text(str(segment.get("text", "")), encoding="utf-8")
    with (OUTPUT_DIR / "tags.json").open("w", encoding="utf-8") as fh:
        json.dump(seo.get("tags", []), fh, ensure_ascii=False, indent=2)
    manifest = {
        "segment_id": segment["segment_id"],
        "video_type": segment["video_type"],
        "surah": segment["surah"],
        "start_ayah": segment["start_ayah"],
        "end_ayah": segment["end_ayah"],
        "video_path": str(video_path),
        "preview_path": str(preview_path),
        "audio_mode": audio_package.get("audio_mode"),
        "test_mode": bool(audio_package.get("test_mode")),
        "exact_ayah_sync": bool(audio_package.get("exact_ayah_sync")),
        "exact_word_sync": bool(audio_package.get("exact_word_sync")),
        "rights_confirmed": bool(audio_package.get("rights_confirmed")),
        "reciter": audio_package.get("reciter", {}),
        "visual_engine_version": "golden_mihrab_1.0",
    }
    with (OUTPUT_DIR / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)


def build_video(segment: dict, seo: dict) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for key in ["segment_id", "video_type", "surah", "start_ayah", "end_ayah", "ayahs", "text"]:
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
    scene_w = int((mihrab_rect(width, height)[2] - mihrab_rect(width, height)[0]) * 0.92)
    scene_h = int((mihrab_rect(width, height)[3] - mihrab_rect(width, height)[1]) * 0.88)
    scene_source = SceneSource(scene_w, scene_h)
    render_text, word_timings_by_ayah = build_text_renderer(segment, audio_package, width, height, font_path)
    timeline_starts = [float(item["start"]) for item in timeline]
    base_bg = make_canvas_bg(width, height)
    mrect = mihrab_rect(width, height)
    reciter_name = str(audio_package.get("reciter", {}).get("name", "")).strip() or "القرآن الكريم"

    def make_frame(t: float):
        frame = base_bg.copy()
        scene = scene_source.frame(t, duration)
        mihrab_canvas = Image.new("RGBA", (mrect[2] - mrect[0], mrect[3] - mrect[1]), (0, 0, 0, 0))
        mihrab_inner = draw_mihrab_frame(mrect[2] - mrect[0], mrect[3] - mrect[1], scene)
        mihrab_canvas.alpha_composite(mihrab_inner)
        frame.alpha_composite(mihrab_canvas, (mrect[0], mrect[1]))

        ayah_index, active_item = active_timeline_item(timeline, timeline_starts, t)
        ayah = segment["ayahs"][ayah_index]
        gnum = int(ayah.get("global_number", ayah_index + 1))
        active_word = active_word_index(word_timings_by_ayah.get(gnum, []), t)
        text_layer = render_text(ayah_index, active_word, reciter_name).copy()

        local_t = t - float(active_item["start"])
        appear = ease_out(min(1.0, max(0.0, local_t / 0.18)))
        if appear < 1.0:
            offset = int((1.0 - appear) * height * 0.008)
            moved = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            moved.alpha_composite(text_layer, (0, offset))
            text_layer = moved
        frame.alpha_composite(text_layer)
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

    if (not video_path.is_file()) or video_path.stat().st_size < MINIMUM_VIDEO_SIZE:
        raise RuntimeError("Generated video is missing or empty.")

    save_metadata(segment, seo, audio_package, video_path, preview_path)

    print("\n========== GOLDEN MIHRAB VIDEO READY ==========")
    print("Resolution:", f"{width}x{height}")
    print("Surah:", segment["surah"])
    print("Ayahs:", f"{segment['start_ayah']}-{segment['end_ayah']}")
    print("Video:", video_path)
    print("Preview:", preview_path)
    print("================================================")
    return str(video_path)
