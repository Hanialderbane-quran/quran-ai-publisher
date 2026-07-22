"""
Quran AI Publisher
Professional Animated Video Engine
Version 6.0
"""

import json
import math
import os
import random

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from generator.audio_engine import get_audio


OUTPUT_FOLDER = "output"
BACKGROUND_FOLDER = "assets/backgrounds"
FONT_FOLDER = "assets/fonts"

VIDEO_PATH = os.path.join(OUTPUT_FOLDER, "video.mp4")
PREVIEW_PATH = os.path.join(OUTPUT_FOLDER, "preview.png")

WIDTH = 1080
HEIGHT = 1920
FPS = 24

MIN_DURATION = 8.0
MAX_DURATION = 120.0

GOLD = (232, 202, 124)
LIGHT_GOLD = (255, 235, 180)
WHITE = (255, 255, 255)
SOFT_WHITE = (225, 232, 235)


def prepare_folders():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(BACKGROUND_FOLDER, exist_ok=True)
    os.makedirs(FONT_FOLDER, exist_ok=True)


def find_font():

    possible_fonts = [
        os.path.join(
            FONT_FOLDER,
            "NotoNaskhArabic-Bold.ttf"
        ),
        os.path.join(
            FONT_FOLDER,
            "NotoNaskhArabic-Regular.ttf"
        ),
        os.path.join(
            FONT_FOLDER,
            "arabic.ttf"
        ),
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for font_path in possible_fonts:

        if os.path.isfile(font_path):
            return font_path

    raise FileNotFoundError(
        "No Arabic font was found."
    )


def find_background():

    supported_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    )

    backgrounds = []

    if not os.path.isdir(BACKGROUND_FOLDER):
        return None

    for file_name in os.listdir(
        BACKGROUND_FOLDER
    ):

        if file_name.lower().endswith(
            supported_extensions
        ):

            backgrounds.append(
                os.path.join(
                    BACKGROUND_FOLDER,
                    file_name
                )
            )

    if not backgrounds:
        return None

    backgrounds.sort()

    return random.choice(backgrounds)


def cover_image(
    image,
    target_width,
    target_height
):

    source_width, source_height = image.size

    scale = max(
        target_width / source_width,
        target_height / source_height
    )

    resized_width = math.ceil(
        source_width * scale
    )

    resized_height = math.ceil(
        source_height * scale
    )

    image = image.resize(
        (
            resized_width,
            resized_height
        ),
        Image.Resampling.LANCZOS
    )

    crop_left = max(
        0,
        (
            resized_width
            -
            target_width
        ) // 2
    )

    crop_top = max(
        0,
        (
            resized_height
            -
            target_height
        ) // 2
    )

    return image.crop(
        (
            crop_left,
            crop_top,
            crop_left + target_width,
            crop_top + target_height
        )
    )


def load_background_image():

    background_path = find_background()

    if background_path is None:

        print(
            "No custom background found. "
            "Using automatic animated background."
        )

        return None

    image = Image.open(
        background_path
    ).convert("RGB")

    image = ImageEnhance.Color(
        image
    ).enhance(0.78)

    image = ImageEnhance.Contrast(
        image
    ).enhance(1.12)

    image = ImageEnhance.Brightness(
        image
    ).enhance(0.72)

    print(
        "Background:",
        background_path
    )

    return image


def create_gradient_background():

    image = np.zeros(
        (
            HEIGHT,
            WIDTH,
            3
        ),
        dtype=np.uint8
    )

    top_color = np.array(
        [15, 62, 72],
        dtype=np.float32
    )

    middle_color = np.array(
        [6, 35, 48],
        dtype=np.float32
    )

    bottom_color = np.array(
        [2, 10, 20],
        dtype=np.float32
    )

    for y in range(HEIGHT):

        progress = y / max(
            HEIGHT - 1,
            1
        )

        if progress < 0.5:

            local_progress = (
                progress / 0.5
            )

            color = (
                top_color
                * (1.0 - local_progress)
                +
                middle_color
                * local_progress
            )

        else:

            local_progress = (
                progress - 0.5
            ) / 0.5

            color = (
                middle_color
                * (1.0 - local_progress)
                +
                bottom_color
                * local_progress
            )

        image[y, :, :] = np.clip(
            color,
            0,
            255
        )

    return image


