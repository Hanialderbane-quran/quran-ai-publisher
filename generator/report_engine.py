"""
Quran AI Publisher
Report Engine
"""

import json
import os
from datetime import datetime

OUTPUT = "output"

os.makedirs(OUTPUT, exist_ok=True)


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

        os.path.join(OUTPUT, "report.json"),

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(report, file, ensure_ascii=False, indent=4)

    return report
