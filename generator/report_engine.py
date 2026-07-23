"""Atomic JSON report writer."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path("output")


def create_report(
    segment: dict,
    seo: dict,
    stage: str = "ready",
    extra: dict | None = None,
) -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "segment_id": segment.get("segment_id"),
        "surah": segment.get("surah"),
        "start_ayah": segment.get("start_ayah"),
        "end_ayah": segment.get("end_ayah"),
        "title": seo.get("title"),
        "description": seo.get("description"),
        "tags": seo.get("tags", []),
        "status": "READY" if stage != "failed" else "FAILED",
    }

    if extra:
        report.update(extra)

    path = OUTPUT / "report.json"
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    return report
