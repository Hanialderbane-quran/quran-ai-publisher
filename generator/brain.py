"""
Quran AI Publisher
Brain Engine
Version 2.0
"""

from generator.verse_selector import choose_verse
from generator.seo import build_seo


def think():

    print()
    print("========== BRAIN ==========")

    verse = choose_verse()

    if verse is None:
        print("No verse available.")
        return None

    seo = build_seo(verse)

    print("Verse Selected")

    return {
        "verse": verse,
        "seo": seo
    }
