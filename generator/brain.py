"""
Quran AI Publisher
Brain Engine
Version: 1.0
"""

from generator.verse_selector import choose_verse
from generator.seo import build_seo


def think():
    print("========== BRAIN ==========")
    print("Brain is thinking...")
    print()

    verse = choose_verse()

    if verse is None:
        print("No verse selected.")
        return None

    print("Today's verse selected.")
    print()

    seo = build_seo(verse)

    result = {
        "verse": verse,
        "seo": seo
    }

    print("Brain finished successfully.")
    print("===========================")
    print()

    return result
