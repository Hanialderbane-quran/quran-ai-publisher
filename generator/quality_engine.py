"""
Quran AI Publisher
Quality Engine
Version: 1.0
"""

def validate(verse, seo):
    errors = []

    if verse is None:
        errors.append("No verse selected.")

    if not seo["title"]:
        errors.append("Missing title.")

    if not seo["description"]:
        errors.append("Missing description.")

    if len(seo["tags"]) == 0:
        errors.append("No tags found.")

    if errors:
        print("========== QUALITY CHECK ==========")

        for error in errors:
            print("-", error)

        print("Status : FAILED")
        print("===================================")

        return False

    print("========== QUALITY CHECK ==========")
    print("Status : PASSED")
    print("===================================")

    return True
