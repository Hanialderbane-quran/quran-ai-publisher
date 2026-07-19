"""
Quran AI Publisher
Settings Manager
Version: 1.0
"""

SETTINGS = {
    "project_name": "Quran AI Publisher",
    "project_version": "1.0",

    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration": 60
    },

    "youtube": {
        "privacy": "public",
        "category": "Education",
        "made_for_kids": False
    },

    "safety": {
        "allow_duplicates": False,
        "stop_on_error": True
    }
}


def get_settings():
    return SETTINGS
