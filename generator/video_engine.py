"""Professional Quran video renderer with word highlighting."""
from __future__ import annotations

import bisect
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip, VideoFileClip
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from generator.audio_engine import get_segment_audio_package
from generator.background_engine import choose_background

OUTPUT_DIR = Path("output")
FONT_DIR = Path("assets/fonts")
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
MINIMUM_VIDEO_SIZE = 10000


def render_scale() -> float:
    try:
        return max(
            0.2,
            min(
                1.0,
                float(
                    os.getenv(
                        "QURAN_RENDER_SCALE",
                        "1",
                    )
                ),
            ),
        )
    except ValueError:
        return 1.0


def dimensions(segment: dict) -> tuple[int, int]:
    base = (
        (1920, 1080)
        if segment.get("video_type") == "long"
        else (1080, 1920)
    )
    scale = render_scale()
    return (
        max(320, int(base[0] * scale)),
        max(320, int(base[1] * scale)),
    )


def find_font() -> str:
    candidates = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
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
        ),
    ]

    for path in candidates:
        if path.is_file():
            return str(path)

    raise RuntimeError(
        "No Arabic font was found."
    )


def cover(
    image: Image.Image,
    width: int,
    height: int,
) -> Image.Image:
    scale = max(
        width / image.width,
        height / image.height,
    )
    size = (
        math.ceil(image.width * scale),
        math.ceil(image.height * scale),
    )
    image = image.resize(
        size,
        Image.Resampling.LANCZOS,
    )
    left = max(
        0,
        (image.width - width) // 2,
    )
    top = max(
        0,
        (image.height - height) // 2,
    )
    return image.crop(
        (
            left,
            top,
            left + width,
            top + height,
        )
    )


def procedural_background(
    width: int,
    height: int,
    time_value: float,
) -> Image.Image:
    top = np.array(
        [10, 52, 67],
        dtype=np.float32,
    )
    bottom = np.array(
        [2, 8, 18],
        dtype=np.float32,
    )
    vertical = np.linspace(
        0,
        1,
        height,
        dtype=np.float32,
    )[:, None, None]
    gradient = (
        top[None, None, :]
        * (1 - vertical)
        +
        bottom[None, None, :]
        * vertical
    )
    gradient = np.repeat(
        gradient,
        width,
        axis=1,
    ).astype(np.uint8)
    shift = int(
        math.sin(time_value * 0.08)
        * width
        * 0.01
    )
    gradient = np.roll(
        gradient,
        shift,
        axis=1,
    )
    return Image.fromarray(
        gradient
    ).convert("RGBA")


class BackgroundSource:
    def __init__(
        self,
        path: Path | None,
        width: int,
        height: int,
    ):
        self.path = path
        self.width = width
        self.height = height
        self.image = None
        self.video = None

        if path is None:
            return

        if path.suffix.lower() in {
            ".mp4",
            ".mov",
            ".mkv",
            ".webm",
        }:
            self.video = VideoFileClip(
                str(path),
                audio=False,
            )
        else:
            image = Image.open(
                path
            ).convert("RGB")
            image = ImageEnhance.Brightness(
                image
            ).enhance(0.70)
            image = ImageEnhance.Color(
                image
            ).enhance(0.80)
            self.image = image

    def frame(
        self,
        time_value: float,
        total_duration: float,
    ) -> Image.Image:
        if self.path is None:
            return procedural_background(
                self.width,
                self.height,
                time_value,
            )

        if self.video is not None:
            clip_duration = max(
                0.1,
                float(self.video.duration),
            )
            array = self.video.get_frame(
                time_value % clip_duration
            )
            image = Image.fromarray(
                np.asarray(
                    array,
                    dtype=np.uint8,
                )
            ).convert("RGB")
            return cover(
                image,
                self.width,
                self.height,
            ).convert("RGBA")

        progress = (
            time_value
            / max(total_duration, 0.01)
        )
        zoom = (
            1.02
            + progress * 0.05
        )
        render_width = int(
            self.width * zoom
        )
        render_height = int(
            self.height * zoom
        )
        image = cover(
            self.image,
            render_width,
            render_height,
        )

        x_room = max(
            0,
            render_width - self.width,
        )
        y_room = max(
            0,
            render_height - self.height,
        )
        x = int(
            x_room
            * (
                0.5
                + 0.12
                * math.sin(
                    progress * math.pi
                )
            )
        )
        y = int(
            y_room
            * (
                0.5
                + 0.10
                * math.cos(
                    progress * math.pi
                )
            )
        )
        return image.crop(
            (
                x,
                y,
                x + self.width,
                y + self.height,
            )
        ).convert("RGBA")

    def close(self) -> None:
        if self.video is not None:
            self.video.close()


