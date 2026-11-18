"""Write a stock-video import CSV in the Envato or Shutterstock format.

One row per clip. Envato's Filename is the processed output (converted/stripped)
when there is one, since Envato needs the re-encoded file; Shutterstock accepts
H265, so its Filename is always the original. Title, Description, Keywords, and
Category come from the pipeline. The two formats differ only in their columns
and how the pipeline fields map onto them; see ENVATO and SHUTTERSTOCK.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
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
        excess = orc.tags_over_limit(len(orc.parse_tags(item.tags or "")))
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


SHUTTERSTOCK_COLUMNS = [
    "Filename",
    "Description",
    "Keywords",
    "Categories",
    "Editorial",
    "Mature content",
    "illustration",
]

# Map each Envato pipeline category onto a Shutterstock category. Envato's
# capture-technique categories (Overhead, Slow Motion, Stop Motion, Time Lapse)
# have no Shutterstock subject equivalent and are left out, so they fall through
# to a blank Categories column.
ENVATO_TO_SHUTTERSTOCK_CATEGORY = {
    "Buildings": "Buildings/Landmarks",
    "City": "Buildings/Landmarks",
    "Business": "Business/Finance",
    "Corporate": "Business/Finance",
    "Construction": "Industrial",
    "Industrial": "Industrial",
    "Education": "Education",
    "Food": "Food and drink",
    "Holidays": "Holidays",
    "Special Events": "Holidays",
    "Kids": "People",
    "People": "People",
    "Lifestyle": "People",
    "Military": "People",
    "Medical": "Healthcare/Medical",
    "Nature": "Nature",
    "Weather": "Nature",
    "Religious": "Religion",
    "Sports": "Sports/Recreation",
    "Technology": "Technology",
    "Vehicles": "Transportation",
    "Science": "Science",
    "Cartoons": "Arts",
}

# The marketplace's own category list for the detail-panel dropdown. Derived
# from the map's targets so it stays in lockstep with the translation above;
# every entry therefore has a reverse mapping back to Envato.
SHUTTERSTOCK_CATEGORIES = sorted(set(ENVATO_TO_SHUTTERSTOCK_CATEGORY.values()))

# Characters Shutterstock rejects in text fields (e.g. the title).
SHUTTERSTOCK_FORBIDDEN_CHARS = ("<", ">", "/", "&")


def forbidden_shutterstock_chars(text: str) -> list[str]:
    """Which Shutterstock-forbidden characters appear in text, in rule order."""
    return [char for char in SHUTTERSTOCK_FORBIDDEN_CHARS if char in (text or "")]


def build_shutterstock_row(item: VideoItem) -> dict:
    row = {column: "" for column in SHUTTERSTOCK_COLUMNS}
    # Shutterstock accepts H265, so the original file is uploaded as-is — unlike
    # Envato, it never points at the re-encoded "converted" output.
    row["Filename"] = item.filename
    # Shutterstock has no Title column — its Description field is the headline, so
    # the pipeline Title goes there, falling back to the description if unset.
    row["Description"] = item.title or item.description or ""
    row["Keywords"] = item.tags or ""
    row["Categories"] = ENVATO_TO_SHUTTERSTOCK_CATEGORY.get(item.category or "", "")
    row["Editorial"] = "no"
    row["Mature content"] = "no"
    row["illustration"] = "no"
    return row


@dataclass(frozen=True)
class ExportFormat:
    """A marketplace CSV layout: its columns and how a clip maps onto a row."""

    name: str
    columns: list[str]
    build_row: Callable[[VideoItem], dict]
    filename_prefix: str


ENVATO = ExportFormat("Envato", COLUMNS, build_row, "envato_export")
SHUTTERSTOCK = ExportFormat(
    "Shutterstock", SHUTTERSTOCK_COLUMNS, build_shutterstock_row, "shutterstock_export"
)

FORMATS = {fmt.name: fmt for fmt in (ENVATO, SHUTTERSTOCK)}


def write_csv(items: list[VideoItem], path: Path, fmt: ExportFormat = ENVATO) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fmt.columns)
        writer.writeheader()
        for item in items:
            writer.writerow(fmt.build_row(item))
