"""
Quran AI Publisher
Broadcast Identity 4.0 video engine.

Creates original Quran videos with:
- multiple procedural cinematic background themes
- deterministic background rotation with reuse memory
- slow respectful camera motion
- Arabic RTL text with active-word highlighting
- channel watermark: التجارة مع الله
- preview and manifest metadata for quality checks
"""
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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
ASSET_DIR = Path("assets")
BG_DIR = ASSET_DIR / "backgrounds"
FONT_DIR = ASSET_DIR / "fonts"
BACKGROUND_MEMORY = Path("data/background_memory.json")

FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
MINIMUM_VIDEO_SIZE = 10_000
CHANNEL_NAME = os.getenv("QURAN_CHANNEL_NAME", "التجارة مع الله").strip() or "التجارة مع الله"
VISUAL_ENGINE_VERSION = "broadcast_identity_4.0"

THEMES = (
    "moonlit_mountains",
    "dawn_clouds",
    "emerald_valley",
    "desert_twilight",
    "ocean_night",
    "islamic_lanterns",
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


def _read_memory() -> dict:
    try:
        data = json.loads(BACKGROUND_MEMORY.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_memory(theme: str, segment_id: str) -> None:
    BACKGROUND_MEMORY.parent.mkdir(parents=True, exist_ok=True)
    data = _read_memory()
    recent = [str(x) for x in data.get("recent_backgrounds", []) if str(x)]
    recent = [x for x in recent if x != theme]
    recent.append(theme)
    recent = recent[-4:]
    history = list(data.get("history", []))
    history.append({"background": theme, "segment_id": segment_id})
    data["recent_backgrounds"] = recent
    data["history"] = history[-100:]
    BACKGROUND_MEMORY.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def choose_theme(segment: dict) -> str:
    memory = _read_memory()
    recent = {str(x) for x in memory.get("recent_backgrounds", [])[-3:]}
    available = [theme for theme in THEMES if theme not in recent] or list(THEMES)
    key = f"{segment.get('segment_id','')}:{segment.get('surah','')}:{segment.get('start_ayah','')}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return available[int(digest[:8], 16) % len(available)]


def _gradient(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        u = y / max(1, height - 1)
        arr[y, :, :] = [int(top[i] * (1 - u) + bottom[i] * u) for i in range(3)]
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _add_stars(img: Image.Image, count: int, alpha: int = 120) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    width, height = img.size
    for i in range(count):
        x = (i * 137 + 29) % width
        y = (i * 79 + 17) % max(1, int(height * 0.58))
        r = 1 + (i % 2)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(245, 231, 191, alpha - (i % 45)))


def _glow_disc(img: Image.Image, x: int, y: int, radius: int, color: tuple[int, int, int]) -> None:
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow, "RGBA")
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, 65))
    glow = glow.filter(ImageFilter.GaussianBlur(max(12, radius // 2)))
    img.alpha_composite(glow)
    draw = ImageDraw.Draw(img, "RGBA")
    core = max(8, radius // 3)
    draw.ellipse((x - core, y - core, x + core, y + core), fill=(*color, 225))


def _cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, fill: tuple[int, int, int, int]) -> None:
    pieces = (
        (-0.30, 0.04, 0.28),
        (-0.08, -0.08, 0.38),
        (0.20, 0.00, 0.31),
        (0.40, 0.08, 0.22),
    )
    for ox, oy, rr in pieces:
        r = scale * rr
        x = cx + scale * ox
        y = cy + scale * oy
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def procedural_scene(theme: str, width: int, height: int, t: float) -> Image.Image:
    phase = t * 0.20
    if theme == "dawn_clouds":
        img = _gradient(width, height, (91, 128, 161), (239, 170, 112))
        _glow_disc(img, int(width * 0.76), int(height * 0.24), int(min(width, height) * 0.18), (255, 222, 165))
        draw = ImageDraw.Draw(img, "RGBA")
        for i in range(7):
            cx = ((i * width * 0.23) + math.sin(phase + i) * width * 0.03) % (width * 1.25) - width * 0.1
            cy = height * (0.18 + (i % 4) * 0.10)
            _cloud(draw, cx, cy, width * 0.22, (249, 241, 224, 58))
        draw.polygon([(0, height), (0, height * .73), (width*.22, height*.62), (width*.43, height*.78),
                      (width*.66, height*.59), (width, height*.71), (width, height)], fill=(40, 62, 64, 230))
        draw.polygon([(0, height), (0, height*.84), (width*.3, height*.73), (width*.57, height*.86),
                      (width*.82, height*.70), (width, height*.82), (width, height)], fill=(16, 39, 43, 245))
        return img

    if theme == "emerald_valley":
        img = _gradient(width, height, (21, 91, 94), (7, 31, 41))
        _add_stars(img, 80, 75)
        draw = ImageDraw.Draw(img, "RGBA")
        shift = math.sin(phase) * width * 0.025
        draw.polygon([(0, height), (0, height*.68), (width*.22+shift, height*.50), (width*.43, height*.75),
                      (width*.67-shift, height*.46), (width, height*.72), (width, height)], fill=(9, 54, 49, 230))
        draw.polygon([(0, height), (0, height*.82), (width*.28-shift, height*.67), (width*.55, height*.84),
                      (width*.79+shift, height*.65), (width, height*.79), (width, height)], fill=(4, 30, 32, 250))
        river = [(width*.48, height), (width*.54, height*.80), (width*.51, height*.66), (width*.56, height*.55)]
        draw.line(river, fill=(149, 210, 201, 105), width=max(3, int(width*.018)))
        return img

    if theme == "desert_twilight":
        img = _gradient(width, height, (72, 48, 91), (205, 116, 74))
        _glow_disc(img, int(width * 0.25), int(height * 0.24), int(min(width, height) * 0.14), (255, 218, 166))
        draw = ImageDraw.Draw(img, "RGBA")
        shift = math.sin(phase) * width * .025
        draw.polygon([(0, height), (0, height*.73), (width*.28+shift, height*.64), (width*.58, height*.76),
                      (width, height*.60), (width, height)], fill=(116, 65, 54, 225))
        draw.polygon([(0, height), (0, height*.83), (width*.35-shift, height*.71), (width*.72, height*.88),
                      (width, height*.72), (width, height)], fill=(55, 39, 42, 246))
        return img

    if theme == "ocean_night":
        img = _gradient(width, height, (13, 57, 93), (2, 18, 35))
        _add_stars(img, 120, 120)
        _glow_disc(img, int(width * 0.76), int(height * 0.18), int(min(width, height) * .15), (247, 229, 181))
        draw = ImageDraw.Draw(img, "RGBA")
        horizon = int(height * .67)
        draw.rectangle((0, horizon, width, height), fill=(3, 30, 48, 235))
        for i in range(30):
            y = horizon + i * max(2, int(height * .009))
            wobble = math.sin(phase * 1.8 + i * .55) * width * .018
            draw.line((width*.20+wobble, y, width*.82-wobble, y), fill=(225, 208, 151, max(5, 45-i)), width=2)
        return img

    if theme == "islamic_lanterns":
        img = _gradient(width, height, (20, 48, 70), (4, 15, 28))
        _add_stars(img, 90, 80)
        draw = ImageDraw.Draw(img, "RGBA")
        for i, x_ratio in enumerate((.18, .50, .82)):
            sway = math.sin(phase + i * 1.7) * width * .012
            x = width * x_ratio + sway
            top = height * (.04 + .025 * (i % 2))
            bottom = height * (.33 + .05 * (i % 2))
            draw.line((x, 0, x, top), fill=(210, 179, 102, 120), width=max(1, int(width*.003)))
            r = width * .055
            draw.rounded_rectangle((x-r, top, x+r, bottom), radius=int(r*.35), fill=(13, 32, 43, 210),
                                   outline=(222, 190, 111, 190), width=max(2, int(width*.004)))
            glow = Image.new("RGBA", img.size, (0,0,0,0))
            gd = ImageDraw.Draw(glow, "RGBA")
            gd.ellipse((x-r*1.8, top-r*.2, x+r*1.8, bottom+r*.4), fill=(245, 195, 98, 42))
            img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(8, int(r)))))
        draw.polygon([(0,height),(0,height*.76),(width*.25,height*.66),(width*.52,height*.82),
                      (width*.78,height*.64),(width,height*.76),(width,height)], fill=(3,19,29,245))
        return img

    img = _gradient(width, height, (25, 84, 112), (3, 20, 35))
    _add_stars(img, 130, 125)
    _glow_disc(img, int(width * .78), int(height * .17), int(min(width, height) * .16), (248, 232, 188))
    draw = ImageDraw.Draw(img, "RGBA")
    shift = math.sin(phase) * width * .02
    draw.polygon([(0,height),(0,height*.74),(width*.18+shift,height*.57),(width*.36,height*.75),
                  (width*.58-shift,height*.50),(width*.78,height*.72),(width,height*.59),(width,height)],
                 fill=(5,39,47,238))
    draw.polygon([(0,height),(0,height*.86),(width*.24-shift,height*.72),(width*.50,height*.86),
                  (width*.73+shift,height*.70),(width,height*.82),(width,height)], fill=(2,22,31,250))
    return img


