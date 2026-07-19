import json
import os


def check_required_files():
    required_files = [
        "config.json",
        "data/quran.json",
        "data/published.json",
        "data/state.json"
    ]

    missing = []

    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)

    return missing


def run_safety_check():
    missing = check_required_files()

    if len(missing) > 0:
        print("Safety Check Failed")
        print("Missing files:")

        for file in missing:
            print("-", file)

        return False

    print("Safety Check Passed")
    return True
