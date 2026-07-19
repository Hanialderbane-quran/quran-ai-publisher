import json
import random


def load_quran():
    with open("data/quran.json", "r", encoding="utf-8") as file:
        return json.load(file)


def load_published():
    with open("data/published.json", "r", encoding="utf-8") as file:
        return json.load(file)


def save_published(published):
    with open("data/published.json", "w", encoding="utf-8") as file:
        json.dump(published, file, ensure_ascii=False, indent=2)


def choose_verse():
    quran = load_quran()
    published = load_published()

    available = []

    for verse in quran:
        key = f"{verse['surah']} - آية {verse['ayah']}"

        if key not in published:
            available.append(verse)

    if len(available) == 0:
        print("No available verses")
        return None

    selected = random.choice(available)

    key = f"{selected['surah']} - آية {selected['ayah']}"

    published.append(key)
    save_published(published)

    print("Memory updated:")
    print(key)

    return selected
