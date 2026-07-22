"""
Quran AI Publisher
Compact Professional Video Engine
Version 7.0
"""

import json
import math
import os
import random

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from generator.audio_engine import get_audio


WIDTH = 1080
HEIGHT = 1920
FPS = 24
MIN_DURATION = 8.0
MAX_DURATION = 120.0

OUTPUT_DIR = "output"
BACKGROUND_DIR = "assets/backgrounds"
FONT_DIR = "assets/fonts"

VIDEO_PATH = os.path.join(OUTPUT_DIR, "video.mp4")
PREVIEW_PATH = os.path.join(OUTPUT_DIR, "preview.png")


def ensure_folders():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BACKGROUND_DIR, exist_ok=True)
    os.makedirs(FONT_DIR, exist_ok=True)


def find_font():
    candidates = [
        os.path.join(FONT_DIR, "NotoNaskhArabic-Bold.ttf"),
        os.path.join(FONT_DIR, "NotoNaskhArabic-Regular.ttf"),
        os.path.join(FONT_DIR, "arabic.ttf"),
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError("No Arabic font was found.")


def find_background():
    allowed = (".jpg", ".jpeg", ".png", ".webp")

    files = [
        os.path.join(BACKGROUND_DIR, name)
        for name in os.listdir(BACKGROUND_DIR)
        if name.lower().endswith(allowed)
    ]

    return random.choice(files) if files else None


def make_gradient():
    top = np.array([17, 66, 76], dtype=np.float32)
    bottom = np.array([2, 10, 22], dtype=np.float32)

    y = np.linspace(
        0,
        1,
        HEIGHT,
        dtype=np.float32
    )[:, None, None]

    gradient = (
        top[None, None, :] * (1 - y)
        +
        bottom[None, None, :] * y
    )

    return np.repeat(
        gradient,
        WIDTH,
        axis=1
    ).astype(np.uint8)


def cover(image, width, height):
    scale = max(
        width / image.width,
        height / image.height
    )

    new_size = (
        math.ceil(image.width * scale),
        math.ceil(image.height * scale)
    )

    image = image.resize(
        new_size,
        Image.Resampling.LANCZOS
    )

    left = (image.width - width) // 2
    top = (image.height - height) // 2

    return image.crop(
        (
            left,
            top,
            left + width,
            top + height
        )
    )


def load_background():
    path = find_background()

    if not path:
        print("Background: automatic gradient")
        return None

    image = Image.open(path).convert("RGB")
    image = ImageEnhance.Brightness(image).enhance(0.72)
    image = ImageEnhance.Contrast(image).enhance(1.10)
    image = ImageEnhance.Color(image).enhance(0.80)

    print("Background:", path)

    return image


def measure(draw, text, font):
    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
        direction="rtl",
        language="ar"
    )

    return box[2] - box[0]


def wrap_text(draw, text, font, max_width):
    lines = []
    current = []

    for word in text.split():
        test = " ".join(current + [word])

        if measure(draw, test, font) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))

            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def fit_text(draw, text, font_path):
    for size in range(84, 43, -2):
        font = ImageFont.truetype(
            font_path,
            size
        )

        lines = wrap_text(
            draw,
            text,
            font,
            WIDTH - 220
        )

        line_height = int(size * 1.55)

        if (
            len(lines) <= 8
            and len(lines) * line_height <= 760
        ):
            return font, lines, line_height

    font = ImageFont.truetype(
        font_path,
        44
    )

    return (
        font,
        wrap_text(
            draw,
            text,
            font,
            WIDTH - 220
        ),
        70
    )


def draw_rtl(
    draw,
    xy,
    text,
    font,
    fill,
    stroke_width=0
):
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor="mm",
        align="center",
        direction="rtl",
        language="ar",
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0)
    )


def make_text_layer(verse):
    font_path = find_font()

    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

    title_font = ImageFont.truetype(
        font_path,
        54
    )

    footer_font = ImageFont.truetype(
        font_path,
        38
    )

    verse_font, lines, line_height = fit_text(
        draw,
        verse["text"],
        font_path
    )

    draw.rounded_rectangle(
        (60, 300, WIDTH - 60, 1585),
        radius=60,
        fill=(1, 13, 20, 190),
        outline=(232, 202, 124, 225),
        width=4
    )

    draw.rounded_rectangle(
        (76, 316, WIDTH - 76, 1569),
        radius=48,
        outline=(255, 239, 185, 65),
        width=2
    )

    title = (
        f"سورة {verse['surah']} "
        f"• الآية {verse['ayah']}"
    )

    draw_rtl(
        draw,
        (WIDTH // 2, 420),
        title,
        title_font,
        (255, 235, 180),
        1
    )

    draw.line(
        (280, 510, 800, 510),
        fill=(232, 202, 124, 150),
        width=2
    )

    draw.ellipse(
        (532, 502, 548, 518),
        fill=(255, 235, 170, 240)
    )

    total_height = len(lines) * line_height

    start_y = (
        575
        +
        max(
            0,
            (730 - total_height) // 2
        )
    )

    for index, line in enumerate(lines):
        y = (
            start_y
            +
            index * line_height
            +
            line_height // 2
        )

        draw_rtl(
            draw,
            (WIDTH // 2, y),
            line,
            verse_font,
            (255, 255, 255),
            2
        )

    draw_rtl(
        draw,
        (WIDTH // 2, 1470),
        "القرآن الكريم",
        footer_font,
        (225, 232, 235)
    )

    return layer


def make_particles(count=30):
    random.seed(2026)

    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "r": random.uniform(1.2, 4.0),
            "speed": random.uniform(12, 32),
            "phase": random.uniform(0, math.tau),
            "alpha": random.randint(45, 135)
        }
        for _ in range(count)
    ]


def particle_layer(t, particles):
    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

    for particle in particles:
        y = (
            particle["y"]
            -
            t * particle["speed"]
        ) % (HEIGHT + 100) - 50

        x = (
            particle["x"]
            +
            math.sin(
                t * 0.7
                +
                particle["phase"]
            ) * 18
        )

        alpha = int(
            particle["alpha"]
            *
            (
                0.65
                +
                0.35
                *
                math.sin(
                    t
                    +
                    particle["phase"]
                )
            )
        )

        radius = particle["r"]

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill=(
                255,
                232,
                165,
                max(20, alpha)
            )
        )

    return layer.filter(
        ImageFilter.GaussianBlur(1.1)
    )