def make_canvas_bg(width: int, height: int) -> Image.Image:
    base = _gradient(width, height, (8, 35, 51), (2, 11, 23))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    for ix in range(6):
        for iy in range(8):
            cx = int((ix + .5) * width / 6)
            cy = int((iy + .6) * height / 8)
            rr = max(7, int(min(width, height) * .006))
            draw.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), outline=(205,173,95,10), width=1)
            draw.line((cx-rr*2, cy, cx+rr*2, cy), fill=(205,173,95,7), width=1)
            draw.line((cx, cy-rr*2, cx, cy+rr*2), fill=(205,173,95,7), width=1)
    return Image.alpha_composite(base, overlay)


def mihrab_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        return int(width*.12), int(height*.13), int(width*.88), int(height*.59)
    return int(width*.18), int(height*.10), int(width*.82), int(height*.64)


def text_panel_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        return int(width*.055), int(height*.63), int(width*.945), int(height*.90)
    return int(width*.075), int(height*.68), int(width*.925), int(height*.91)


def header_panel_rect(width: int, height: int) -> tuple[int, int, int, int]:
    if height > width:
        return int(width*.18), int(height*.047), int(width*.82), int(height*.105)
    return int(width*.33), int(height*.035), int(width*.67), int(height*.105)


def words_of(text: str) -> list[str]:
    return [word for word in str(text).split() if word.strip()]


