"""
Quran AI Publisher
Report Engine
Version: 1.0
"""

import json
import os
from datetime import datetime


REPORT_FOLDER = "output"

if not os.path.exists(REPORT_FOLDER):
    os.makedirs(REPORT_FOLDER)


def create_report(verse, seo):
    report = {
        "created_at": datetime.now().isoformat(),
        "surah": verse["surah"],
        "ayah": verse["ayah"],
        "title": seo["title"],
        "description": seo["description"],
        "tags": seo["tags"],
        "status": "READY"
    }

    with open(
        os.path.join(REPORT_FOLDER, "report.json"),
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(report, file, ensure_ascii=False, indent=4)

    print("Report created successfully.")