def rounded_panel(
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    if height > width:
        return (
            int(width * 0.07),
            int(height * 0.20),
            int(width * 0.93),
            int(height * 0.80),
        )

    return (
        int(width * 0.12),
        int(height * 0.20),
        int(width * 0.88),
        int(height * 0.82),
    )


def text_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> tuple[int, int, int, int]:
    return draw.textbbox(
        (0, 0),
        text,
        font=font,
        direction="rtl",
        language="ar",
    )


def word_width(
    draw: ImageDraw.ImageDraw,
    word: str,
    font: ImageFont.FreeTypeFont,
) -> int:
    box = text_box(
        draw,
        word,
        font,
    )
    return box[2] - box[0]


def make_lines(
    draw,
    words,
    font,
    maximum_width,
    spacing,
):
    lines = []
    current = []
    current_width = 0

    for index, word in enumerate(words):
        width = word_width(
            draw,
            word,
            font,
        )
        extra = (
            width
            if not current
            else width + spacing
        )

        if (
            current
            and current_width + extra
            > maximum_width
        ):
            lines.append(current)
            current = []
            current_width = 0

        current.append(
            (
                index,
                word,
                width,
            )
        )
        current_width += (
            width
            if len(current) == 1
            else width + spacing
        )

    if current:
        lines.append(current)

    return lines


def fit_layout(
    words,
    font_path,
    maximum_width,
    maximum_height,
    maximum_size,
    minimum_size,
):
    probe = Image.new(
        "RGBA",
        (32, 32),
    )
    draw = ImageDraw.Draw(probe)

    for size in range(
        maximum_size,
        minimum_size - 1,
        -2,
    ):
        font = ImageFont.truetype(
            font_path,
            size,
        )
        spacing = max(
            8,
            int(size * 0.22),
        )
        lines = make_lines(
            draw,
            words,
            font,
            maximum_width,
            spacing,
        )
        line_height = int(
            size * 1.55
        )

        if (
            len(lines) * line_height
            <= maximum_height
        ):
            return (
                font,
                spacing,
                lines,
                line_height,
            )

    font = ImageFont.truetype(
        font_path,
        minimum_size,
    )
    spacing = max(
        8,
        int(minimum_size * 0.22),
    )
    lines = make_lines(
        draw,
        words,
        font,
        maximum_width,
        spacing,
    )
    return (
        font,
        spacing,
        lines,
        int(minimum_size * 1.55),
    )


def active_item(
    timeline: list[dict],
    starts: list[float],
    time_value: float,
) -> tuple[int, dict]:
    index = (
        bisect.bisect_right(
            starts,
            time_value,
        )
        - 1
    )
    index = max(
        0,
        min(
            index,
            len(timeline) - 1,
        ),
    )
    return index, timeline[index]


def active_word_index(
    words_timing: list[dict],
    time_value: float,
) -> int | None:
    if not words_timing:
        return None

    starts = [
        float(item["start"])
        for item in words_timing
    ]
    index = (
        bisect.bisect_right(
            starts,
            time_value,
        )
        - 1
    )

    if index < 0:
        return None

    index = min(
        index,
        len(words_timing) - 1,
    )
    return int(
        words_timing[index][
            "word_index"
        ]
    )


def draw_centered_arabic(
    draw,
    xy,
    text,
    font,
    fill,
):
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor="mm",
        direction="rtl",
        language="ar",
        align="center",
    )


