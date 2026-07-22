"""
Quran AI Publisher
Real Video Engine
Version 4.0
"""

import json
import os
import textwrap

import arabic_reshaper
import numpy as np
from bidi.algorithm import get_display
from moviepy import ImageClip
from PIL import Image, ImageDraw, ImageFont


OUTPUT_FOLDER = "output"
VIDEO_PATH = os.path.join(OUTPUT_FOLDER, "video.mp4")
FRAME_PATH = os.path.join(OUTPUT_FOLDER, "frame.png")

WIDTH = 1080
HEIGHT = 1920
FPS = 24
DURATION = 12


def prepare_output():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def find_font():
    possible_fonts = [
        "assets/fonts/arabic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]

    for font_path in possible_fonts:
        if os.path.exists(font_path):
            return font_path

    raise FileNotFoundError("No Arabic font was found.")


def prepare_arabic(text):
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def wrap_arabic_text(text, max_chars=24):
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])

        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))

            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def create_gradient_background():
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()

    top = (17, 45, 55)
    bottom = (4, 17, 25)

    for y in range(HEIGHT):
        ratio = y / HEIGHT

        red = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        green = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        blue = int(top[2] * (1 - ratio) + bottom[2] * ratio)

        for x in range(WIDTH):
            pixels[x, y] = (red, green, blue)

    return image


def draw_centered_text(draw, text, font, y, fill):
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]

    x = (WIDTH - text_width) // 2
    draw.text((x, y), text, font=font, fill=fill)


def create_video_frame(verse):
    font_path = find_font()

    title_font = ImageFont.truetype(font_path, 56)
    verse_font = ImageFont.truetype(font_path, 68)
    footer_font = ImageFont.truetype(font_path, 42)

    image = create_gradient_background()
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