def glow_layer(t):
    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

    x = (
        WIDTH * 0.5
        +
        math.sin(t * 0.22) * 145
    )

    y = (
        HEIGHT * 0.15
        +
        math.cos(t * 0.18) * 50
    )

    radius = int(
        320
        +
        math.sin(t * 0.65) * 35
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius
        ),
        fill=(255, 224, 150, 45)
    )

    return layer.filter(
        ImageFilter.GaussianBlur(115)
    )


def background_frame(
    t,
    duration,
    source,
    gradient
):
    if source is None:
        shift = int(
            math.sin(t * 0.22) * 24
        )

        shifted = np.roll(
            gradient,
            shift,
            axis=1
        )

        return Image.fromarray(
            shifted
        ).convert("RGBA")

    progress = t / max(
        duration,
        0.001
    )

    zoom = 1.05 + progress * 0.08

    width = int(WIDTH * zoom)
    height = int(HEIGHT * zoom)

    image = cover(
        source,
        width,
        height
    )

    max_x = width - WIDTH
    max_y = height - HEIGHT

    x = int(
        max_x
        *
        (
            0.5
            +
            0.25
            *
            math.sin(
                progress * math.pi
            )
        )
    )

    y = int(
        max_y
        *
        (
            0.5
            +
            0.20
            *
            math.cos(
                progress * math.pi
            )
        )
    )

    return image.crop(
        (
            x,
            y,
            x + WIDTH,
            y + HEIGHT
        )
    ).convert("RGBA")


def animate_text(
    layer,
    t,
    duration
):
    fade_in = min(
        1.0,
        max(
            0.0,
            t / 1.2
        )
    )

    fade_out = min(
        1.0,
        max(
            0.0,
            (
                duration - t
            ) / 0.8
        )
    )

    opacity = min(
        fade_in,
        fade_out
    )

    animated = layer.copy()

    alpha = animated.getchannel(
        "A"
    ).point(
        lambda value: int(
            value * opacity
        )
    )

    animated.putalpha(alpha)

    offset = int(
        (
            1.0 - fade_in
        ) * 34
    )

    if offset == 0:
        return animated

    moved = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    moved.alpha_composite(
        animated,
        (0, offset)
    )

    return moved


def save_metadata(verse, seo):
    with open(
        os.path.join(
            OUTPUT_DIR,
            "title.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(seo["title"])

    with open(
        os.path.join(
            OUTPUT_DIR,
            "description.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(seo["description"])

    with open(
        os.path.join(
            OUTPUT_DIR,
            "tags.json"
        ),
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            seo["tags"],
            file,
            ensure_ascii=False,
            indent=2
        )

    with open(
        os.path.join(
            OUTPUT_DIR,
            "verse.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(verse["text"])


def build_video(verse, seo):
    ensure_folders()
    save_metadata(verse, seo)

    audio_path = get_audio(verse)

    audio = AudioFileClip(
        audio_path
    )

    duration = max(
        MIN_DURATION,
        min(
            float(audio.duration),
            MAX_DURATION
        )
    )

    if audio.duration > duration:
        audio = audio.subclipped(
            0,
            duration
        )

    source = load_background()
    gradient = make_gradient()
    text_layer = make_text_layer(verse)
    particles = make_particles()

    def make_frame(t):
        frame = background_frame(
            t,
            duration,
            source,
            gradient
        )

        frame = Image.alpha_composite(
            frame,
            glow_layer(t)
        )

        frame = Image.alpha_composite(
            frame,
            particle_layer(
                t,
                particles
            )
        )

        frame = Image.alpha_composite(
            frame,
            animate_text(
                text_layer,
                t,
                duration
            )
        )

        return np.asarray(
            frame.convert("RGB"),
            dtype=np.uint8
        )

    preview_time = min(
        1.5,
        duration / 2
    )

    Image.fromarray(
        make_frame(preview_time)
    ).save(PREVIEW_PATH)

    video = VideoClip(
        frame_function=make_frame,
        duration=duration
    ).with_audio(audio)

    video.write_videofile(
        VIDEO_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        bitrate="5000k",
        preset="medium",
        threads=2,
        pixel_format="yuv420p",
        logger="bar"
    )

    video.close()
    audio.close()

    if (
        not os.path.isfile(VIDEO_PATH)
        or os.path.getsize(VIDEO_PATH) < 10000
    ):
        raise RuntimeError(
            "The generated video is missing or empty."
        )

    print(
        "Video created successfully:",
        VIDEO_PATH
    )

    return VIDEO_PATH
