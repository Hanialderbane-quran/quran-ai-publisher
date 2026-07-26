"""Download and normalize real mosque footage for Quran videos.

This replaces the previously generated/drawn mosque scenes. The selected clips are
real stock footage published on Pixabay and are used under the Pixabay Content
License. GitHub Actions downloads them at render time, converts them to a stable
1920x1080 H.264 format, strips their audio, and records source metadata.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

OUTPUT = Path("assets/background_videos")
TEMP = OUTPUT / "downloads"
LIBRARY_FILE = Path("data/background_videos.json")

CLIPS = [
    {
        "id": "real_mosque_istanbul",
        "page_url": "https://pixabay.com/videos/mosque-islam-religious-architecture-155851/",
        "source": "pixabay-real-footage",
        "license": "Pixabay Content License",
    },
    {
        "id": "real_mosque_pakistan",
        "page_url": "https://pixabay.com/videos/mosque-islam-muslim-pakistan-163886/",
        "source": "pixabay-real-footage",
        "license": "Pixabay Content License",
    },
    {
        "id": "real_mosque_sunset_drone",
        "page_url": "https://pixabay.com/videos/mosque-islam-sunset-islamic-227088/",
        "source": "pixabay-real-footage",
        "license": "Pixabay Content License",
    },
]


def run(command: list[str], message: str) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise RuntimeError(f"{message}: {detail}")
    return result


def find_downloaded(prefix: str) -> Path:
    matches = sorted(TEMP.glob(f"{prefix}.*"))
    matches = [path for path in matches if path.is_file() and path.suffix != ".part"]
    if not matches:
        raise RuntimeError(f"Downloaded source file was not found for {prefix}.")
    return matches[0]


def download_clip(item: dict) -> Path:
    TEMP.mkdir(parents=True, exist_ok=True)
    prefix = item["id"]
    for old in TEMP.glob(f"{prefix}.*"):
        old.unlink(missing_ok=True)

    run(
        [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--retries", "3",
            "--socket-timeout", "60",
            "-f", "bv*[height<=1080]/b[height<=1080]/best",
            "-o", str(TEMP / f"{prefix}.%(ext)s"),
            item["page_url"],
        ],
        f"Could not download real background {prefix}",
    )
    return find_downloaded(prefix)


def normalize(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".temporary.mp4")
    temporary.unlink(missing_ok=True)

    run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(source),
            "-t", "20",
            "-an",
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            "fps=24,format=yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-movflags", "+faststart",
            str(temporary),
        ],
        f"Could not normalize background {source.name}",
    )
    temporary.replace(destination)

    probe = run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height",
            "-of", "csv=p=0", str(destination),
        ],
        f"Could not verify background {destination.name}",
    )
    if "1920,1080" not in probe.stdout.replace("\n", ""):
        raise RuntimeError(f"Background has incorrect dimensions: {destination}")
    if destination.stat().st_size < 500_000:
        raise RuntimeError(f"Background file is unexpectedly small: {destination}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)

    library = []
    for item in CLIPS:
        destination = OUTPUT / f"{item['id']}.mp4"
        if not destination.is_file() or destination.stat().st_size < 500_000:
            source = download_clip(item)
            normalize(source, destination)
        library.append(
            {
                "id": item["id"],
                "path": destination.as_posix(),
                "source": item["source"],
                "license": item["license"],
                "source_page": item["page_url"],
                "real_footage": True,
            }
        )
        print("Real background ready:", destination)

    LIBRARY_FILE.write_text(
        json.dumps(library, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.rmtree(TEMP, ignore_errors=True)
    print(f"Prepared {len(library)} real mosque background videos.")


if __name__ == "__main__":
    main()
