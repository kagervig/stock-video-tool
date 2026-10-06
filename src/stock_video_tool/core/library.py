"""Local persistence of generated AI fields, keyed by filename.

Thumbnails and codec/stats are never stored — they are regenerated on drop.
Only the text fields the user generated or edited are kept, so re-adding a
file by the same name restores its description, titles, tags, and category.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import APP_SUPPORT_DIR
from .models import Stage, VideoItem

LIBRARY_PATH = APP_SUPPORT_DIR / "library.json"


def item_fields(item: VideoItem) -> dict:
    """The persistable AI fields of an item."""
    return {
        "description": item.description,
        "title": item.title,
        "title_candidates": list(item.title_candidates),
        "tags": item.tags,
        "category": item.category,
    }


def has_data(fields: dict) -> bool:
    """True if any AI field holds content worth saving."""
    return any(
        fields.get(k) for k in ("description", "title", "tags", "category")
    ) or bool(fields.get("title_candidates"))


def apply_fields(item: VideoItem, data: dict) -> None:
    """Restore stored fields onto an item and set its stage accordingly."""
    item.description = data.get("description")
    item.title = data.get("title")
    item.title_candidates = list(data.get("title_candidates") or [])
    item.tags = data.get("tags")
    item.category = data.get("category")
    item.stage = _stage_for(item)


def _stage_for(item: VideoItem) -> Stage:
    if item.tags:
        return Stage.TAGGED
    if item.title:
        return Stage.TITLED
    if item.description:
        return Stage.DESCRIBED
    return Stage.NEW


class Library:
    def __init__(self, path: Path | str = LIBRARY_PATH) -> None:
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self._data = {}

    def lookup(self, filename: str) -> dict | None:
        return self._data.get(filename)

    def record(self, filename: str, fields: dict) -> None:
        self._data[filename] = fields
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))