def build_text_renderer(
    segment,
    audio_package,
    width,
    height,
    font_path,
):
    panel = rounded_panel(
        width,
        height,
    )
    panel_width = (
        panel[2] - panel[0]
    )
    panel_height = (
        panel[3] - panel[1]
    )
    scale = render_scale()

    header_font = ImageFont.truetype(
        font_path,
        max(
            24,
            int(58 * scale),
        ),
    )
    footer_font = ImageFont.truetype(
        font_path,
        max(
            18,
            int(36 * scale),
        ),
    )

    ayah_data = []
    for ayah in segment["ayahs"]:
        words = [
            word
            for word in str(
                ayah["text"]
            ).split()
            if word
        ]
        layout = fit_layout(
            words,
            font_path,
            int(panel_width * 0.82),
            int(panel_height * 0.56),
            max(
                30,
                int(92 * scale),
            ),
            max(
                20,
                int(44 * scale),
            ),
        )
        ayah_data.append(
            (
                words,
                *layout,
            )
        )

    by_global = {}
    for item in audio_package.get(
        "word_timeline",
        [],
    ):
        by_global.setdefault(
            int(item["global_number"]),
            [],
        ).append(item)

    for value in by_global.values():
        value.sort(
            key=lambda item:
            float(item["start"])
        )

    @lru_cache(maxsize=48)
    def render(
        ayah_index: int,
        highlighted_word: int | None,
    ) -> Image.Image:
        layer = Image.new(
            "RGBA",
            (width, height),
            (0, 0, 0, 0),
        )
        draw = ImageDraw.Draw(layer)
        ayah = segment["ayahs"][
            ayah_index
        ]
        (
            words,
            font,
            spacing,
            lines,
            line_height,
        ) = ayah_data[ayah_index]

        draw.rounded_rectangle(
            panel,
            radius=max(
                18,
                int(
                    min(width, height)
                    * 0.018
                ),
            ),
            fill=(2, 16, 25, 176),
            outline=(202, 166, 82, 215),
            width=max(
                2,
                int(3 * scale),
            ),
        )

        header_y = (
            panel[1]
            + int(
                panel_height * 0.12
            )
        )
        draw_centered_arabic(
            draw,
            (
                width // 2,
                header_y,
            ),
            (
                f"سورة {segment['surah']}"
                f"  •  الآية {ayah['ayah']}"
            ),
            header_font,
            (231, 203, 128, 255),
        )

        total_height = (
            len(lines)
            * line_height
        )
        y = (
            panel[1]
            + int(
                panel_height * 0.50
            )
            - total_height // 2
        )
        right_edge = (
            panel[2]
            - int(
                panel_width * 0.09
            )
        )

        for line in lines:
            x = right_edge

            for (
                word_index,
                word,
                measured_width,
            ) in line:
                top = (
                    y
                    + int(
                        line_height * 0.10
                    )
                )
                is_active = (
                    highlighted_word
                    == word_index
                )

                if is_active:
                    padding_x = max(
                        5,
                        int(
                            font.size * 0.13
                        ),
                    )
                    padding_y = max(
                        3,
                        int(
                            font.size * 0.08
                        ),
                    )
                    draw.rounded_rectangle(
                        (
                            x
                            - measured_width
                            - padding_x,
                            top - padding_y,
                            x + padding_x,
                            top
                            + font.size
                            + padding_y,
                        ),
                        radius=max(
                            5,
                            int(
                                font.size
                                * 0.12
                            ),
                        ),
                        fill=(
                            226,
                            189,
                            91,
                            238,
                        ),
                    )
                    fill = (
                        8,
                        27,
                        31,
                        255,
                    )
                else:
                    fill = (
                        244,
                        243,
                        232,
                        255,
                    )

                draw.text(
                    (
                        x,
                        top,
                    ),
                    word,
                    font=font,
                    fill=fill,
                    anchor="ra",
                    direction="rtl",
                    language="ar",
                    stroke_width=0,
                )
                x -= (
                    measured_width
                    + spacing
                )

            y += line_height

        reciter_name = str(
            audio_package.get(
                "reciter",
                {},
            ).get(
                "name",
                "",
            )
        )
        footer = (
            "القرآن الكريم"
            if not reciter_name
            else (
                "القرآن الكريم"
                f"  •  {reciter_name}"
            )
        )
        draw_centered_arabic(
            draw,
            (
                width // 2,
                panel[3]
                - int(
                    panel_height
                    * 0.10
                ),
            ),
            footer,
            footer_font,
            (221, 229, 229, 255),
        )
        return layer

    return render, by_global