def text_advance(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return float(draw.textlength(text, font=font, direction="rtl", language="ar"))


def build_lines(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont, max_width: int, spacing: int):
    lines, current, current_w = [], [], 0.0
    for idx, word in enumerate(words):
        adv = text_advance(draw, word, font)
        need = adv if not current else adv + spacing
        if current and current_w + need > max_width:
            lines.append(current)
            current, current_w = [], [], 0.0
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
        spacing = max(8, int(size*.20))
        lines = build_lines(draw, words, font, max_width, spacing)
        line_h = int(size*1.55)
        if len(lines) <= 5 and len(lines)*line_h <= max_height:
            return font, spacing, lines, line_h
    font = ImageFont.truetype(font_path, min_size)
    spacing = max(8, int(min_size*.20))
    lines = build_lines(draw, words, font, max_width, spacing)
    return font, spacing, lines, int(min_size*1.55)


def active_timeline_item(timeline: list[dict], starts: list[float], t: float):
    index = max(0, min(bisect.bisect_right(starts, t)-1, len(timeline)-1))
    return index, timeline[index]


def active_word_index(words_timing: list[dict], t: float):
    if not words_timing:
        return None
    starts = [float(item["start"]) for item in words_timing]
    idx = bisect.bisect_right(starts, t)-1
    if idx < 0:
        return None
    idx = min(idx, len(words_timing)-1)
    item = words_timing[idx]
    return int(item["word_index"]) if float(item["start"]) <= t <= float(item["end"]) else None


def rounded_panel(draw: ImageDraw.ImageDraw, rect, fill, outline, radius, width=2):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)


