from generator.verse_selector import choose_verse


def think():
    print("Brain is thinking...")

    verse = choose_verse()

    if verse is None:
        print("No verse selected")
        return None

    print("Brain selected today's verse")

    return verse