def text_width(
    draw,
    text,
    font
):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
        direction="rtl",
        language="ar"
    )

    return box[2] - box[0]


def wrap_rtl_text(
    draw,
    text,
    font,
    max_width
):

    words = text.split()

    lines = []
    current_line = []

    for word in words:

        test_line = " ".join(
            current_line + [word]
        )

        width = text_width(
            draw,
            test_line,
            font
        )

        if width <= max_width:

            current_line.append(word)

        else:

            if current_line:

                lines.append(
                    " ".join(
                        current_line
                    )
                )

            current_line = [word]

    if current_line:

        lines.append(
            " ".join(
                current_line
            )
        )

    return lines


def fit_verse_text(
    draw,
    verse_text,
    font_path
):

    max_text_width = WIDTH - 230
    max_text_height = 760

    for font_size in range(
        82,
        43,
        -2
    ):

        font = ImageFont.truetype(
            font_path,
            font_size
        )

        lines = wrap_rtl_text(
            draw,
            verse_text,
            font,
            max_text_width
        )

        line_height = int(
            font_size * 1.55
        )

        total_height = (
            len(lines)
            *
            line_height
        )

        if (
            len(lines) <= 8
            and
            total_height
            <=
            max_text_height
        ):

            return (
                font,
                lines,
                line_height
            )

    fallback_font = ImageFont.truetype(
        font_path,
        44
    )

    fallback_lines = wrap_rtl_text(
        draw,
        verse_text,
        fallback_font,
        max_text_width
    )

    return (
        fallback_font,
        fallback_lines,
        70
    )


def draw_centered_rtl(
    draw,
    x,
    y,
    text,
    font,
    fill,
    stroke_width=0,
    stroke_fill=(0, 0, 0)
):

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        anchor="mm",
        align="center",
        direction="rtl",
        language="ar",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill
    )


def create_text_overlay(verse):

    font_path = find_font()

    overlay = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    draw = ImageDraw.Draw(
        overlay
    )

    title_font = ImageFont.truetype(
        font_path,
        54
    )

    footer_font = ImageFont.truetype(
        font_path,
        38
    )

    (
        verse_font,
        verse_lines,
        line_height
    ) = fit_verse_text(
        draw,
        verse["text"],
        font_path
    )

    panel_left = 60
    panel_top = 300
    panel_right = WIDTH - 60
    panel_bottom = 1585

    draw.rounded_rectangle(
        (
            panel_left,
            panel_top,
            panel_right,
            panel_bottom
        ),
        radius=60,
        fill=(
            1,
            13,
            20,
            185
        ),
        outline=(
            232,
            202,
            124,
            220
        ),
        width=4
    )

    draw.rounded_rectangle(
        (
            panel_left + 16,
            panel_top + 16,
            panel_right - 16,
            panel_bottom - 16
        ),
        radius=48,
        outline=(
            255,
            239,
            185,
            70
        ),
        width=2
    )

    center_x = WIDTH // 2

    title = (
        f"سورة {verse['surah']} "
        f"• الآية {verse['ayah']}"
    )

    draw_centered_rtl(
        draw,
        center_x,
        420,
        title,
        title_font,
        LIGHT_GOLD,
        stroke_width=1,
        stroke_fill=(
            30,
            20,
            5
        )
    )

    ornament_y = 510

    draw.line(
        (
            280,
            ornament_y,
            800,
            ornament_y
        ),
        fill=(
            232,
            202,
            124,
            150
        ),
        width=2
    )

    draw.ellipse(
        (
            center_x - 8,
            ornament_y - 8,
            center_x + 8,
            ornament_y + 8
        ),
        fill=(
            255,
            235,
            170,
            240
        )
    )

    total_text_height = (
        len(verse_lines)
        *
        line_height
    )

    available_height = 730

    start_y = (
        575
        +
        max(
            0,
            (
                available_height
                -
                total_text_height
            ) // 2
        )
    )

    for index, line in enumerate(
        verse_lines
    ):

        line_y = (
            start_y
            +
            index * line_height
            +
            line_height // 2
        )

        draw_centered_rtl(
            draw,
            center_x,
            line_y,
            line,
            verse_font,
            WHITE,
            stroke_width=2,
            stroke_fill=(
                0,
                0,
                0
            )
        )

    draw_centered_rtl(
        draw,
        center_x,
        1470,
        "القرآن الكريم",
        footer_font,
        SOFT_WHITE
    )

    return overlay


