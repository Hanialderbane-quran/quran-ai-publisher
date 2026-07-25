"""Automatic channel branding for every rendered video."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CONFIG_PATH = Path("config.json")
ASSET_DIR = Path("assets")
FONT_DIR = ASSET_DIR / "fonts"


@lru_cache(maxsize=1)
def channel_name() -> str:
    """Read the real channel name from config without hard-coding or renaming it."""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        name = str(data.get("channel_name", "")).strip()
        if name:
            return name
    except (OSError, ValueError, TypeError):
        pass
    return "قناة القرآن الكريم"


def _font_path() -> str:
    candidates = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        FONT_DIR / "arabic.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    raise RuntimeError("No Arabic font was found for channel branding.")


def branding_layer(
    size: tuple[int, int],
    *,
    vertical: bool,
    accent: tuple[int, int, int],
    accent_soft: tuple[int, int, int],
) -> Image.Image:
    """Create a small, readable, non-obstructive logo carrying the channel name."""
    width, height = size
    scale = min(width / 1920.0, height / 1080.0) if not vertical else min(width / 1080.0, height / 1920.0)
    scale = max(0.45, scale)

    font_size = max(19, int((29 if vertical else 27) * scale))
    font = ImageFont.truetype(_font_path(), font_size)
    name = channel_name()

    measure = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    md = ImageDraw.Draw(measure)
    bbox = md.textbbox((0, 0), name, font=font, direction="rtl", language="ar")
    text_w = max(1, bbox[2] - bbox[0])
    text_h = max(1, bbox[3] - bbox[1])

    pad_x = max(14, int(20 * scale))
    pad_y = max(9, int(12 * scale))
    badge_w = text_w + pad_x * 2
    badge_h = text_h + pad_y * 2
    margin_x = int(width * (0.045 if vertical else 0.035))
    margin_y = int(height * (0.035 if vertical else 0.045))

    # Keep the identity away from Shorts controls and away from the Quran text panel.
    x1 = margin_x
    y1 = height - margin_y - badge_h
    x2 = x1 + badge_w
    y2 = y1 + badge_h
    radius = max(12, int(badge_h * 0.34))

    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((x1 + 5, y1 + 7, x2 + 5, y2 + 7), radius=radius, fill=(0, 0, 0, 115))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(5, int(7 * scale))))

    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=(7, 18, 22, 178), outline=(*accent, 205), width=max(1, int(2 * scale)))
    draw.ellipse((x1 + pad_x * 0.55, y1 + badge_h * 0.34, x1 + pad_x * 1.15, y1 + badge_h * 0.66), fill=(*accent_soft, 235))
    draw.text(
        (x2 - pad_x, (y1 + y2) // 2),
        name,
        font=font,
        fill=(246, 244, 232, 225),
        anchor="rm",
        direction="rtl",
        language="ar",
        stroke_width=max(1, int(scale)),
        stroke_fill=(0, 0, 0, 105),
    )
    return Image.alpha_composite(shadow, layer)
