"""Generate a self-contained local library of animated Quran backgrounds.

The files are created during GitHub Actions, so the publisher never depends on
external download links.  Every background is 1920x1080, silent, loopable and
contains restrained Islamic architectural motion suitable for Quran videos.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
from moviepy import VideoClip
from PIL import Image, ImageDraw, ImageFilter

WIDTH = int(os.getenv("QURAN_VIDEO_WIDTH", "1920"))
HEIGHT = int(os.getenv("QURAN_VIDEO_HEIGHT", "1080"))
FPS = 24
DURATION = 12.0
OUTPUT = Path("assets/background_videos")

THEMES = {
    "royal_mosque_burgundy": ((49, 5, 42), (15, 2, 24), (233, 192, 92), (123, 199, 221)),
    "royal_mosque_navy": ((9, 27, 65), (2, 8, 25), (232, 200, 111), (112, 188, 222)),
    "royal_mosque_emerald": ((7, 49, 43), (2, 18, 22), (230, 198, 103), (111, 199, 171)),
    "royal_mosque_twilight": ((62, 26, 79), (12, 6, 29), (236, 190, 95), (180, 159, 224)),
    "royal_mosque_dawn": ((87, 44, 64), (24, 11, 29), (242, 205, 112), (237, 170, 143)),
    "royal_mosque_blue": ((12, 56, 88), (3, 17, 34), (233, 198, 101), (119, 195, 227)),
}


def gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    arr = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for y in range(HEIGHT):
        u = y / max(1, HEIGHT - 1)
        arr[y, :, :] = [int(top[i] * (1 - u) + bottom[i] * u) for i in range(3)]
    return Image.fromarray(arr, "RGB").convert("RGBA")


def add_glow(img: Image.Image, x: int, y: int, radius: int, color: tuple[int, int, int], alpha: int) -> None:
    layer = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(*color, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius // 2)))


def draw_geometric_border(draw: ImageDraw.ImageDraw, gold: tuple[int, int, int], t: float) -> None:
    pulse = 185 + int(35 * (0.5 + 0.5 * math.sin(t * 0.7)))
    g = (*gold, pulse)
    draw.rounded_rectangle((40, 36, WIDTH-40, HEIGHT-36), radius=42, outline=g, width=5)
    draw.rounded_rectangle((72, 66, WIDTH-72, HEIGHT-66), radius=34, outline=(*gold, 70), width=2)
    for side_x in (95, WIDTH-95):
        draw.rounded_rectangle((side_x-34, 170, side_x+34, HEIGHT-170), radius=20, outline=(*gold, 165), width=3)
        for y in range(210, HEIGHT-210, 90):
            r = 16
            draw.regular_polygon((side_x, y, r), n_sides=8, rotation=22.5, outline=(*gold, 105), width=2)


def draw_arch(draw: ImageDraw.ImageDraw, gold: tuple[int, int, int]) -> None:
    left, right = int(WIDTH * 0.18), int(WIDTH * 0.82)
    top, base = 90, int(HEIGHT * 0.72)
    draw.line((left, int(HEIGHT*.31), left, base), fill=(*gold, 220), width=8)
    draw.line((right, int(HEIGHT*.31), right, base), fill=(*gold, 220), width=8)
    draw.arc((left, top, right, int(HEIGHT*.58)), 180, 360, fill=(*gold, 235), width=11)
    draw.arc((left+32, top+34, right-32, int(HEIGHT*.56)), 180, 360, fill=(*gold, 100), width=3)
    for x in range(left+70, right-69, 105):
        draw.ellipse((x-7, 147, x+7, 161), fill=(*gold, 130))


def draw_mosque(img: Image.Image, dome_color: tuple[int, int, int], gold: tuple[int, int, int], t: float) -> None:
    layer = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(layer, "RGBA")
    center = WIDTH // 2
    base_y = int(HEIGHT * 0.69)
    body_w = 660
    body_h = 205
    body = (center-body_w//2, base_y-body_h, center+body_w//2, base_y)
    draw.rounded_rectangle(body, radius=28, fill=(11, 17, 28, 232), outline=(*gold, 105), width=3)

    # Main dome and side domes.
    sway = math.sin(t * 0.28) * 3
    draw.pieslice((center-205, base_y-body_h-260+sway, center+205, base_y-body_h+150+sway), 180, 360, fill=(*dome_color, 245), outline=(*gold, 210), width=5)
    draw.rectangle((center-190, base_y-body_h-62+sway, center+190, base_y-body_h), fill=(*dome_color, 245))
    for offset in (-270, 270):
        x = center + offset
        draw.pieslice((x-112, base_y-body_h-135, x+112, base_y-body_h+90), 180, 360, fill=(*dome_color, 235), outline=(*gold, 180), width=4)
        draw.rectangle((x-103, base_y-body_h-28, x+103, base_y-body_h+55), fill=(*dome_color, 235))

    # Minarets.
    for x in (center-410, center+410):
        draw.rounded_rectangle((x-34, base_y-390, x+34, base_y), radius=14, fill=(8, 15, 26, 245), outline=(*gold, 160), width=3)
        draw.polygon([(x-50, base_y-390), (x, base_y-462), (x+50, base_y-390)], fill=(*dome_color, 245), outline=(*gold, 190))
        draw.ellipse((x-7, base_y-480, x+7, base_y-466), fill=(*gold, 230))

    # Lit windows.
    for i in range(9):
        x = center - 270 + i * 67
        brightness = 95 + int(45 * (0.5 + 0.5 * math.sin(t * 1.2 + i)))
        draw.rounded_rectangle((x-14, base_y-105, x+14, base_y-50), radius=12, fill=(*gold, brightness))

    shadow = layer.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(shadow)
    img.alpha_composite(layer)


def draw_lanterns(img: Image.Image, gold: tuple[int, int, int], t: float) -> None:
    layer = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(layer, "RGBA")
    for i, x in enumerate((300, 520, WIDTH-520, WIDTH-300)):
        swing = math.sin(t * 0.75 + i * 1.3) * 9
        top = 92 + (i % 2) * 28
        draw.line((x, 0, x+swing, top), fill=(*gold, 150), width=3)
        cx = x+swing
        draw.rounded_rectangle((cx-22, top, cx+22, top+70), radius=12, fill=(20, 9, 24, 230), outline=(*gold, 210), width=3)
        add_glow(layer, int(cx), top+36, 52, gold, 34)
        draw.ellipse((cx-10, top+24, cx+10, top+44), fill=(*gold, 210))
    img.alpha_composite(layer)


def frame(theme: str, t: float) -> np.ndarray:
    top, bottom, gold, dome = THEMES[theme]
    img = gradient(top, bottom)
    add_glow(img, int(WIDTH*.72), int(HEIGHT*.20), 210, dome, 50)
    draw = ImageDraw.Draw(img, "RGBA")

    # Slow moving stars/particles.
    for i in range(165):
        x = (i * 173 + int(t * (4 + i % 4))) % WIDTH
        y = (i * 97 + 31) % int(HEIGHT * .62)
        alpha = 55 + int(45 * (0.5 + 0.5 * math.sin(t*.9 + i*.33)))
        r = 1 + (i % 5 == 0)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(*gold, alpha))

    draw_geometric_border(draw, gold, t)
    draw_arch(draw, gold)
    draw_mosque(img, dome, gold, t)
    draw_lanterns(img, gold, t)

    # Gentle vignette.
    vignette = Image.new("RGBA", img.size)
    vd = ImageDraw.Draw(vignette, "RGBA")
    for i in range(14):
        inset = i * 16
        vd.rounded_rectangle((inset, inset, WIDTH-inset, HEIGHT-inset), radius=50, outline=(0, 0, 0, 9+i*4), width=22)
    img.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(20)))
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def render_theme(theme: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / f"{theme}.mp4"
    if destination.is_file() and destination.stat().st_size > 250_000:
        print("Background already exists:", destination)
        return
    clip = VideoClip(frame_function=lambda t: frame(theme, t), duration=DURATION)
    try:
        clip.write_videofile(
            str(destination),
            fps=FPS,
            codec="libx264",
            audio=False,
            bitrate="4500k",
            preset="veryfast",
            pixel_format="yuv420p",
            threads=2,
            logger="bar",
        )
    finally:
        clip.close()
    if not destination.is_file() or destination.stat().st_size < 250_000:
        raise RuntimeError(f"Background generation failed: {destination}")
    print("Background ready:", destination)


def main() -> None:
    for theme in THEMES:
        render_theme(theme)
    print(f"Generated {len(THEMES)} local animated backgrounds.")


if __name__ == "__main__":
    main()