def draw_mihrab_mask(width: int, height: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, int(height*.22), width, int(height*.96)),
                           radius=int(width*.055), fill=255)
    draw.pieslice((int(width*.13), 0, int(width*.87), int(height*.57)),
                  start=180, end=360, fill=255)
    draw.rectangle((0, int(height*.30), width, int(height*.96)), fill=255)
    return mask


def draw_mihrab_frame(width: int, height: int, scene: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (0,0,0,0))
    mask = draw_mihrab_mask(width, height)
    clipped = Image.new("RGBA", (width, height), (0,0,0,0))
    clipped.paste(scene.resize((width, height), Image.Resampling.LANCZOS), (0,0), mask)
    layer = Image.alpha_composite(layer, clipped)
    draw = ImageDraw.Draw(layer, "RGBA")
    gold, pale = (214,182,96,255), (246,226,169,165)
    w1, w2 = max(2, int(width*.009)), max(1, int(width*.004))
    draw.arc((int(width*.13), int(height*.015), int(width*.87), int(height*.59)),
             start=180, end=360, fill=gold, width=w1)
    draw.arc((int(width*.16), int(height*.045), int(width*.84), int(height*.56)),
             start=180, end=360, fill=pale, width=w2)
    for x in (.075, .925):
        draw.line((int(width*x), int(height*.31), int(width*x), int(height*.92)), fill=gold, width=w1)
    for x in (.105, .895):
        draw.line((int(width*x), int(height*.33), int(width*x), int(height*.90)), fill=pale, width=w2)
    draw.rounded_rectangle((int(width*.055), int(height*.88), int(width*.945), int(height*.975)),
                           radius=int(width*.035), fill=(5,18,29,175), outline=gold, width=w1)
    return layer


