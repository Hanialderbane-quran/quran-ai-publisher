"""Optional private YouTube uploader."""
from __future__ import annotations

import os
from pathlib import Path

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def upload_if_enabled(video_path: str, seo: dict, manifest: dict) -> dict:
    if not env_true("YOUTUBE_UPLOAD_ENABLED", False):
        return {
            "status": "skipped",
            "reason": "YOUTUBE_UPLOAD_ENABLED is false",
        }

    if manifest.get("test_mode") is True:
        raise RuntimeError(
            "YouTube upload blocked: test/silent audio is active."
        )
    if manifest.get("exact_word_sync") is not True:
        raise RuntimeError(
            "YouTube upload blocked: exact word synchronization is not ready."
        )
    if manifest.get("rights_confirmed") is not True:
        raise RuntimeError(
            "YouTube upload blocked: audio publication rights are not confirmed."
        )

    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError("YouTube OAuth secrets are incomplete.")

    path = Path(video_path)
    if not path.is_file():
        raise RuntimeError("Video file does not exist for upload.")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )
    youtube = build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    body = {
        "snippet": {
            "title": str(seo["title"])[:100],
            "description": str(seo["description"]),
            "tags": [str(tag) for tag in seo.get("tags", [])],
            "categoryId": str(seo.get("category_id", "27")),
            "defaultLanguage": "ar",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": bool(
                seo.get("made_for_kids", False)
            ),
        },
    }

    media = MediaFileUpload(
        str(path),
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(
            "YouTube upload completed without a video id."
        )

    return {
        "status": "uploaded",
        "video_id": video_id,
        "privacy": "private",
    }
