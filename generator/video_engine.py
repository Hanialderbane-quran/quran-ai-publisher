"""Broadcast-quality Quran renderer for MoviePy 2.x."""
from __future__ import annotations

import bisect
import json
import os
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package
from generator.branding import branding_layer, channel_name
from generator.visual_identity import CinematicBackground, Theme

OUTPUT_DIR = Path("output")
ASSET_DIR = Path("assets")
FONT_DIR = ASSET_DIR / "fonts"
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


def fade_factor(local_t: float, item_start: float, item_end: float) -> float:
    fade = min(0.45, max(0.16, (item_end - item_start) * 0.12))
    fade_in = max(0.0, min(1.0, (local_t - item_start) / fade))
    fade_out = max(0.0, min(1.0, (item_end - local_t) / fade))
    return min(fade_in, fade_out)


def glass_panel(size: tuple[int, int], box: tuple[int, int, int, int], radius: int, theme: Theme, alpha: int = 215) -> Image.Image:
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((box[0] + 12, box[1] + 14, box[2] + 12, box[3] + 14), radius=radius, fill=(0, 0, 0, 125))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(10, radius // 2)))
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel, "RGBA")
    pd.rounded_rectangle(box, radius=radius, fill=(*theme.panel, alpha), outline=(*theme.accent, 235), width=max(2, radius // 10))
    inset = max(7, radius // 4)
    pd.rounded_rectangle((box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset), radius=max(8, radius - inset), outline=(*theme.accent_soft, 55), width=max(1, radius // 16))
    return Image.alpha_composite(shadow, panel)


def decorative_frame(width: int, height: int, theme: Theme, vertical: bool) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    margin = int(width * (0.045 if vertical else 0.032))
    top = int(height * 0.025)
    bottom = height - top
    radius = max(24, int(min(width, height) * 0.025))
    draw.rounded_rectangle((margin, top, width - margin, bottom), radius=radius, outline=(*theme.accent, 130), width=max(2, int(min(width, height) * 0.0025)))
    inner = margin + max(8, int(width * 0.008))
    draw.rounded_rectangle((inner, top + 10, width - inner, bottom - 10), radius=max(18, radius - 8), outline=(*theme.accent_soft, 38), width=1)
    return layer


def draw_word_lines(draw, lines, font, center_x, start_y, active_word, theme, opacity, line_gap) -> None:
    line_height = int(font.size * line_gap)
    global_word_index = 0
    alpha = max(0, min(255, int(255 * opacity)))
    for line in lines:
        line_text = " ".join(line)
        line_width = draw.textlength(line_text, font=font, direction="rtl", language="ar")
        x = center_x + line_width / 2
        for word in line:
            word_width = draw.textlength(word, font=font, direction="rtl", language="ar")
            is_active = active_word == global_word_index
            fill_rgb = theme.accent_soft if is_active else theme.text
            stroke_rgb = theme.accent if is_active else (0, 0, 0)
            draw.text((x, start_y), word, font=font, fill=(*fill_rgb, alpha), anchor="ra", direction="rtl", language="ar", stroke_width=max(1, int(font.size * (0.025 if is_active else 0.014))), stroke_fill=(*stroke_rgb, max(60, int(alpha * 0.65))))
            x -= word_width + font.size * 0.21
            global_word_index += 1
        start_y += line_height


def render_long_layout(segment, ayah_index, active_word, reciter_name, width, height, font_path, theme, opacity) -> Image.Image:
    scale = render_scale()
    layer = decorative_frame(width, height, theme, vertical=False)
    draw = ImageDraw.Draw(layer, "RGBA")
    title_font = ImageFont.truetype(font_path, max(24, int(46 * scale)))
    body_font = ImageFont.truetype(font_path, max(30, int(62 * scale)))
    info_font = ImageFont.truetype(font_path, max(18, int(28 * scale)))
    header = (int(width * 0.34), int(height * 0.055), int(width * 0.66), int(height * 0.145))
    layer = Image.alpha_composite(layer, glass_panel((width, height), header, max(18, int(24 * scale)), theme, 220))
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.text((width // 2, (header[1] + header[3]) // 2), f"سورة {segment['surah']}", font=title_font, fill=(*theme.accent_soft, 255), anchor="mm", direction="rtl", language="ar")
    panel = (int(width * 0.09), int(height * 0.57), int(width * 0.91), int(height * 0.90))
    layer = Image.alpha_composite(layer, glass_panel((width, height), panel, max(24, int(30 * scale)), theme, 220))
    draw = ImageDraw.Draw(layer, "RGBA")
    ayah = segment["ayahs"][ayah_index]
    text = str(ayah.get("text", ""))
    max_text_width = int((panel[2] - panel[0]) * 0.84)
    lines = wrap_words(draw, text, body_font, max_text_width)
    while len(lines) > 4 and body_font.size > max(24, int(38 * scale)):
        body_font = ImageFont.truetype(font_path, body_font.size - 2)
        lines = wrap_words(draw, text, body_font, max_text_width)
    total_height = len(lines) * int(body_font.size * 1.52)
    start_y = panel[1] + max(int(body_font.size * 0.40), (panel[3] - panel[1] - total_height) // 2 - int(body_font.size * 0.18))
    draw_word_lines(draw, lines, body_font, width / 2, start_y, active_word, theme, opacity, 1.52)
    part = str(segment.get("display_part", "")).strip()
    footer_text = f"الآية {ayah['ayah']}  •  {reciter_name}"
    if part:
        footer_text += f"  •  {part}"
    draw.text((width // 2, panel[3] - int((panel[3] - panel[1]) * 0.10)), footer_text, font=info_font, fill=(225, 232, 231, 238), anchor="mm", direction="rtl", language="ar")
    return layer


def render_short_layout(segment, ayah_index, active_word, reciter_name, width, height, font_path, theme, opacity) -> Image.Image:
    scale = render_scale()
    layer = decorative_frame(width, height, theme, vertical=True)
    draw = ImageDraw.Draw(layer, "RGBA")
    title_font = ImageFont.truetype(font_path, max(26, int(52 * scale)))
    body_font = ImageFont.truetype(font_path, max(34, int(72 * scale)))
    info_font = ImageFont.truetype(font_path, max(20, int(30 * scale)))
    header = (int(width * 0.18), int(height * 0.085), int(width * 0.82), int(height * 0.155))
    layer = Image.alpha_composite(layer, glass_panel((width, height), header, max(20, int(28 * scale)), theme, 218))
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.text((width // 2, (header[1] + header[3]) // 2), f"سورة {segment['surah']}", font=title_font, fill=(*theme.accent_soft, 255), anchor="mm", direction="rtl", language="ar")
    panel = (int(width * 0.07), int(height * 0.36), int(width * 0.93), int(height * 0.73))
    layer = Image.alpha_composite(layer, glass_panel((width, height), panel, max(28, int(38 * scale)), theme, 224))
    draw = ImageDraw.Draw(layer, "RGBA")
    ayah = segment["ayahs"][ayah_index]
    text = str(ayah.get("text", ""))
    max_text_width = int((panel[2] - panel[0]) * 0.80)
    lines = wrap_words(draw, text, body_font, max_text_width)
    while len(lines) > 7 and body_font.size > max(28, int(43 * scale)):
        body_font = ImageFont.truetype(font_path, body_font.size - 2)
        lines = wrap_words(draw, text, body_font, max_text_width)
    total_height = len(lines) * int(body_font.size * 1.48)
    start_y = panel[1] + max(int(body_font.size * 0.35), (panel[3] - panel[1] - total_height) // 2)
    draw_word_lines(draw, lines, body_font, width / 2, start_y, active_word, theme, opacity, 1.48)
    draw.text((width // 2, int(height * 0.785)), f"الآية {ayah['ayah']}", font=title_font, fill=(*theme.accent_soft, 245), anchor="mm", direction="rtl", language="ar")
    draw.text((width // 2, int(height * 0.835)), reciter_name, font=info_font, fill=(231, 236, 234, 230), anchor="mm", direction="rtl", language="ar")
    return layer


def make_text_layer(segment, ayah_index, active_word, reciter_name, width, height, font_path, theme, opacity) -> Image.Image:
    if segment.get("video_type") == "short":
        return render_short_layout(segment, ayah_index, active_word, reciter_name, width, height, font_path, theme, opacity)
    return render_long_layout(segment, ayah_index, active_word, reciter_name, width, height, font_path, theme, opacity)


def save_metadata(segment, seo, audio_package, video_path, preview_path, theme, background) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "title.txt").write_text(str(seo.get("title", "")), encoding="utf-8")
    (OUTPUT_DIR / "description.txt").write_text(str(seo.get("description", "")), encoding="utf-8")
    (OUTPUT_DIR / "segment_text.txt").write_text(str(segment.get("text", "")), encoding="utf-8")
    (OUTPUT_DIR / "tags.json").write_text(json.dumps(seo.get("tags", []), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "segment_id": segment["segment_id"], "video_type": segment["video_type"], "surah": segment["surah"],
        "start_ayah": segment["start_ayah"], "end_ayah": segment["end_ayah"], "video_path": str(video_path),
        "preview_path": str(preview_path), "privacy_status": str(seo.get("privacy_status", "private")),
        "audio_mode": audio_package.get("audio_mode"), "test_mode": bool(audio_package.get("test_mode")),
        "exact_ayah_sync": bool(audio_package.get("exact_ayah_sync")), "exact_word_sync": bool(audio_package.get("exact_word_sync")),
        "rights_confirmed": bool(audio_package.get("rights_confirmed")), "reciter": audio_package.get("reciter", {}),
        "visual_engine_version": "broadcast_identity_3.1", "visual_theme": theme.key,
        "background_family": theme.background_family, "background_asset": str(background.path) if background.path else "procedural",
        "layout": "vertical_short" if segment.get("video_type") == "short" else "horizontal_long",
        "branding": {"enabled": True, "channel_name": channel_name(), "placement": "bottom_left_safe_zone"},
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
    source = CinematicBackground(segment, width, height)
    timeline_starts = [float(item["start"]) for item in timeline]
    word_timings: dict[int, list[dict]] = {}
    for item in audio_package.get("word_timeline", []):
        word_timings.setdefault(int(item["global_number"]), []).append(item)
    reciter_name = str(audio_package.get("reciter", {}).get("name", "")).strip() or "القرآن الكريم"
    brand = branding_layer((width, height), vertical=segment.get("video_type") == "short", accent=source.theme.accent, accent_soft=source.theme.accent_soft)

    def make_frame(t: float) -> np.ndarray:
        frame = source.frame(t, duration)
        ayah_index, timeline_item = active_timeline_item(timeline, timeline_starts, t)
        ayah = segment["ayahs"][ayah_index]
        global_number = int(ayah.get("global_number", ayah_index + 1))
        active_word = active_word_index(word_timings.get(global_number, []), t)
        opacity = fade_factor(t, float(timeline_item["start"]), float(timeline_item["end"]))
        frame.alpha_composite(make_text_layer(segment, ayah_index, active_word, reciter_name, width, height, font_path, source.theme, opacity))
        frame.alpha_composite(brand)
        return np.asarray(frame.convert("RGB"), dtype=np.uint8)

    video_path = OUTPUT_DIR / f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR / f"{segment['segment_id']}_preview.png"
    preview_t = min(max(duration * 0.22, 0.10), max(0.10, duration - 0.05))
    Image.fromarray(make_frame(preview_t)).save(preview_path)
    video = VideoClip(frame_function=make_frame, duration=duration).with_audio(audio)
    try:
        video.write_videofile(str(video_path), fps=FPS, codec="libx264", audio_codec="aac", audio_bitrate="192k", bitrate="6500k" if segment.get("video_type") == "short" else "8500k", preset=os.getenv("QURAN_FFMPEG_PRESET", "medium"), threads=2, pixel_format="yuv420p", logger="bar")
    finally:
        video.close()
        audio.close()
    if not video_path.is_file() or video_path.stat().st_size < MINIMUM_VIDEO_SIZE:
        raise RuntimeError("Generated video is missing or empty.")
    save_metadata(segment, seo, audio_package, video_path, preview_path, source.theme, source)
    print("\n========== QURAN VIDEO READY ==========")
    print("Channel:", channel_name())
    print("Resolution:", f"{width}x{height}")
    print("Type:", segment["video_type"])
    print("Theme:", source.theme.key)
    print("Surah:", segment["surah"])
    print("Ayahs:", f"{segment['start_ayah']}-{segment['end_ayah']}")
    print("Video:", video_path)
    print("Preview:", preview_path)
    print("=======================================")
    return str(video_path)
