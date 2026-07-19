import json
import random


def load_quran():
    with open("data/quran.json", "r", encoding="utf-8") as file:
        return json.load(file)


def load_published():
    with open("data/published.json", "r", encoding="utf-8") as file:
        return json.load(file)


def choose_verse():
    quran = load_quran()
    published = load_published()

    available = []

    for verse in quran:
        key = f"{verse['surah']} - آية {verse['ayah']}"

        if key not in published:
            available.append(verse)

    if not available:
        return None

    return random.choice(available)


if __name__ == "__main__":
    verse = choose_verse()

    if verse:
        print("Selected verse:")
        print(verse["surah"])
        print("Ayah:", verse["ayah"])
        print(verse["text"])
    else:
        print("No new verses available")
