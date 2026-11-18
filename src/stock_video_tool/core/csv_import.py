"""Read an Envato or Shutterstock CSV back into VideoItems.

The inverse of csv_export: detect which marketplace a CSV came from, then turn
each row into a normalized VideoItem (Envato-style category, Title present) that
can be re-exported in the other format or matched onto loaded clips.

The Shutterstock -> Envato direction is lossy: Shutterstock has no Title, and a
Shutterstock category can map back to several Envato categories. Those gaps are
resolved by the caller (see ui.import_dialog) via category_choices and
title_policy; unresolved gaps fall through to blank and are flagged downstream.
"""

from __future__ import annotations

import csv
from enum import Enum
from pathlib import Path

from .models import VideoItem
from . import csv_export
from .csv_export import ExportFormat


class TitlePolicy(str, Enum):
    """How to fill the Envato Title column when importing a Shutterstock CSV."""

    USE_DESCRIPTION = "use_description"
    LEAVE_BLANK = "leave_blank"


def _invert_category_map() -> dict[str, list[str]]:
    """Shutterstock category -> the Envato categories that map onto it.

    Built from csv_export.ENVATO_TO_SHUTTERSTOCK_CATEGORY, so the two stay in
    lockstep. Candidate order follows that map's insertion order.
    """
    inverse: dict[str, list[str]] = {}
    for envato, shutterstock in csv_export.ENVATO_TO_SHUTTERSTOCK_CATEGORY.items():
        inverse.setdefault(shutterstock, []).append(envato)
    return inverse


SHUTTERSTOCK_TO_ENVATO = _invert_category_map()


def detect_format(header: list[str]) -> ExportFormat | None:
    """The ExportFormat whose columns match this header, or None if neither."""
    normalized = [column.strip() for column in header]
    for fmt in csv_export.FORMATS.values():
        if normalized == fmt.columns:
            return fmt
    return None


def read_csv(path: Path) -> tuple[ExportFormat, list[dict]]:
    """Parse a CSV and identify its format. Raises ValueError on an unknown header."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fmt = detect_format(reader.fieldnames or [])
        if fmt is None:
            raise ValueError(
                "Unrecognized CSV header — expected an Envato or Shutterstock export."
            )
        rows = list(reader)
    return fmt, rows


def _primary_shutterstock_category(value: str | None) -> str:
    """The first of Shutterstock's (up to two) comma-separated categories.

    Envato allows a single category, so only the first is carried across.
    """
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            return part
    return ""


def resolve_envato_category(
    shutterstock_category: str, choices: dict[str, str] | None = None
) -> str:
    """Map a Shutterstock category back to an Envato one.

    Auto-resolves when there's a single candidate; uses `choices` for ambiguous
    categories; returns "" for unmapped or unresolved-ambiguous categories.
    """
    candidates = SHUTTERSTOCK_TO_ENVATO.get(shutterstock_category, [])
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]
    if choices and shutterstock_category in choices:
        return choices[shutterstock_category]
    return ""


def envato_for_shutterstock_choice(
    shutterstock_category: str, current_envato: str | None
) -> str:
    """The Envato category to store when a Shutterstock category is picked in the UI.

    Keeps the clip's current Envato value when it already maps onto the chosen
    Shutterstock category, so switching marketplaces doesn't discard a specific
    pick (e.g. Kids vs People, which share the Shutterstock "People"). Otherwise
    falls to the first candidate; returns "" for an unmapped category.
    """
    candidates = SHUTTERSTOCK_TO_ENVATO.get(shutterstock_category, [])
    if not candidates:
        return ""
    if current_envato in candidates:
        return current_envato
    return candidates[0]


def ambiguous_shutterstock_categories(rows: list[dict]) -> dict[str, list[str]]:
    """Distinct Shutterstock categories in `rows` that need a manual pick.

    Maps each such category to its Envato candidates. Categories with a single
    candidate (auto-resolved) or none (blank) are omitted.
    """
    present = {_primary_shutterstock_category(row.get("Categories")) for row in rows}
    return {
        category: SHUTTERSTOCK_TO_ENVATO[category]
        for category in present
        if category and len(SHUTTERSTOCK_TO_ENVATO.get(category, [])) > 1
    }


def item_from_row(
    row: dict,
    fmt: ExportFormat,
    *,
    category_choices: dict[str, str] | None = None,
    title_policy: TitlePolicy = TitlePolicy.LEAVE_BLANK,
) -> VideoItem:
    """Build a normalized VideoItem from one CSV row.

    The result always uses the app's Envato-style category and carries a Title,
    so it can be re-exported in either format or applied to a loaded clip.
    """
    item = VideoItem(path=Path(row.get("Filename") or ""))
    item.description = (row.get("Description") or "") or None
    item.tags = (row.get("Keywords") or "") or None
    if fmt is csv_export.ENVATO:
        item.title = (row.get("Title") or "") or None
        item.category = (row.get("Category") or "") or None
        return item

    # Shutterstock: no Title column, Categories need the reverse mapping.
    shutterstock_category = _primary_shutterstock_category(row.get("Categories"))
    item.category = resolve_envato_category(shutterstock_category, category_choices) or None
    if title_policy is TitlePolicy.USE_DESCRIPTION:
        item.title = item.description
    return item


def items_from_rows(
    rows: list[dict],
    fmt: ExportFormat,
    *,
    category_choices: dict[str, str] | None = None,
    title_policy: TitlePolicy = TitlePolicy.LEAVE_BLANK,
) -> list[VideoItem]:
    return [
        item_from_row(
            row, fmt, category_choices=category_choices, title_policy=title_policy
        )
        for row in rows
    ]