def create_particles(
    count=32
):

    random.seed(2026)

    particles = []

    for _ in range(count):

        particles.append(
            {
                "x": random.uniform(
                    0,
                    WIDTH
                ),
                "y": random.uniform(
                    0,
                    HEIGHT
                ),
                "radius": random.uniform(
                    1.2,
                    4.0
                ),
                "speed": random.uniform(
                    12,
                    32
                ),
                "phase": random.uniform(
                    0,
                    math.tau
                ),
                "alpha": random.randint(
                    45,
                    135
                )
            }
        )

    return particles


def render_particles(
    time_value,
    particles
):

    layer = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    draw = ImageDraw.Draw(
        layer
    )

    for particle in particles:

        particle_y = (
            particle["y"]
            -
            time_value
            *
            particle["speed"]
        ) % (HEIGHT + 100) - 50

        particle_x = (
            particle["x"]
            +
            math.sin(
                time_value * 0.7
                +
                particle["phase"]
            ) * 18
        )

        pulse = (
            0.60
            +
            0.40
            *
            math.sin(
                time_value * 1.25
                +
                particle["phase"]
            )
        )

        alpha = int(
            particle["alpha"]
            *
            max(
                0.15,
                pulse
            )
        )

        radius = particle["radius"]

        draw.ellipse(
            (
                particle_x - radius,
                particle_y - radius,
                particle_x + radius,
                particle_y + radius
            ),
            fill=(
                255,
                232,
                165,
                alpha
            )
        )

    return layer.filter(
        ImageFilter.GaussianBlur(
            1.1
        )
    )


def render_light_glow(
    time_value
):

    layer = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    draw = ImageDraw.Draw(
        layer
    )

    glow_x = (
        WIDTH * 0.5
        +
        math.sin(
            time_value * 0.22
        ) * 145
    )

    glow_y = (
        HEIGHT * 0.15
        +
        math.cos(
            time_value * 0.18
        ) * 50
    )

    radius = int(
        320
        +
        math.sin(
            time_value * 0.65
        ) * 35
    )

    draw.ellipse(
        (
            glow_x - radius,
            glow_y - radius,
            glow_x + radius,
            glow_y + radius
        ),
        fill=(
            255,
            224,
            150,
            45
        )
    )

    return layer.filter(
        ImageFilter.GaussianBlur(
            115
        )
    )


