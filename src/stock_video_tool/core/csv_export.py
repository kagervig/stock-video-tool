"""Write the Envato stock-video import CSV.

One row per clip. Filename is the processed output (converted/stripped) when
there is one, otherwise the original file. Title, Description, Keywords, and
Category come from the pipeline; prices are fixed; every other column is blank.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import PRICE_MULTI_USE, PRICE_SINGLE_USE, VideoItem

COLUMNS = [
    "Filename",
    "Title",
    "Description",
    "Keywords",
    "Category",
    "Price: Single Use License ($USD)",
    "Price: Multi-use License ($USD)",
    "Recognisable people?",
    "Recognisable buildings?",
    "Releases",
    "Is Motion Graphics?",
    "AudioJungle Track (IDs)",
    "Color",
    "Pace",
    "Movement",
    "Composition",
    "Setting",
    "No. of People",
    "Gender",
    "Age",
    "Ethnicity",
    "Alpha Channel",
    "Looped",
    "Source Audio",
    "Location",
]


def missing_fields(item: VideoItem) -> list[str]:
    """The pipeline fields a clip is still missing, for an export warning."""
    missing = []
    if not item.title:
        missing.append("Title")
    if not item.description:
        missing.append("Description")
    if not item.tags:
        missing.append("Keywords")
    if not item.category:
        missing.append("Category")
    return missing


def build_row(item: VideoItem) -> dict:
    row = {column: "" for column in COLUMNS}
    row["Filename"] = item.export_filename
    row["Title"] = item.title or ""
    # Fall back to the title when there's no description, so the column is never
    # blank on an otherwise-complete row.
    row["Description"] = item.description or item.title or ""
    row["Keywords"] = item.tags or ""
    row["Category"] = item.category or ""
    row["Price: Single Use License ($USD)"] = PRICE_SINGLE_USE
    row["Price: Multi-use License ($USD)"] = PRICE_MULTI_USE
    return row


def write_csv(items: list[VideoItem], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow(build_row(item))
