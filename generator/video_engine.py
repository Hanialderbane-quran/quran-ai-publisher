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
            glow_layer
        )

        frame = Image.alpha_composite(
            frame,
            particle_layer
        )

        animated_text = (
            apply_overlay_animation(
                text_overlay,
                time_value,
                duration
            )
        )

        frame = Image.alpha_composite(
            frame,
            animated_text
        )

        frame_array = np.asarray(
            frame.convert("RGB")
        ).astype(np.float32)

        frame_array *= vignette

        frame_array = np.clip(
            frame_array,
            0,
            255
        ).astype(np.uint8)

        return frame_array

    preview_time = min(
        1.5,
        duration / 2
    )

    preview_frame = make_frame(
        preview_time
    )

    Image.fromarray(
        preview_frame
    ).save(
        PREVIEW_PATH
    )

    video_clip = VideoClip(
        frame_function=make_frame,
        duration=duration
    )

    video_clip = video_clip.with_audio(
        audio_clip
    )

    print()
    print(
        "Rendering professional video..."
    )

    video_clip.write_videofile(
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

    video_clip.close()
    audio_clip.close()

    if not os.path.isfile(
        VIDEO_PATH
    ):

        raise RuntimeError(
            "The video was not created."
        )

    if os.path.getsize(
        VIDEO_PATH
    ) < 10000:

        raise RuntimeError(
            "The generated video is empty."
        )

    print()
    print(
        "Video created successfully:",
        VIDEO_PATH
    )

    return VIDEO_PATH    new_width = math.ceil(source_width * scale)
    new_height = math.ceil(source_height * scale)

    image = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    left = max(0, (new_width - target_width) // 2)
    top = max(0, (new_height - target_height) // 2)

    return image.crop(
        (
            left,
            top,
            left + target_width,
            top + target_height
        )
    )


def load_background_image():

    background_path = find_background()

    if background_path is None:
        return None

    image = Image.open(background_path).convert("RGB")

    image = ImageEnhance.Color(image).enhance(0.75)
    image = ImageEnhance.Contrast(image).enhance(1.12)
    image = ImageEnhance.Brightness(image).enhance(0.72)

    print("Background:", background_path)

    return image


def create_procedural_background():

    y = np.linspace(
        0.0,
        1.0,
        HEIGHT,
        dtype=np.float32
    )[:, None]

    top = np.array(
        [13, 57, 67],
        dtype=np.float32
    )

    middle = np.array(
        [8, 37, 50],
        dtype=np.float32
    )

    bottom = np.array(
        [2, 12, 23],
        dtype=np.float32
    )

    first_half = np.clip(y * 2.0, 0.0, 1.0)
    second_half = np.clip((y - 0.5) * 2.0, 0.0, 1.0)

    gradient_top = (
        top[None, None, :]
        * (1.0 - first_half[:, :, None])
        +
        middle[None, None, :]
        * first_half[:, :, None]
    )

    gradient_bottom = (
        middle[None, None, :]
        * (1.0 - second_half[:, :, None])
        +
        bottom[None, None, :]
        * second_half[:, :, None]
    )

    use_bottom = (y >= 0.5)[:, :, None]

    gradient = np.where(
        use_bottom,
        gradient_bottom,
        gradient_top
    )

    gradient = np.repeat(
        gradient,
        WIDTH,
        axis=1
    )

    return np.clip(
        gradient,
        0,
        255
    ).astype(np.uint8)


def wrap_rtl_text(draw, text, font, max_width):

    words = text.split()

    lines = []
    current_words = []

    for word in words:

        test_words = current_words + [word]
        test_line = " ".join(test_words)

        box = draw.textbbox(
            (0, 0),
            test_line,
            font=font,
            direction="rtl",
            language="ar"
        )

        line_width = box[2] - box[0]

        if line_width <= max_width:
            current_words.append(word)

        else:

            if current_words:
                lines.append(" ".join(current_words))

            current_words = [word]

    if current_words:
        lines.append(" ".join(current_words))

    return lines


def fit_verse_font(draw, verse_text, font_path):

    max_width = WIDTH - 210
    max_height = 790

    for font_size in range(82, 43, -2):

        font = ImageFont.truetype(
            font_path,
            font_size
        )

        lines = wrap_rtl_text(
            draw,
            verse_text,
            font,
            max_width
        )

        line_height = int(font_size * 1.65)
        total_height = len(lines) * line_height

        if (
            len(lines) <= 8
            and total_height <= max_height
        ):
            return font, lines, line_height

    font = ImageFont.truetype(
        font_path,
        44
    )

    lines = wrap_rtl_text(
        draw,
        verse_text,
        font,
        max_width
    )

    return font, lines, 73


def draw_centered_rtl(
    draw,
    position,
    text,
    font,
    fill,
    stroke_width=0,
    stroke_fill=None
):

    draw.text(
        position,
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
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    title_font = ImageFont.truetype(
        font_path,
        55
    )

    footer_font = ImageFont.truetype(
        font_path,
        38
    )

    verse_font, lines, line_height = fit_verse_font(
        draw,
        verse["text"],
        font_path
    )

    panel_left = 62
    panel_top = 315
    panel_right = WIDTH - 62
    panel_bottom = 1580

    draw.rounded_rectangle(
        (
            panel_left,
            panel_top,
            panel_right,
            panel_bottom
        ),
        radius=58,
        fill=(3, 15, 21, 178),
        outline=(232, 202, 124, 205),
        width=3
    )

    draw.rounded_rectangle(
        (
            panel_left + 15,
            panel_top + 15,
            panel_right - 15,
            panel_bottom - 15
        ),
        radius=48,
        outline=(255, 240, 190, 65),
        width=2
    )

    center_x = WIDTH // 2

    title = (
        f"سورة {verse['surah']} "
        f"• الآية {verse['ayah']}"
    )

    draw_centered_rtl(
        draw,
        (center_x, 420),
        title,
        title_font,
        LIGHT_GOLD,
        stroke_width=1,
        stroke_fill=(40, 30, 10, 180)
    )

    ornament_y = 500

    draw.line(
        (290, ornament_y, 790, ornament_y),
        fill=(232, 202, 124, 130),
        width=2
    )

    draw.ellipse(
        (
            center_x - 7,
            ornament_y - 7,
            center_x + 7,
            ornament_y + 7
        ),
        fill=(255, 232, 160, 230)
    )

    total_text_height = (
        len(lines) * line_height
    )

    start_y = (
        590
        +
        max(
            0,
            (700 - total_text_height) // 2
        )
    )

    for index, line in enumerate(lines):

        line_y = (
            start_y
            +
            index * line_height
            +
            line_height // 2
        )

        draw_centered_rtl(
            draw,
            (center_x, line_y),
            line,
            verse_font,
            WHITE,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 125)
        )

    footer = "القرآن الكريم"

    draw_centered_rtl(
        draw,
        (center_x, 1465),
        footer,
        footer_font,
        SOFT_WHITE
    )

    return overlay


def create_vignette():

    y, x = np.ogrid[
        -1.0:1.0:complex(0, HEIGHT),
        -1.0:1.0:complex(0, WIDTH)
    ]

    distance = np.sqrt(
        x * x
        +
        y * y
    )

    vignette = np.clip(
        1.13 - distance * 0.38,
        0.58,
        1.0
    )

    return vignette[:, :, None]


def create_particles(count=34):

    random.seed(2026)

    particles = []

    for _ in range(count):

        particles.append(
            {
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, HEIGHT),
                "radius": random.uniform(1.2, 4.5),
                "speed": random.uniform(10, 35),
                "phase": random.uniform(0, math.tau),
                "alpha": random.randint(45, 145)
            }
        )

    return particles


def render_particles(time_value, particles):

    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

    for particle in particles:

        particle_y = (
            particle["y"]
            -
            time_value * particle["speed"]
        ) % (HEIGHT + 100) - 50

        sway = math.sin(
            time_value * 0.65
            +
            particle["phase"]
        ) * 18

        particle_x = particle["x"] + sway

        pulse = (
            0.58
            +
            0.42
            * math.sin(
                time_value * 1.2
                +
                particle["phase"]
            )
        )

        alpha = int(
            particle["alpha"]
            *
            max(0.15, pulse)
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
                231,
                160,
                alpha
            )
        )

    return layer.filter(
        ImageFilter.GaussianBlur(1.2)
    )


def render_light_glow(time_value):

    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

    glow_x = (
        WIDTH * 0.5
        +
        math.sin(time_value * 0.19)
        * WIDTH * 0.15
    )

    glow_y = (
        HEIGHT * 0.17
        +
        math.cos(time_value * 0.15)
        * 60
    )

    pulse = (
        0.82
        +
        0.18
        * math.sin(time_value * 0.7)
    )

    radius = int(330 * pulse)

    draw.ellipse(
        (
            glow_x - radius,
            glow_y - radius,
            glow_x + radius,
            glow_y + radius
        ),
        fill=(255, 224, 150, 42)
    )

    return layer.filter(
        ImageFilter.GaussianBlur(115)
    )


def create_background_frame(
    time_value,
    duration,
    source_background,
    procedural_background
):

    if source_background is None:

        base = Image.fromarray(
            procedural_background.copy()
        ).convert("RGB")

        shift = int(
            math.sin(time_value * 0.18)
            * 22
        )

        base = Image.fromarray(
            np.roll(
                np.asarray(base),
                shift,
                axis=1
            )
        )

        return base

    progress = (
        time_value
        /
        max(duration, 0.001)
    )

    zoom = 1.05 + progress * 0.075

    target_width = int(WIDTH * zoom)
    target_height = int(HEIGHT * zoom)

    frame = cover_image(
        source_background,
        target_width,
        target_height
    )

    max_x = target_width - WIDTH
    max_y = target_height - HEIGHT

    crop_x = int(
        max_x
        *
        (
            0.5
            +
            0.32
            * math.sin(
                progress * math.pi
            )
        )
    )

    crop_y = int(
        max_y
        *
        (
            0.45
            +
            0.25
            * math.cos(
                progress * math.pi
            )
        )
    )

    crop_x = max(
        0,
        min(crop_x, max_x)
    )

    crop_y = max(
        0,
        min(crop_y, max_y)
    )

    return frame.crop(
        (
            crop_x,
            crop_y,
            crop_x + WIDTH,
            crop_y + HEIGHT
        )
    )


def apply_fade(overlay, time_value, duration):

    fade_in = min(
        1.0,
        max(0.0, time_value / 1.15)
    )

    fade_out = min(
        1.0,
        max(
            0.0,
            (duration - time_value) / 0.85
        )
    )

    opacity = min(
        fade_in,
        fade_out
    )

    animated_overlay = overlay.copy()

    alpha = animated_overlay.getchannel("A")

    alpha = alpha.point(
        lambda value: int(
            value * opacity
        )
    )

    animated_overlay.putalpha(alpha)

    vertical_offset = int(
        (1.0 - fade_in) * 35
    )

    return animated_overlay, vertical_offset


def save_metadata(verse, seo):

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


def build_video(verse, seo):

    prepare_folders()
    save_metadata(verse, seo)

    audio_path = get_audio(verse)

    audio_clip = AudioFileClip(
        audio_path
    )

    duration = float(
        audio_clip.duration
    )

    duration = max(
        MIN_DURATION,
        min(duration, MAX_DURATION)
    )

    if audio_clip.duration > duration:

        audio_clip = audio_clip.subclipped(
            0,
            duration
        )

    font_path = find_font()

    print("Font:", font_path)
    print("Duration:", round(duration, 2))
    print("Resolution:", f"{WIDTH}x{HEIGHT}")
    print("FPS:", FPS)

    source_background = load_background_image()

    procedural_background = (
        create_procedural_background()
    )

    text_overlay = create_text_overlay(
        verse
    )

    vignette = create_vignette()
    particles = create_particles()

    def make_frame(time_value):

        background = create_background_frame(
            time_value,
            duration,
            source_background,
            procedural_background
        ).convert("RGBA")

        light_layer = render_light_glow(
            time_value
        )

        particle_layer = render_particles(
            time_value,
            particles
        )

        frame = Image.alpha_composite(
            background,
            light_layer
        )

        frame = Image.alpha_composite(
            frame,
            particle_layer
        )

        animated_overlay, offset_y = apply_fade(
            text_overlay,
            time_value,
            duration
        )

        if offset_y != 0:

            moved_overlay = Image.new(
                "RGBA",
                (WIDTH, HEIGHT),
                (0, 0, 0, 0)
            )

            moved_overlay.alpha_composite(
                animated_overlay,
                (0, offset_y)
            )

            animated_overlay = moved_overlay

        frame = Image.alpha_composite(
            frame,
            animated_overlay
        )

        frame_array = np.asarray(
            frame.convert("RGB")
        ).astype(np.float32)

        frame_array = (
            frame_array
            *
            vignette
        )

        frame_array = np.clip(
            frame_array,
            0,
            255
        ).astype(np.uint8)

        return frame_array

    preview_frame = make_frame(
        min(1.5, duration / 2)
    )

    Image.fromarray(
        preview_frame
    ).save(
        PREVIEW_PATH,
        quality=95
    )

    video_clip = VideoClip(
        frame_function=make_frame,
        duration=duration
    )

    video_clip = video_clip.with_audio(
        audio_clip
    )

    print()
    print("Rendering professional video...")

    video_clip.write_videofile(
        VIDEO_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        bitrate="5500k",
        preset="medium",
        threads=2,
        pixel_format="yuv420p",
        logger="bar"
    )

    video_clip.close()
    audio_clip.close()

    if not os.path.isfile(VIDEO_PATH):

        raise RuntimeError(
            "The video was not created."
        )

    if os.path.getsize(VIDEO_PATH) < 10000:

        raise RuntimeError(
            "The generated video is too small."
        )

    print()
    print("Video created successfully:")
    print(VIDEO_PATH)

    return VIDEO_PATH    image = create_gradient_background()
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (70, 330, WIDTH - 70, 1560),
        radius=55,
        fill=(0, 0, 0, 135),
        outline=(220, 190, 105),
        width=4
    )

    surah_title = prepare_arabic(
        f"سورة {verse['surah']} - الآية {verse['ayah']}"
    )

    draw_centered_text(
        draw,
        surah_title,
        title_font,
        420,
        (235, 207, 126)
    )

    lines = wrap_arabic_text(verse["text"], max_chars=23)

    line_height = 105
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2

    for line in lines:
        display_line = prepare_arabic(line)

        draw_centered_text(
            draw,
            display_line,
            verse_font,
            start_y,
            (255, 255, 255)
        )

        start_y += line_height

    footer = prepare_arabic("القرآن الكريم")

    draw_centered_text(
        draw,
        footer,
        footer_font,
        1450,
        (215, 215, 215)
    )

    image.save(FRAME_PATH)

    return FRAME_PATH


def save_files(verse, seo):
    with open(
        os.path.join(OUTPUT_FOLDER, "title.txt"),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(seo["title"])

    with open(
        os.path.join(OUTPUT_FOLDER, "description.txt"),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(seo["description"])

    with open(
        os.path.join(OUTPUT_FOLDER, "tags.json"),
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(seo["tags"], file, ensure_ascii=False, indent=2)

    with open(
        os.path.join(OUTPUT_FOLDER, "verse.txt"),
        "w",
        encoding="utf-8"
    ) as file:
        file.write(verse["text"])


def build_video(verse, seo):
    prepare_output()
    save_files(verse, seo)

    print("Creating video frame...")

    frame_path = create_video_frame(verse)

    print("Rendering MP4 video...")

    clip = ImageClip(frame_path, duration=DURATION)

    clip.write_videofile(
        VIDEO_PATH,
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=2,
        logger="bar"
    )

    clip.close()

    if not os.path.exists(VIDEO_PATH):
        raise RuntimeError("Video creation failed.")

    if os.path.getsize(VIDEO_PATH) == 0:
        raise RuntimeError("Video file is empty.")

    print("Video created successfully:", VIDEO_PATH)

    return VIDEO_PATH
