"""
Quran AI Publisher
Respectful Quran Video Engine
Version 8.0

Creates Quran Shorts and long videos.
Displays consecutive ayahs one at a time.
Uses only calm, respectful movement.
"""

import json
import math
import os
import random
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont
)

from generator.audio_engine import get_segment_audio


OUTPUT_DIR = Path("output")
BACKGROUND_DIR = Path("assets/backgrounds")
FONT_DIR = Path("assets/fonts")

FPS = 24
MINIMUM_VIDEO_SIZE = 10000


def ensure_folders() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    BACKGROUND_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    FONT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def get_video_dimensions(
    segment: dict
) -> tuple[int, int]:
    video_type = segment.get(
        "video_type",
        "short"
    )

    if video_type == "long":
        return 1920, 1080

    return 1080, 1920


def get_output_paths(
    segment: dict
) -> tuple[Path, Path]:
    segment_id = str(
        segment.get(
            "segment_id",
            "quran_video"
        )
    )

    video_path = OUTPUT_DIR / (
        f"{segment_id}.mp4"
    )

    preview_path = OUTPUT_DIR / (
        f"{segment_id}_preview.png"
    )

    return video_path, preview_path


def find_font() -> str:
    candidates = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        FONT_DIR / "arabic.ttf",

        Path(
            "/usr/share/fonts/truetype/noto/"
            "NotoNaskhArabic-Bold.ttf"
        ),

        Path(
            "/usr/share/fonts/truetype/noto/"
            "NotoNaskhArabic-Regular.ttf"
        ),

        Path(
            "/usr/share/fonts/opentype/noto/"
            "NotoNaskhArabic-Bold.ttf"
        ),

        Path(
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf"
        )
    ]

    for path in candidates:
        if path.is_file():
            return str(path)

    raise RuntimeError(
        "No Arabic font was found."
    )


def find_backgrounds() -> list[Path]:
    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }

    files = []

    if not BACKGROUND_DIR.exists():
        return files

    for path in BACKGROUND_DIR.iterdir():
        if (
            path.is_file()
            and path.suffix.lower()
            in allowed_extensions
        ):
            files.append(path)

    return files


def choose_background() -> Path | None:
    files = find_backgrounds()

    if not files:
        return None

    return random.choice(files)


def cover_image(
    image: Image.Image,
    width: int,
    height: int
) -> Image.Image:
    scale = max(
        width / image.width,
        height / image.height
    )

    resized_width = math.ceil(
        image.width * scale
    )

    resized_height = math.ceil(
        image.height * scale
    )

    image = image.resize(
        (
            resized_width,
            resized_height
        ),
        Image.Resampling.LANCZOS
    )

    left = max(
        0,
        (
            resized_width
            - width
        ) // 2
    )

    top = max(
        0,
        (
            resized_height
            - height
        ) // 2
    )

    return image.crop(
        (
            left,
            top,
            left + width,
            top + height
        )
    )


def load_background() -> Image.Image | None:
    path = choose_background()

    if path is None:
        print(
            "Background: calm automatic gradient"
        )

        return None

    try:
        image = Image.open(
            path
        ).convert("RGB")

        image = ImageEnhance.Brightness(
            image
        ).enhance(0.66)

        image = ImageEnhance.Contrast(
            image
        ).enhance(1.08)

        image = ImageEnhance.Color(
            image
        ).enhance(0.72)

        print(
            "Background:",
            path
        )

        return image

    except OSError as error:
        raise RuntimeError(
            f"Could not open background: {path}"
        ) from error


def make_gradient(
    width: int,
    height: int
) -> np.ndarray:
    top_color = np.array(
        [15, 58, 67],
        dtype=np.float32
    )

    bottom_color = np.array(
        [2, 9, 18],
        dtype=np.float32
    )

    vertical = np.linspace(
        0,
        1,
        height,
        dtype=np.float32
    )[:, None, None]

    gradient = (
        top_color[None, None, :]
        * (1 - vertical)
        +
        bottom_color[None, None, :]
        * vertical
    )

    return np.repeat(
        gradient,
        width,
        axis=1
    ).astype(np.uint8)