def build_text_renderer(segment: dict, audio_package: dict, width: int, height: int, font_path: str):
    text_rect = text_panel_rect(width, height)
    panel_w, panel_h = text_rect[2]-text_rect[0], text_rect[3]-text_rect[1]
    scale = render_scale()
    title_font = ImageFont.truetype(font_path, max(22, int(46*scale)))
    info_font = ImageFont.truetype(font_path, max(18, int(32*scale)))
    footer_font = ImageFont.truetype(font_path, max(17, int(27*scale)))
    watermark_font = ImageFont.truetype(font_path, max(16, int(25*scale)))

    layouts = []
    for ayah in segment["ayahs"]:
        words = words_of(ayah.get("text", ""))
        font, spacing, lines, line_h = fit_text_layout(
            words, font_path, int(panel_w*.86), int(panel_h*.56),
            max(28, int(70*scale)), max(20, int(38*scale)),
        )
        layouts.append({"font": font, "spacing": spacing, "lines": lines, "line_height": line_h})

    timings_by_ayah: dict[int, list[dict]] = {}
    for item in audio_package.get("word_timeline", []):
        timings_by_ayah.setdefault(int(item["global_number"]), []).append(item)
    for items in timings_by_ayah.values():
        items.sort(key=lambda item: float(item["start"]))

    @lru_cache(maxsize=96)
    def render(ayah_index: int, active_word: int | None, reciter_name: str):
        layer = Image.new("RGBA", (width, height), (0,0,0,0))
        draw = ImageDraw.Draw(layer, "RGBA")
        head = header_panel_rect(width, height)
        rounded_panel(draw, head, (7,23,36,218), (214,182,96,255),
                      max(18, int(min(width,height)*.018)), max(2,int(3*scale)))
        title = f"سورة {segment['surah']}"
        draw.text(((head[0]+head[2])//2, (head[1]+head[3])//2),
                  title, font=title_font, fill=(247,231,188,255),
                  anchor="mm", direction="rtl", language="ar")

        ayah = segment["ayahs"][ayah_index]
        badge_text = f"الآية {ayah['ayah']}"
        badge_w = int(width*.22) if height > width else int(width*.14)
        badge_h = int(height*.043)
        badge_x = width//2 - badge_w//2
        badge_y = head[3] + int(height*.012)
        rounded_panel(draw, (badge_x,badge_y,badge_x+badge_w,badge_y+badge_h),
                      (14,34,48,205), (216,185,100,220), int(badge_h*.45),
                      max(1,int(2*scale)))
        draw.text((width//2,badge_y+badge_h//2), badge_text, font=info_font,
                  fill=(235,238,235,255), anchor="mm", direction="rtl", language="ar")

        shadow = Image.new("RGBA", (width,height), (0,0,0,0))
        sd = ImageDraw.Draw(shadow, "RGBA")
        sd.rounded_rectangle((text_rect[0]+10,text_rect[1]+10,text_rect[2]+10,text_rect[3]+10),
                             radius=max(18,int(min(width,height)*.022)), fill=(0,0,0,120))
        layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(16)))
        draw = ImageDraw.Draw(layer, "RGBA")
        rounded_panel(draw, text_rect, (3,17,28,205), (214,182,96,255),
                      max(22,int(min(width,height)*.025)), max(2,int(3*scale)))
        inner = 12
        draw.rounded_rectangle((text_rect[0]+inner,text_rect[1]+inner,text_rect[2]-inner,text_rect[3]-inner),
                               radius=max(16,int(min(width,height)*.018)),
                               outline=(245,227,170,90), width=max(1,int(2*scale)))

        layout = layouts[ayah_index]
        font, lines, spacing, line_h = layout["font"], layout["lines"], layout["spacing"], layout["line_height"]
        y = text_rect[1] + int(panel_h*.44) - len(lines)*line_h//2
        for line in lines:
            line_w = sum(item[2] for item in line) + spacing*max(0,len(line)-1)
            x = width/2 + line_w/2
            for word_index, word, adv in line:
                fill, stroke_fill, stroke_width = (243,242,234,255), (0,0,0,135), max(1,int(scale))
                if active_word == word_index:
                    fill, stroke_fill, stroke_width = (232,199,109,255), (34,22,6,160), max(1,int(2*scale))
                draw.text((x,y), word, font=font, fill=fill, anchor="ra",
                          direction="rtl", language="ar", stroke_width=stroke_width,
                          stroke_fill=stroke_fill)
                x -= adv + spacing
            y += line_h

        reciter_label = reciter_name or "تلاوة القرآن الكريم"
        foot_y = text_rect[3] - int(panel_h*.12)
        draw.text((width//2,foot_y), reciter_label, font=footer_font,
                  fill=(221,228,226,245), anchor="mm", direction="rtl", language="ar")

        wm_x = int(width*.965)
        wm_y = int(height*.965)
        draw.text((wm_x,wm_y), CHANNEL_NAME, font=watermark_font,
                  fill=(236,218,165,155), anchor="rs", direction="rtl", language="ar",
                  stroke_width=max(1,int(scale)), stroke_fill=(0,0,0,85))
        return layer

    return render, timings_by_ayah


def save_metadata(segment: dict, seo: dict, audio_package: dict, video_path: Path, preview_path: Path, theme: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR/"title.txt").write_text(str(seo.get("title","")), encoding="utf-8")
    (OUTPUT_DIR/"description.txt").write_text(str(seo.get("description","")), encoding="utf-8")
    (OUTPUT_DIR/"segment_text.txt").write_text(str(segment.get("text","")), encoding="utf-8")
    (OUTPUT_DIR/"tags.json").write_text(
        json.dumps(seo.get("tags",[]), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "segment_id": segment["segment_id"],
        "video_type": segment["video_type"],
        "surah": segment["surah"],
        "start_ayah": segment["start_ayah"],
        "end_ayah": segment["end_ayah"],
        "video_path": str(video_path),
        "preview_path": str(preview_path),
        "privacy_status": str(seo.get("privacy_status","private")),
        "audio_mode": audio_package.get("audio_mode"),
        "test_mode": bool(audio_package.get("test_mode")),
        "exact_ayah_sync": bool(audio_package.get("exact_ayah_sync")),
        "exact_word_sync": bool(audio_package.get("exact_word_sync")),
        "rights_confirmed": bool(audio_package.get("rights_confirmed")),
        "reciter": audio_package.get("reciter",{}),
        "channel_name": CHANNEL_NAME,
        "watermark_enabled": True,
        "background_theme": theme,
        "visual_engine_version": VISUAL_ENGINE_VERSION,
    }
    (OUTPUT_DIR/"manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_video(segment: dict, seo: dict) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for key in ("segment_id","video_type","surah","start_ayah","end_ayah","ayahs","text"):
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

    theme = choose_theme(segment)
    audio = AudioFileClip(audio_path)
    render_text, timings_by_ayah = build_text_renderer(segment, audio_package, width, height, font_path)
    timeline_starts = [float(item["start"]) for item in timeline]
    base_bg = make_canvas_bg(width, height)
    mrect = mihrab_rect(width, height)
    scene_w, scene_h = mrect[2]-mrect[0], mrect[3]-mrect[1]
    reciter_name = str(audio_package.get("reciter",{}).get("name","")).strip() or "تلاوة القرآن الكريم"

    def make_frame(t: float):
        frame = base_bg.copy()
        scene = procedural_scene(theme, scene_w, scene_h, t)
        frame.alpha_composite(draw_mihrab_frame(scene_w, scene_h, scene), (mrect[0],mrect[1]))
        ayah_index, _active_item = active_timeline_item(timeline, timeline_starts, t)
        ayah = segment["ayahs"][ayah_index]
        gnum = int(ayah.get("global_number", ayah_index+1))
        active_word = active_word_index(timings_by_ayah.get(gnum,[]), t)
        frame.alpha_composite(render_text(ayah_index, active_word, reciter_name).copy())
        return np.asarray(frame.convert("RGB"), dtype=np.uint8)

    video_path = OUTPUT_DIR/f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR/f"{segment['segment_id']}_preview.png"
    preview_t = min(max(duration*.22,.10), max(.10,duration-.05))
    Image.fromarray(make_frame(preview_t)).save(preview_path)

    video = VideoClip(frame_function=make_frame, duration=duration).with_audio(audio)
    try:
        video.write_videofile(
            str(video_path), fps=FPS, codec="libx264", audio_codec="aac",
            audio_bitrate="192k",
            bitrate="6000k" if segment.get("video_type") == "short" else "7500k",
            preset=os.getenv("QURAN_FFMPEG_PRESET","medium"),
            threads=2, pixel_format="yuv420p", logger="bar",
        )
    finally:
        video.close()
        audio.close()

    if not video_path.is_file() or video_path.stat().st_size < MINIMUM_VIDEO_SIZE:
        raise RuntimeError("Generated video is missing or empty.")

    save_metadata(segment, seo, audio_package, video_path, preview_path, theme)
    _write_memory(theme, str(segment["segment_id"]))

    print("\n========== BROADCAST QURAN VIDEO READY ==========")
    print("Resolution:", f"{width}x{height}")
    print("Theme:", theme)
    print("Channel:", CHANNEL_NAME)
    print("Surah:", segment["surah"])
    print("Ayahs:", f"{segment['start_ayah']}-{segment['end_ayah']}")
    print("Video:", video_path)
    print("Preview:", preview_path)
    print("=================================================")
    return str(video_path)