def save_metadata(
    segment,
    seo,
    audio_package,
    video_path,
    preview_path,
):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    (
        OUTPUT_DIR / "title.txt"
    ).write_text(
        str(seo["title"]),
        encoding="utf-8",
    )
    (
        OUTPUT_DIR
        / "description.txt"
    ).write_text(
        str(seo["description"]),
        encoding="utf-8",
    )
    (
        OUTPUT_DIR
        / "segment_text.txt"
    ).write_text(
        str(segment["text"]),
        encoding="utf-8",
    )

    with (
        OUTPUT_DIR / "tags.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            seo["tags"],
            file,
            ensure_ascii=False,
            indent=2,
        )

    manifest = {
        "segment_id":
        segment["segment_id"],
        "video_type":
        segment["video_type"],
        "surah":
        segment["surah"],
        "start_ayah":
        segment["start_ayah"],
        "end_ayah":
        segment["end_ayah"],
        "start_global_number":
        segment["start_global_number"],
        "end_global_number":
        segment["end_global_number"],
        "privacy_status":
        seo.get(
            "privacy_status",
            "private",
        ),
        "video_path":
        str(video_path),
        "preview_path":
        str(preview_path),
        "audio_mode":
        audio_package.get(
            "audio_mode"
        ),
        "test_mode":
        bool(
            audio_package.get(
                "test_mode"
            )
        ),
        "exact_ayah_sync":
        bool(
            audio_package.get(
                "exact_ayah_sync"
            )
        ),
        "exact_word_sync":
        bool(
            audio_package.get(
                "exact_word_sync"
            )
        ),
        "rights_confirmed":
        bool(
            audio_package.get(
                "rights_confirmed"
            )
        ),
        "reciter":
        audio_package.get(
            "reciter",
            {},
        ),
    }

    with (
        OUTPUT_DIR / "manifest.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )


def build_video(
    segment: dict,
    seo: dict,
) -> str:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    width, height = dimensions(
        segment
    )
    font_path = find_font()
    audio_package = (
        get_segment_audio_package(
            segment
        )
    )
    audio_path = str(
        audio_package["audio_path"]
    )
    duration = float(
        audio_package["duration"]
    )
    timeline = audio_package.get(
        "ayah_timeline",
        [],
    )

    if duration <= 0 or not timeline:
        raise RuntimeError(
            "Audio package has invalid "
            "duration or timing."
        )

    segment_id = str(
        segment["segment_id"]
    )
    video_path = (
        OUTPUT_DIR
        / f"{segment_id}.mp4"
    )
    preview_path = (
        OUTPUT_DIR
        / f"{segment_id}_preview.png"
    )

    background = BackgroundSource(
        choose_background(),
        width,
        height,
    )
    audio = AudioFileClip(
        audio_path
    )
    render_text, word_timings = (
        build_text_renderer(
            segment,
            audio_package,
            width,
            height,
            font_path,
        )
    )
    timeline_starts = [
        float(item["start"])
        for item in timeline
    ]

    def make_frame(
        time_value: float,
    ) -> np.ndarray:
        frame = background.frame(
            time_value,
            duration,
        )
        darkness = Image.new(
            "RGBA",
            (width, height),
            (0, 5, 11, 72),
        )
        frame = Image.alpha_composite(
            frame,
            darkness,
        )

        ayah_index, item = active_item(
            timeline,
            timeline_starts,
            time_value,
        )
        ayah = segment["ayahs"][
            ayah_index
        ]
        active_word = (
            active_word_index(
                word_timings.get(
                    int(
                        ayah[
                            "global_number"
                        ]
                    ),
                    [],
                ),
                time_value,
            )
        )
        layer = render_text(
            ayah_index,
            active_word,
        ).copy()

        local_time = (
            time_value
            - float(item["start"])
        )
        ayah_duration = max(
            0.01,
            (
                float(item["end"])
                - float(item["start"])
            ),
        )
        fade_in = min(
            1.0,
            max(
                0.0,
                local_time / 0.35,
            ),
        )
        fade_out = min(
            1.0,
            max(
                0.0,
                (
                    ayah_duration
                    - local_time
                ) / 0.35,
            ),
        )
        fade = min(
            fade_in,
            fade_out,
        )

        if fade < 1.0:
            alpha = (
                layer.getchannel("A")
                .point(
                    lambda value:
                    int(value * fade)
                )
            )
            layer.putalpha(alpha)

        frame = Image.alpha_composite(
            frame,
            layer,
        )
        return np.asarray(
            frame.convert("RGB"),
            dtype=np.uint8,
        )

    preview_time = min(
        max(
            duration * 0.2,
            0.1,
        ),
        max(
            0.1,
            duration - 0.05,
        ),
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
        duration=duration,
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
                "5500k"
                if segment.get(
                    "video_type"
                ) == "short"
                else "7000k"
            ),
            preset=os.getenv(
                "QURAN_FFMPEG_PRESET",
                "medium",
            ),
            threads=2,
            pixel_format="yuv420p",
            logger="bar",
        )
    finally:
        video.close()
        audio.close()
        background.close()

    if (
        not video_path.is_file()
        or video_path.stat().st_size
        < MINIMUM_VIDEO_SIZE
    ):
        raise RuntimeError(
            "Generated video is missing "
            "or empty."
        )

    save_metadata(
        segment,
        seo,
        audio_package,
        video_path,
        preview_path,
    )

    print("Video:", video_path)
    print(
        "Resolution:",
        f"{width}x{height}",
    )
    print(
        "Exact word sync:",
        audio_package.get(
            "exact_word_sync"
        ),
    )
    return str(video_path)
