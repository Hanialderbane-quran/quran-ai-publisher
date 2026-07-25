"""Deterministic broadcast visual identity for Quran videos.

Every surah receives a stable visual theme. Shorts and long videos use
separate compositions while preserving one channel identity.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ASSET_DIR = Path("assets")
BACKGROUND_DIR = ASSET_DIR / "backgrounds"


@dataclass(frozen=True)
class Theme:
    key: str
    background_family: str
    top: tuple[int, int, int]
    bottom: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_soft: tuple[int, int, int]
    panel: tuple[int, int, int]
    text: tuple[int, int, int]
    motion: str


THEMES: tuple[Theme, ...] = (
    Theme("royal_night", "mosque", (17, 46, 72), (2, 10, 22), (223, 190, 104), (249, 226, 164), (3, 18, 31), (248, 247, 239), "push_in"),
    Theme("emerald_dawn", "architecture", (24, 83, 76), (3, 25, 31), (222, 184, 91), (244, 222, 159), (4, 31, 34), (250, 248, 238), "drift_left"),
    Theme("desert_gold", "mountain", (112, 73, 45), (28, 17, 20), (240, 197, 103), (255, 226, 166), (30, 20, 23), (252, 246, 232), "drift_right"),
    Theme("celestial_blue", "sky", (32, 74, 125), (5, 16, 43), (225, 194, 111), (249, 230, 174), (4, 19, 43), (246, 248, 250), "rise"),
    Theme("violet_twilight", "pattern", (72, 53, 91), (20, 12, 35), (229, 190, 105), (250, 226, 165), (24, 14, 38), (250, 246, 238), "push_in"),
    Theme("ocean_teal", "water", (20, 88, 105), (2, 25, 39), (221, 190, 106), (246, 224, 167), (2, 28, 40), (245, 249, 247), "drift_left"),
)

FAMILY_HINTS: dict[str, tuple[str, ...]] = {
    "mosque": ("mosque", "masjid", "mihrab"),
    "architecture": ("arch", "islamic", "courtyard", "dome"),
    "mountain": ("mountain", "desert", "valley"),
    "sky": ("sky", "cloud", "moon", "night"),
    "pattern": ("pattern", "arabesque", "geometric"),
    "water": ("water", "sea", "river", "lake"),
}


def stable_number(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def select_theme(segment: dict) -> Theme:
    seed = stable_number(segment.get("surah_number"), segment.get("surah"), segment.get("video_type"))
    return THEMES[seed % len(THEMES)]


def _candidate_backgrounds(family: str) -> list[Path]:
    if not BACKGROUND_DIR.is_dir():
        return []
    images = [
        path for path in BACKGROUND_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    hints = FAMILY_HINTS.get(family, ())
    matched = [path for path in images if any(hint in path.stem.lower() for hint in hints)]
    return sorted(matched or images)


def choose_background(segment: dict, theme: Theme) -> Path | None:
    candidates = _candidate_backgrounds(theme.background_family)
    if not candidates:
        return None
    seed = stable_number(segment.get("surah"), segment.get("part_number", 1), segment.get("video_type"), "background")
    return candidates[seed % len(candidates)]


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    size = (max(width, math.ceil(image.width * scale)), max(height, math.ceil(image.height * scale)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    left = max(0, (size[0] - width) // 2)
    top = max(0, (size[1] - height) // 2)
    return resized.crop((left, top, left + width, top + height))


class CinematicBackground:
    def __init__(self, segment: dict, width: int, height: int):
        self.segment = segment
        self.width = width
        self.height = height
        self.theme = select_theme(segment)
        self.path = choose_background(segment, self.theme)
        self.image = Image.open(self.path).convert("RGB") if self.path else None
        self.seed = stable_number(segment.get("surah"), segment.get("video_type"))

    def frame(self, t: float, duration: float) -> Image.Image:
        progress = max(0.0, min(1.0, t / max(duration, 0.01)))
        if self.image is None:
            frame = self._procedural(t, progress)
        else:
            frame = self._photo_frame(progress)
        return self._grade(frame, t)

    def _photo_frame(self, progress: float) -> Image.Image:
        motion = self.theme.motion
        zoom = 1.035 + 0.055 * progress
        work_w = max(self.width, int(self.width * zoom))
        work_h = max(self.height, int(self.height * zoom))
        image = cover(self.image, work_w, work_h)
        max_x = max(0, work_w - self.width)
        max_y = max(0, work_h - self.height)
        if motion == "drift_left":
            x = int(max_x * (0.72 - 0.44 * progress))
            y = int(max_y * 0.48)
        elif motion == "drift_right":
            x = int(max_x * (0.28 + 0.44 * progress))
            y = int(max_y * 0.48)
        elif motion == "rise":
            x = int(max_x * 0.50)
            y = int(max_y * (0.68 - 0.36 * progress))
        else:
            x = int(max_x * (0.46 + 0.08 * math.sin(progress * math.pi)))
            y = int(max_y * 0.50)
        return image.crop((x, y, x + self.width, y + self.height)).convert("RGBA")

    def _procedural(self, t: float, progress: float) -> Image.Image:
        top, bottom = self.theme.top, self.theme.bottom
        image = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        for y in range(self.height):
            ratio = y / max(1, self.height - 1)
            color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            draw.line((0, y, self.width, y), fill=color)

        overlay = image.convert("RGBA")
        od = ImageDraw.Draw(overlay, "RGBA")
        unit = min(self.width, self.height)
        moon_r = max(20, int(unit * 0.055))
        moon_x = int(self.width * (0.78 if self.height < self.width else 0.72))
        moon_y = int(self.height * 0.19)
        glow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        gd.ellipse((moon_x - moon_r * 2, moon_y - moon_r * 2, moon_x + moon_r * 2, moon_y + moon_r * 2), fill=(*self.theme.accent_soft, 45))
        glow = glow.filter(ImageFilter.GaussianBlur(max(18, moon_r)))
        overlay = Image.alpha_composite(overlay, glow)
        od = ImageDraw.Draw(overlay, "RGBA")
        od.ellipse((moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r), fill=(*self.theme.accent_soft, 225))

        shift = int(math.sin(t * 0.16 + self.seed % 5) * self.width * 0.018)
        horizon = int(self.height * (0.69 if self.height > self.width else 0.72))
        od.polygon([
            (0, horizon + int(self.height * 0.08)),
            (int(self.width * 0.20) + shift, horizon - int(self.height * 0.05)),
            (int(self.width * 0.43), horizon + int(self.height * 0.03)),
            (int(self.width * 0.68) - shift, horizon - int(self.height * 0.08)),
            (self.width, horizon + int(self.height * 0.05)),
            (self.width, self.height),
            (0, self.height),
        ], fill=(*self.theme.bottom, 245))
        return overlay

    def _grade(self, frame: Image.Image, t: float) -> Image.Image:
        image = ImageEnhance.Color(frame.convert("RGB")).enhance(0.90)
        image = ImageEnhance.Contrast(image).enhance(1.08).convert("RGBA")
        shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade, "RGBA")
        sd.rectangle((0, 0, self.width, self.height), fill=(0, 7, 14, 34))
        vignette = Image.new("L", image.size, 0)
        vd = ImageDraw.Draw(vignette)
        inset_x, inset_y = int(self.width * 0.07), int(self.height * 0.05)
        vd.ellipse((-inset_x, -inset_y, self.width + inset_x, self.height + inset_y), fill=195)
        vignette = vignette.filter(ImageFilter.GaussianBlur(max(40, int(min(self.width, self.height) * 0.12))))
        dark = Image.new("RGBA", image.size, (0, 0, 0, 105))
        dark.putalpha(Image.eval(vignette, lambda p: 255 - p))
        image = Image.alpha_composite(image, shade)
        image = Image.alpha_composite(image, dark)

        particles = Image.new("RGBA", image.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(particles, "RGBA")
        for index in range(14):
            phase = ((self.seed >> (index % 8)) & 255) / 255
            x = int((phase * self.width + t * (3 + index % 4)) % self.width)
            y = int(((index + 1) / 16 * self.height + math.sin(t * 0.20 + index) * 14) % self.height)
            radius = 1 + index % 3
            pd.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*self.theme.accent_soft, 22 + index % 4 * 8))
        return Image.alpha_composite(image, particles)
