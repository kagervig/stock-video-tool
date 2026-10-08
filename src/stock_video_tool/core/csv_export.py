"""Write the Envato stock-video import CSV.

One row per clip. Filename is the processed output (converted/stripped) when
there is one, otherwise the original file. Title, Description, Keywords, and
Category come from the pipeline; prices are fixed; every other column is blank.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import PRICE_MULTI_USE, PRICE_SINGLE_USE, VideoItem
from . import openrouter as orc

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


def over_limit_report(items: list[VideoItem]) -> list[str]:
    """Per-clip lines for clips whose keywords exceed the hard limit.

    One formatted line per offending clip, e.g. "  • clip.mp4: remove 3".
    Empty list when every clip is within the limit (the export can proceed).

    SOURCE: the first loop in main_window._export_csv (the `over` list).
    Uses openrouter.parse_tags / tags_over_limit.
    """
    over = []
    for item in items:
        excess = orc.tags_over_limit(len(orc.parse_tags (item.tags or "")))
        if excess:
            over.append(f"  • {item.filename}: remove {excess}")
    return over


def incomplete_report(items: list[VideoItem]) -> list[str]:
    """Per-clip lines for clips still missing pipeline fields.

    One formatted line per clip with gaps, e.g.
    "  • clip.mp4: missing Title, Keywords". Empty list when all complete.

    SOURCE: the second loop in main_window._export_csv (the `incomplete` list).
    Uses missing_fields.
    """
    incomplete = []
    for item in items:
        missing = missing_fields(item)
        if missing:
            incomplete.append(f"  • {item.filename}: missing {', '.join(missing)}")
    return incomplete


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