def create_background_frame(
    time_value: float,
    duration: float,
    source: Image.Image | None,
    gradient: np.ndarray,
    width: int,
    height: int
) -> Image.Image:
    if source is None:
        shift = int(
            math.sin(
                time_value * 0.10
            ) * 12
        )

        shifted = np.roll(
            gradient,
            shift,
            axis=1
        )

        return Image.fromarray(
            shifted
        ).convert("RGBA")

    progress = time_value / max(
        duration,
        0.001
    )

    zoom = (
        1.04
        +
        progress * 0.045
    )

    render_width = int(
        width * zoom
    )

    render_height = int(
        height * zoom
    )

    image = cover_image(
        source,
        render_width,
        render_height
    )

    available_x = max(
        0,
        render_width - width
    )

    available_y = max(
        0,
        render_height - height
    )

    x = int(
        available_x
        * (
            0.50
            +
            0.12
            * math.sin(
                progress * math.pi
            )
        )
    )

    y = int(
        available_y
        * (
            0.50
            +
            0.10
            * math.cos(
                progress * math.pi
            )
        )
    )

    return image.crop(
        (
            x,
            y,
            x + width,
            y + height
        )
    ).convert("RGBA")


def create_soft_light(
    time_value: float,
    width: int,
    height: int
) -> Image.Image:
    layer = Image.new(
        "RGBA",
        (
            width,
            height
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

    center_x = (
        width * 0.50
        +
        math.sin(
            time_value * 0.12
        )
        * width * 0.06
    )

    center_y = (
        height * 0.15
        +
        math.cos(
            time_value * 0.10
        )
        * height * 0.025
    )

    radius = int(
        min(
            width,
            height
        ) * 0.36
    )

    draw.ellipse(
        (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius
        ),
        fill=(
            255,
            229,
            165,
            38
        )
    )

    return layer.filter(
        ImageFilter.GaussianBlur(
            max(
                60,
                radius // 3
            )
        )
    )


def text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont
) -> int:
    box = draw.textbbox(
        (
            0,
            0
        ),
        text,
        font=font,
        direction="rtl",
        language="ar"
    )

    return box[2] - box[0]


def wrap_arabic_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    maximum_width: int
) -> list[str]:
    lines = []
    current_words = []

    for word in text.split():
        candidate = " ".join(
            current_words + [word]
        )

        if text_width(
            draw,
            candidate,
            font
        ) <= maximum_width:
            current_words.append(
                word
            )

        else:
            if current_words:
                lines.append(
                    " ".join(
                        current_words
                    )
                )

            current_words = [
                word
            ]

    if current_words:
        lines.append(
            " ".join(
                current_words
            )
        )

    return lines


def fit_ayah_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    maximum_width: int,
    maximum_height: int,
    maximum_size: int,
    minimum_size: int
) -> tuple:
    for font_size in range(
        maximum_size,
        minimum_size - 1,
        -2
    ):
        font = ImageFont.truetype(
            font_path,
            font_size
        )

        lines = wrap_arabic_text(
            draw,
            text,
            font,
            maximum_width
        )

        line_height = int(
            font_size * 1.55
        )

        total_height = (
            len(lines)
            * line_height
        )

        if (
            len(lines) <= 10
            and total_height
            <= maximum_height
        ):
            return (
                font,
                lines,
                line_height
            )

    font = ImageFont.truetype(
        font_path,
        minimum_size
    )

    lines = wrap_arabic_text(
        draw,
        text,
        font,
        maximum_width
    )

    return (
        font,
        lines,
        int(
            minimum_size * 1.55
        )
    )