def create_background_frame(
    time_value,
    duration,
    source_background,
    gradient_background
):

    if source_background is None:

        shift_x = int(
            math.sin(
                time_value * 0.22
            ) * 24
        )

        shifted = np.roll(
            gradient_background,
            shift_x,
            axis=1
        )

        return Image.fromarray(
            shifted
        ).convert("RGBA")

    progress = (
        time_value
        /
        max(
            duration,
            0.001
        )
    )

    zoom = (
        1.05
        +
        progress * 0.08
    )

    zoom_width = int(
        WIDTH * zoom
    )

    zoom_height = int(
        HEIGHT * zoom
    )

    enlarged = cover_image(
        source_background,
        zoom_width,
        zoom_height
    )

    max_x = max(
        0,
        zoom_width - WIDTH
    )

    max_y = max(
        0,
        zoom_height - HEIGHT
    )

    crop_x = int(
        max_x
        *
        (
            0.5
            +
            0.25
            *
            math.sin(
                progress
                *
                math.pi
            )
        )
    )

    crop_y = int(
        max_y
        *
        (
            0.5
            +
            0.20
            *
            math.cos(
                progress
                *
                math.pi
            )
        )
    )

    crop_x = max(
        0,
        min(
            crop_x,
            max_x
        )
    )

    crop_y = max(
        0,
        min(
            crop_y,
            max_y
        )
    )

    return enlarged.crop(
        (
            crop_x,
            crop_y,
            crop_x + WIDTH,
            crop_y + HEIGHT
        )
    ).convert("RGBA")


def apply_overlay_animation(
    overlay,
    time_value,
    duration
):

    fade_in = min(
        1.0,
        max(
            0.0,
            time_value / 1.2
        )
    )

    fade_out = min(
        1.0,
        max(
            0.0,
            (
                duration
                -
                time_value
            ) / 0.8
        )
    )

    opacity = min(
        fade_in,
        fade_out
    )

    animated_overlay = overlay.copy()

    alpha_channel = (
        animated_overlay
        .getchannel("A")
    )

    alpha_channel = alpha_channel.point(
        lambda value: int(
            value * opacity
        )
    )

    animated_overlay.putalpha(
        alpha_channel
    )

    offset_y = int(
        (
            1.0
            -
            fade_in
        ) * 34
    )

    if offset_y == 0:
        return animated_overlay

    moved_overlay = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    moved_overlay.alpha_composite(
        animated_overlay,
        (
            0,
            offset_y
        )
    )

    return moved_overlay


def create_vignette():

    y_grid, x_grid = np.ogrid[
        -1.0:1.0:complex(
            0,
            HEIGHT
        ),
        -1.0:1.0:complex(
            0,
            WIDTH
        )
    ]

    distance = np.sqrt(
        x_grid * x_grid
        +
        y_grid * y_grid
    )

    vignette = np.clip(
        1.12
        -
        distance * 0.36,
        0.60,
        1.0
    )

    return vignette[
        :,
        :,
        None
    ]


def save_metadata(
    verse,
    seo
):

    with open(
        os.path.join(
            OUTPUT_FOLDER,
            "title.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            seo["title"]
        )

    with open(
        os.path.join(
            OUTPUT_FOLDER,
            "description.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            seo["description"]
        )

    with open(
        os.path.join(
            OUTPUT_FOLDER,
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
            OUTPUT_FOLDER,
            "verse.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            verse["text"]
        )


def build_video(
    verse,
    seo
):

    prepare_folders()

    save_metadata(
        verse,
        seo
    )

    audio_path = get_audio(
        verse
    )

    audio_clip = AudioFileClip(
        audio_path
    )

    duration = max(
        MIN_DURATION,
        min(
            float(
                audio_clip.duration
            ),
            MAX_DURATION
        )
    )

    if audio_clip.duration > duration:

        audio_clip = (
            audio_clip
            .subclipped(
                0,
                duration
            )
        )

    print(
        "Font:",
        find_font()
    )

    print(
        "Audio:",
        audio_path
    )

    print(
        "Duration:",
        round(
            duration,
            2
        )
    )

    print(
        "Resolution:",
        f"{WIDTH}x{HEIGHT}"
    )

    source_background = (
        load_background_image()
    )

    gradient_background = (
        create_gradient_background()
    )

    text_overlay = create_text_overlay(
        verse
    )

    particles = create_particles()
    vignette = create_vignette()

    def make_frame(
        time_value
    ):

        background = create_background_frame(
            time_value,
            duration,
            source_background,
            gradient_background
        )

        glow_layer = render_light_glow(
            time_value
        )

        particle_layer = render_particles(
            time_value,
            particles
        )

        frame = Image.alpha_composite(
            background,
     
