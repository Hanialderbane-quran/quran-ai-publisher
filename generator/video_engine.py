"""Broadcast Quran video renderer with rotating animated backgrounds."""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generator.audio_engine import get_segment_audio_package

OUTPUT_DIR = Path("output")
FONT_DIR = Path("assets/fonts")
MEMORY_PATH = Path("data/background_memory.json")
FPS = int(os.getenv("QURAN_VIDEO_FPS", "24"))
CHANNEL_NAME = os.getenv("QURAN_CHANNEL_NAME", "التجارة مع الله").strip() or "التجارة مع الله"
VISUAL_ENGINE_VERSION = "broadcast_identity_4.0"
THEMES = ("moonlit_mountains", "dawn_clouds", "emerald_valley", "desert_twilight", "ocean_night", "islamic_lanterns")


def render_scale() -> float:
    try:
        return max(.35, min(1.0, float(os.getenv("QURAN_RENDER_SCALE", "1"))))
    except ValueError:
        return 1.0


def dimensions(segment: dict) -> tuple[int, int]:
    base = (1920, 1080) if segment.get("video_type") == "long" else (1080, 1920)
    s = render_scale()
    return max(320, int(base[0] * s)), max(320, int(base[1] * s))


def find_font() -> str:
    options = [
        FONT_DIR / "NotoNaskhArabic-Bold.ttf",
        FONT_DIR / "NotoNaskhArabic-Regular.ttf",
        FONT_DIR / "arabic.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in options:
        if path.is_file():
            return str(path)
    raise RuntimeError("No Arabic font was found.")


def read_memory() -> dict:
    try:
        value = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def choose_theme(segment: dict) -> str:
    recent = set(read_memory().get("recent_backgrounds", [])[-3:])
    choices = [x for x in THEMES if x not in recent] or list(THEMES)
    seed = f"{segment.get('segment_id')}:{segment.get('surah')}:{segment.get('start_ayah')}"
    index = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % len(choices)
    return choices[index]


def save_theme(theme: str, segment_id: str) -> None:
    data = read_memory()
    recent = [x for x in data.get("recent_backgrounds", []) if x != theme]
    recent.append(theme)
    history = list(data.get("history", []))
    history.append({"background": theme, "segment_id": segment_id})
    data.update(recent_backgrounds=recent[-4:], history=history[-100:])
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    arr = np.empty((h, w, 3), dtype=np.uint8)
    for y in range(h):
        u = y / max(1, h - 1)
        arr[y, :, :] = [int(top[i] * (1-u) + bottom[i] * u) for i in range(3)]
    return Image.fromarray(arr, "RGB").convert("RGBA")


def stars(img: Image.Image, count: int, alpha: int = 110) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for i in range(count):
        x, y = (i * 137 + 29) % w, (i * 79 + 17) % max(1, int(h * .58))
        r = 1 + i % 2
        d.ellipse((x-r, y-r, x+r, y+r), fill=(245, 231, 191, max(20, alpha-i % 45)))


def glow(img: Image.Image, x: int, y: int, radius: int, color: tuple[int, int, int]) -> None:
    layer = Image.new("RGBA", img.size)
    d = ImageDraw.Draw(layer, "RGBA")
    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(*color, 62))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(12, radius // 2))))
    d = ImageDraw.Draw(img, "RGBA")
    core = max(8, radius // 3)
    d.ellipse((x-core, y-core, x+core, y+core), fill=(*color, 225))


def scene(theme: str, w: int, h: int, t: float) -> Image.Image:
    p = t * .20
    palettes = {
        "moonlit_mountains": ((25, 84, 112), (3, 20, 35)),
        "dawn_clouds": ((91, 128, 161), (239, 170, 112)),
        "emerald_valley": ((21, 91, 94), (7, 31, 41)),
        "desert_twilight": ((72, 48, 91), (205, 116, 74)),
        "ocean_night": ((13, 57, 93), (2, 18, 35)),
        "islamic_lanterns": ((20, 48, 70), (4, 15, 28)),
    }
    img = gradient(w, h, *palettes[theme])
    d = ImageDraw.Draw(img, "RGBA")
    shift = math.sin(p) * w * .025

    if theme in {"moonlit_mountains", "ocean_night", "islamic_lanterns", "emerald_valley"}:
        stars(img, 120 if theme != "emerald_valley" else 70, 120)
    if theme in {"moonlit_mountains", "ocean_night"}:
        glow(img, int(w*.77), int(h*.18), int(min(w,h)*.15), (248,232,188))
    elif theme in {"dawn_clouds", "desert_twilight"}:
        glow(img, int(w*(.76 if theme == "dawn_clouds" else .25)), int(h*.24), int(min(w,h)*.16), (255,220,166))

    d = ImageDraw.Draw(img, "RGBA")
    if theme == "ocean_night":
        horizon = int(h*.67)
        d.rectangle((0, horizon, w, h), fill=(3,30,48,235))
        for i in range(28):
            y = horizon + i * max(2, int(h*.009))
            wobble = math.sin(p*1.8+i*.55)*w*.018
            d.line((w*.20+wobble, y, w*.82-wobble, y), fill=(225,208,151,max(5,45-i)), width=2)
        return img

    if theme == "islamic_lanterns":
        for i, xr in enumerate((.18,.50,.82)):
            x = w*xr + math.sin(p+i*1.7)*w*.012
            top, bottom, r = h*(.05+.025*(i%2)), h*(.34+.05*(i%2)), w*.055
            d.line((x,0,x,top), fill=(210,179,102,120), width=max(1,int(w*.003)))
            d.rounded_rectangle((x-r,top,x+r,bottom), radius=int(r*.35), fill=(13,32,43,210),
                                outline=(222,190,111,190), width=max(2,int(w*.004)))
        d.polygon([(0,h),(0,h*.76),(w*.25,h*.66),(w*.52,h*.82),(w*.78,h*.64),(w,h*.76),(w,h)], fill=(3,19,29,245))
        return img

    colors = {
        "moonlit_mountains": ((5,39,47,238),(2,22,31,250)),
        "dawn_clouds": ((40,62,64,230),(16,39,43,245)),
        "emerald_valley": ((9,54,49,230),(4,30,32,250)),
        "desert_twilight": ((116,65,54,225),(55,39,42,246)),
    }
    far, near = colors[theme]
    d.polygon([(0,h),(0,h*.72),(w*.20+shift,h*.55),(w*.42,h*.76),(w*.65-shift,h*.50),(w,h*.70),(w,h)], fill=far)
    d.polygon([(0,h),(0,h*.84),(w*.28-shift,h*.70),(w*.55,h*.86),(w*.80+shift,h*.68),(w,h*.81),(w,h)], fill=near)
    return img


def canvas(w: int, h: int) -> Image.Image:
    img = gradient(w, h, (8,35,51), (2,11,23))
    d = ImageDraw.Draw(img, "RGBA")
    for ix in range(6):
        for iy in range(8):
            x, y = int((ix+.5)*w/6), int((iy+.6)*h/8)
            r = max(7, int(min(w,h)*.006))
            d.ellipse((x-r,y-r,x+r,y+r), outline=(205,173,95,10), width=1)
    return img


def mihrab_rect(w: int, h: int):
    return (int(w*.12),int(h*.13),int(w*.88),int(h*.59)) if h>w else (int(w*.18),int(h*.10),int(w*.82),int(h*.64))


def text_rect(w: int, h: int):
    return (int(w*.055),int(h*.63),int(w*.945),int(h*.90)) if h>w else (int(w*.075),int(h*.68),int(w*.925),int(h*.91))


def header_rect(w: int, h: int):
    return (int(w*.18),int(h*.047),int(w*.82),int(h*.105)) if h>w else (int(w*.33),int(h*.035),int(w*.67),int(h*.105))


def mihrab(w: int, h: int, image: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (w,h))
    mask = Image.new("L", (w,h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0,int(h*.22),w,int(h*.96)), radius=int(w*.055), fill=255)
    md.pieslice((int(w*.13),0,int(w*.87),int(h*.57)), 180, 360, fill=255)
    md.rectangle((0,int(h*.30),w,int(h*.96)), fill=255)
    layer.paste(image.resize((w,h), Image.Resampling.LANCZOS), (0,0), mask)
    d = ImageDraw.Draw(layer, "RGBA")
    gold, pale = (214,182,96,255), (246,226,169,165)
    a, b = max(2,int(w*.009)), max(1,int(w*.004))
    d.arc((int(w*.13),int(h*.015),int(w*.87),int(h*.59)), 180,360,fill=gold,width=a)
    d.arc((int(w*.16),int(h*.045),int(w*.84),int(h*.56)),180,360,fill=pale,width=b)
    for x in (.075,.925):
        d.line((int(w*x),int(h*.31),int(w*x),int(h*.92)),fill=gold,width=a)
    d.rounded_rectangle((int(w*.055),int(h*.88),int(w*.945),int(h*.975)), radius=int(w*.035), fill=(5,18,29,175), outline=gold, width=a)
    return layer


def words(text: str) -> list[str]:
    return [x for x in str(text).split() if x.strip()]


def layout_words(items: list[str], font_path: str, max_w: int, max_h: int, max_size: int, min_size: int):
    probe = ImageDraw.Draw(Image.new("RGBA",(32,32)))
    for size in range(max_size, min_size-1, -2):
        font, spacing, lines, current, current_w = ImageFont.truetype(font_path,size), max(8,int(size*.20)), [], [], 0.0
        for idx, word in enumerate(items):
            adv = float(probe.textlength(word,font=font,direction="rtl",language="ar"))
            if current and current_w+adv+spacing > max_w:
                lines.append(current)
                current, current_w = [], 0.0
            current.append((idx,word,adv))
            current_w += adv if len(current)==1 else adv+spacing
        if current:
            lines.append(current)
        line_h = int(size*1.55)
        if len(lines)<=5 and len(lines)*line_h<=max_h:
            return font, spacing, lines, line_h
    return font, spacing, lines, line_h


def active_word(items: list[dict], t: float):
    if not items:
        return None
    starts = [float(x["start"]) for x in items]
    idx = bisect.bisect_right(starts,t)-1
    if idx < 0:
        return None
    item = items[min(idx,len(items)-1)]
    return int(item["word_index"]) if float(item["start"])<=t<=float(item["end"]) else None


def text_renderer(segment: dict, audio: dict, w: int, h: int, font_path: str):
    rect, scale = text_rect(w,h), render_scale()
    pw, ph = rect[2]-rect[0], rect[3]-rect[1]
    title_font = ImageFont.truetype(font_path,max(22,int(46*scale)))
    info_font = ImageFont.truetype(font_path,max(18,int(32*scale)))
    footer_font = ImageFont.truetype(font_path,max(17,int(27*scale)))
    wm_font = ImageFont.truetype(font_path,max(16,int(25*scale)))
    layouts = [layout_words(words(a.get("text","")),font_path,int(pw*.86),int(ph*.56),max(28,int(70*scale)),max(20,int(38*scale))) for a in segment["ayahs"]]
    timings = {}
    for item in audio.get("word_timeline",[]):
        timings.setdefault(int(item["global_number"]),[]).append(item)

    @lru_cache(maxsize=96)
    def render(idx: int, active: int | None, reciter: str):
        layer = Image.new("RGBA",(w,h))
        d = ImageDraw.Draw(layer,"RGBA")
        head = header_rect(w,h)
        d.rounded_rectangle(head,radius=max(18,int(min(w,h)*.018)),fill=(7,23,36,218),outline=(214,182,96,255),width=max(2,int(3*scale)))
        d.text(((head[0]+head[2])//2,(head[1]+head[3])//2),f"سورة {segment['surah']}",font=title_font,fill=(247,231,188,255),anchor="mm",direction="rtl",language="ar")
        ayah = segment["ayahs"][idx]
        badge = (int(w*.39),head[3]+int(h*.012),int(w*.61),head[3]+int(h*.055))
        d.rounded_rectangle(badge,radius=int((badge[3]-badge[1])*.45),fill=(14,34,48,205),outline=(216,185,100,220),width=max(1,int(2*scale)))
        d.text((w//2,(badge[1]+badge[3])//2),f"الآية {ayah['ayah']}",font=info_font,fill=(235,238,235,255),anchor="mm",direction="rtl",language="ar")
        d.rounded_rectangle(rect,radius=max(22,int(min(w,h)*.025)),fill=(3,17,28,205),outline=(214,182,96,255),width=max(2,int(3*scale)))
        font, spacing, lines, line_h = layouts[idx]
        y = rect[1]+int(ph*.44)-len(lines)*line_h//2
        for line in lines:
            x = w/2+(sum(v[2] for v in line)+spacing*max(0,len(line)-1))/2
            for word_idx, word, adv in line:
                fill = (232,199,109,255) if active==word_idx else (243,242,234,255)
                d.text((x,y),word,font=font,fill=fill,anchor="ra",direction="rtl",language="ar",stroke_width=max(1,int(scale)),stroke_fill=(0,0,0,135))
                x -= adv+spacing
            y += line_h
        d.text((w//2,rect[3]-int(ph*.12)),reciter,font=footer_font,fill=(221,228,226,245),anchor="mm",direction="rtl",language="ar")
        d.text((int(w*.965),int(h*.965)),CHANNEL_NAME,font=wm_font,fill=(236,218,165,155),anchor="rs",direction="rtl",language="ar",stroke_width=max(1,int(scale)),stroke_fill=(0,0,0,85))
        return layer
    return render, timings


def save_metadata(segment: dict, seo: dict, audio: dict, video: Path, preview: Path, theme: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR/"title.txt").write_text(str(seo.get("title","")),encoding="utf-8")
    (OUTPUT_DIR/"description.txt").write_text(str(seo.get("description","")),encoding="utf-8")
    (OUTPUT_DIR/"tags.json").write_text(json.dumps(seo.get("tags",[]),ensure_ascii=False,indent=2),encoding="utf-8")
    manifest = {
        "segment_id":segment["segment_id"], "video_type":segment["video_type"], "surah":segment["surah"],
        "start_ayah":segment["start_ayah"], "end_ayah":segment["end_ayah"], "video_path":str(video),
        "preview_path":str(preview), "privacy_status":str(seo.get("privacy_status","private")),
        "audio_mode":audio.get("audio_mode"), "test_mode":bool(audio.get("test_mode")),
        "exact_ayah_sync":bool(audio.get("exact_ayah_sync")), "exact_word_sync":bool(audio.get("exact_word_sync")),
        "rights_confirmed":bool(audio.get("rights_confirmed")), "reciter":audio.get("reciter",{}),
        "channel_name":CHANNEL_NAME, "watermark_enabled":True, "background_theme":theme,
        "visual_engine_version":VISUAL_ENGINE_VERSION,
    }
    (OUTPUT_DIR/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")


def build_video(segment: dict, seo: dict) -> str:
    for key in ("segment_id","video_type","surah","start_ayah","end_ayah","ayahs","text"):
        if key not in segment:
            raise RuntimeError(f"Video segment is missing: {key}")
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    w,h = dimensions(segment)
    font_path = find_font()
    package = get_segment_audio_package(segment)
    duration = float(package["duration"])
    timeline = package.get("ayah_timeline",[])
    if duration<=0 or not timeline:
        raise RuntimeError("Audio timeline is invalid.")
    theme = choose_theme(segment)
    audio = AudioFileClip(str(package["audio_path"]))
    render_text, timings = text_renderer(segment,package,w,h,font_path)
    starts = [float(x["start"]) for x in timeline]
    base, mr = canvas(w,h), mihrab_rect(w,h)
    mw,mh = mr[2]-mr[0],mr[3]-mr[1]
    reciter = str(package.get("reciter",{}).get("name","")).strip() or "تلاوة القرآن الكريم"

    def frame(t: float):
        image = base.copy()
        image.alpha_composite(mihrab(mw,mh,scene(theme,mw,mh,t)),(mr[0],mr[1]))
        idx = max(0,min(bisect.bisect_right(starts,t)-1,len(timeline)-1))
        ayah = segment["ayahs"][idx]
        gnum = int(ayah.get("global_number",idx+1))
        image.alpha_composite(render_text(idx,active_word(timings.get(gnum,[]),t),reciter).copy())
        return np.asarray(image.convert("RGB"),dtype=np.uint8)

    video_path = OUTPUT_DIR/f"{segment['segment_id']}.mp4"
    preview_path = OUTPUT_DIR/f"{segment['segment_id']}_preview.png"
    Image.fromarray(frame(min(max(duration*.22,.10),max(.10,duration-.05)))).save(preview_path)
    clip = VideoClip(frame_function=frame,duration=duration).with_audio(audio)
    try:
        clip.write_videofile(str(video_path),fps=FPS,codec="libx264",audio_codec="aac",audio_bitrate="192k",
                             bitrate="6000k" if segment.get("video_type")=="short" else "7500k",
                             preset=os.getenv("QURAN_FFMPEG_PRESET","medium"),threads=2,pixel_format="yuv420p",logger="bar")
    finally:
        clip.close()
        audio.close()
    if not video_path.is_file() or video_path.stat().st_size<10_000:
        raise RuntimeError("Generated video is missing or empty.")
    save_metadata(segment,seo,package,video_path,preview_path,theme)
    save_theme(theme,str(segment["segment_id"]))
    print("Video ready:",video_path,"theme:",theme,"channel:",CHANNEL_NAME)
    return str(video_path)