def draw_arabic(
    draw: ImageDraw.ImageDraw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    stroke_width: int = 0
) -> None:
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
        stroke_fill=(
            0,
            0,
            0
        )
    )


def create_ayah_layer(
    ayah: dict,
    segment: dict,
    width: int,
    height: int
) -> Image.Image:
    font_path = find_font()

    layer = Image.new(
        "RGBA",
        (
            width,
            height
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

    is_long = (
        segment.get(
            "video_type"
        )
        == "long"
    )

    if is_long:
        panel_left = int(
            width * 0.12
        )

        panel_right = int(
            width * 0.88
        )

        panel_top = int(
            height * 0.17
        )

        panel_bottom = int(
            height * 0.83
        )

        title_size = 44
        footer_size = 30
        maximum_text_size = 66
        minimum_text_size = 38

    else:
        panel_left = int(
            width * 0.06
        )

        panel_right = int(
            width * 0.94
        )

        panel_top = int(
            height * 0.16
        )

        panel_bottom = int(
            height * 0.84
        )

        title_size = 54
        footer_size = 36
        maximum_text_size = 82
        minimum_text_size = 42

    panel_width = (
        panel_right
        - panel_left
    )

    panel_height = (
        panel_bottom
        - panel_top
    )

    radius = int(
        min(
            width,
            height
        ) * 0.035
    )

    draw.rounded_rectangle(
        (
            panel_left,
            panel_top,
            panel_right,
            panel_bottom
        ),
        radius=radius,
        fill=(
            2,
            15,
            23,
            196
        ),
        outline=(
            232,
            202,
            124,
            225
        ),
        width=4
    )

    inner_margin = int(
        min(
            width,
            height
        ) * 0.014
    )

    draw.rounded_rectangle(
        (
            panel_left
            + inner_margin,
            panel_top
            + inner_margin,
            panel_right
            - inner_margin,
            panel_bottom
            - inner_margin
        ),
        radius=max(
            12,
            radius - 10
        ),
        outline=(
            255,
            239,
            185,
            55
        ),
        width=2
    )

    title_font = ImageFont.truetype(
        font_path,
        title_size
    )

    footer_font = ImageFont.truetype(
        font_path,
        footer_size
    )

    title = (
        f"سورة {ayah['surah']} "
        f"• الآية {ayah['ayah']}"
    )

    title_y = (
        panel_top
        +
        int(
            panel_height * 0.11
        )
    )

    draw_arabic(
        draw,
        (
            width // 2,
            title_y
        ),
        title,
        title_font,
        (
            255,
            235,
            180
        ),
        1
    )

    separator_y = (
        panel_top
        +
        int(
            panel_height * 0.19
        )
    )

    draw.line(
        (
            panel_left
            + panel_width * 0.24,
            separator_y,
            panel_right
            - panel_width * 0.24,
            separator_y
        ),
        fill=(
            232,
            202,
            124,
            145
        ),
        width=2
    )

    text_area_top = (
        panel_top
        +
        int(
            panel_height * 0.25
        )
    )

    text_area_bottom = (
        panel_bottom
        -
        int(
            panel_height * 0.17
        )
    )

    maximum_text_width = int(
        panel_width * 0.82
    )

    maximum_text_height = (
        text_area_bottom
        - text_area_top
    )

    ayah_font, lines, line_height = (
        fit_ayah_text(
            draw=draw,
            text=ayah["text"],
            font_path=font_path,
            maximum_width=maximum_text_width,
            maximum_height=maximum_text_height,
            maximum_size=maximum_text_size,
            minimum_size=minimum_text_size
        )
    )

    total_text_height = (
        len(lines)
        * line_height
    )

    first_line_y = (
        text_area_top
        +
        max(
            0,
            (
                maximum_text_height
                - total_text_height
            ) // 2
        )
        +
        line_height // 2
    )

    for index, line in enumerate(
        lines
    ):
        y = (
            first_line_y
            +
            index
            * line_height
        )

        draw_arabic(
            draw,
            (
                width // 2,
                y
            ),
            line,
            ayah_font,
            (
                255,
                255,
                255
            ),
            2
        )

    footer_y = (
        panel_bottom
        -
        int(
            panel_height * 0.08
        )
    )

    draw_arabic(
        draw,
        (
            width // 2,
            footer_y
        ),
        "القرآن الكريم",
        footer_font,
        (
            220,
            230,
            232
        )
    )

    return layer


def estimate_ayah_weight(
    ayah: dict
) -> float:
    word_count = len(
        ayah.get(
            "text",
            ""
        ).split()
    )

    return max(
        2.5,
        word_count * 0.55
    )


def create_ayah_timeline(
    segment: dict,
    audio_duration: float
) -> list[dict]:
    ayahs = segment.get(
        "ayahs",
        []
    )

    if not ayahs:
        raise RuntimeError(
            "The Quran segment has no ayahs."
        )

    weights = [
        estimate_ayah_weight(
            ayah
        )
        for ayah in ayahs
    ]

    total_weight = sum(
        weights
    )

    if total_weight <= 0:
        raise RuntimeError(
            "Could not calculate ayah timings."
        )

    timeline = []
    current_time = 0.0

    for index, ayah in enumerate(
        ayahs
    ):
        if index == len(ayahs) - 1:
            end_time = audio_duration

        else:
            ayah_duration = (
                audio_duration
                * weights[index]
                / total_weight
            )

            end_time = (
                current_time
                + ayah_duration
            )

        timeline.append(
            {
                "ayah": ayah,
                "start": current_time,
                "end": end_time
            }
        )

        current_time = end_time

    return timeline


def get_active_ayah(
    timeline: list[dict],
    time_value: float
) -> tuple[int, dict]:
    for index, item in enumerate(
        timeline
    ):
        if (
            item["start"]
            <= time_value
            < item["end"]
        ):
            return index, item

    return (
        len(timeline) - 1,
        timeline[-1]
    )


def animate_ayah_layer(
    layer: Image.Image,
    local_time: float,
    ayah_duration: float,
    width: int,
    height: int
) -> Image.Image:
    fade_duration = min(
        0.75,
        max(
            0.20,
            ayah_duration * 0.15
        )
    )

    fade_in = min(
        1.0,
        max(
            0.0,
            local_time
            / fade_duration
        )
    )

    remaining = (
        ayah_duration
        - local_time
    )

    fade_out = min(
        1.0,
        max(
            0.0,
            remaining
            / fade_duration
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

    animated.putalpha(
        alpha
    )

    movement_limit = int(
        height * 0.012
    )

    vertical_offset = int(
        (
            1.0
            - fade_in
        )
        * movement_limit
    )

    if vertical_offset == 0:
        return animated

    moved = Image.new(
        "RGBA",
        (
            width,
            height
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    moved.alpha_composite(
        animated,
        (
            0,
            vertical_offset
        )
    )

    return moved


def save_metadata(
    segment: dict,
    seo: dict,
    video_path: Path,
    preview_path: Path
) -> None:
    files = {
        "title.txt": seo["title"],
        "description.txt": seo["description"],
        "segment_text.txt": segment["text"]
    }

    for filename, content in files.items():
        with (
            OUTPUT_DIR
            / filename
        ).open(
            "w",
            encoding="utf-8"
        ) as file:
            file.write(
                str(content)
            )

    with (
        OUTPUT_DIR
        / "tags.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            seo["tags"],
            file,
            ensure_ascii=False,
            indent=2
        )

    manifest = {
        "segment_id": segment[
            "segment_id"
        ],
        "video_type": segment[
            "video_type"
        ],
        "surah": segment[
            "surah"
        ],
        "start_ayah": segment[
            "start_ayah"
        ],
        "end_ayah": segment[
            "end_ayah"
        ],
        "ayah_count": segment[
            "ayah_count"
        ],
        "privacy_status": seo.get(
            "privacy_status",
            "private"
        ),
        "video_path": str(
            video_path
        ),
        "preview_path": str(
            preview_path
        )
    }

    with (
        OUTPUT_DIR
        / "manifest.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2
        )


def build_video(
    segment: dict,
    seo: dict
) -> str:
    ensure_folders()

    required_fields = [
        "segment_id",
        "video_type",
        "surah",
        "start_ayah",
        "end_ayah",
        "ayahs",
        "text"
    ]

    for field in required_fields:
        if field not in segment:
            raise RuntimeError(
                "Video segment is missing: "
                f"{field}"
            )

    width, height = get_video_dimensions(
        segment
    )

    video_path, preview_path = (
        get_output_paths(
            segment
        )
    )

    audio_path = get_segment_audio(
        segment
    )

    audio = AudioFileClip(
        audio_path
    )

    duration = float(
        audio.duration
    )

    if duration <= 0:
        audio.close()

        raise RuntimeError(
            "Quran audio duration is invalid."
        )

    timeline = create_ayah_timeline(
        segment,
        duration
    )

    background_source = (
        load_background()
    )

    gradient = make_gradient(
        width,
        height
    )

    ayah_layers = [
        create_ayah_layer(
            ayah=item["ayah"],
            segment=segment,
            width=width,
            height=height
        )
        for item in timeline
    ]

    def make_frame(
        time_value: float
    ) -> np.ndarray:
        frame = create_background_frame(
            time_value=time_value,
            duration=duration,
            source=background_source,
            gradient=gradient,
            width=width,
            height=height
        )

        frame = Image.alpha_composite(
            frame,
            create_soft_light(
                time_value,
                width,
                height
            )
        )

        active_index, active_item = (
            get_active_ayah(
                timeline,
                time_value
            )
        )

        local_time = (
            time_value
            - active_item["start"]
        )

        ayah_duration = max(
            0.01,
            active_item["end"]
            - active_item["start"]
        )

        animated_layer = (
            animate_ayah_layer(
                layer=ayah_layers[
                    active_index
                ],
                local_time=local_time,
                ayah_duration=ayah_duration,
                width=width,
                height=height
            )
        )

        frame = Image.alpha_composite(
            frame,
            animated_layer
        )

        return np.asarray(
            frame.convert("RGB"),
            dtype=np.uint8
        )

    preview_time = min(
        max(
            duration * 0.15,
            0.20
        ),
        duration - 0.01
    )

    Image.fromarray(
        make_frame(
            preview_time
        )
    ).save(
        preview_path
    )

    video = VideoClip(
        frame_function=make_frame,
        duration=duration
    ).with_audio(
        audio
    )

    try:
        video.write_videofile(
            str(video_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate=(
                "6000k"
                if segment["video_type"]
                == "long"
                else "4500k"
            ),
            preset="medium",
            threads=2,
            pixel_format="yuv420p",
            logger="bar"
        )

    finally:
        video.close()
        audio.close()

    if (
        not video_path.is_file()
        or video_path.stat().st_size
        < MINIMUM_VIDEO_SIZE
    ):
        raise RuntimeError(
            "The generated Quran video is "
            "missing or empty."
        )

    save_metadata(
        segment=segment,
        seo=seo,
        video_path=video_path,
        preview_path=preview_path
    )

    print()
    print("========== VIDEO READY ==========")
    print("Type:", segment["video_type"])
    print("Size:", f"{width}x{height}")
    print("Surah:", segment["surah"])
    print(
        "Ayahs:",
        f"{segment['start_ayah']}"
        f"-{segment['end_ayah']}"
    )
    print("Duration:", round(duration, 2))
    print("Video:", video_path)
    print("Preview:", preview_path)
    print("Privacy: private")
    print("=================================")

    return str(
        video_path
    )
