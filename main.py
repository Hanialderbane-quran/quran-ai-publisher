import json
from datetime import datetime

def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)

def start():
    config = load_config()

    print("Quran AI Publisher Started")
    print("Channel:", config["channel_name"])
    print("Time:", datetime.now())
    print("Preparing daily Quran video...")

if __name__ == "__main__":
    start()
