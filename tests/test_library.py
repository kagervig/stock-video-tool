"""Tests for core.library — persistence and field restore keyed by filename."""

from __future__ import annotations

from pathlib import Path

from stock_video_tool.core import library as lib
from stock_video_tool.core.models import Stage, VideoItem


def _library(tmp_path: Path) -> lib.Library:
    return lib.Library(path=tmp_path / "library.json")


def test_lookup_returns_none_for_unseen_filename(tmp_path):
    assert _library(tmp_path).lookup("clip.mp4") is None


def test_record_then_lookup_round_trips(tmp_path):
    store = _library(tmp_path)
    store.record("clip.mp4", {"description": "a sunset", "tags": "sun, sky"})
    assert store.lookup("clip.mp4")["description"] == "a sunset"


def test_data_persists_across_instances(tmp_path):
    path = tmp_path / "library.json"
    lib.Library(path=path).record("clip.mp4", {"title": "Sunset 4K"})
    assert lib.Library(path=path).lookup("clip.mp4")["title"] == "Sunset 4K"


def test_item_fields_captures_ai_fields_only():
    item = VideoItem(path=Path("/videos/clip.mp4"))
    item.description = "a sunset"
    item.title = "Sunset 4K"
    item.title_candidates = ["Sunset 4K", "Golden Hour"]
    item.tags = "sun, sky"
    item.category = "Nature"
    fields = lib.item_fields(item)
    assert fields == {
        "description": "a sunset",
        "title": "Sunset 4K",
        "title_candidates": ["Sunset 4K", "Golden Hour"],
        "tags": "sun, sky",
        "category": "Nature",
    }


def test_apply_fields_restores_values():
    item = VideoItem(path=Path("/videos/clip.mp4"))
    lib.apply_fields(item, {"description": "a sunset", "tags": "sun, sky"})
    assert item.description == "a sunset"
    assert item.tags == "sun, sky"


def test_apply_fields_sets_tagged_stage_when_tags_present():
    item = VideoItem(path=Path("/videos/clip.mp4"))
    lib.apply_fields(item, {"description": "d", "title": "t", "tags": "a, b"})
    assert item.stage is Stage.TAGGED


def test_apply_fields_sets_described_stage_when_only_description():
    item = VideoItem(path=Path("/videos/clip.mp4"))
    lib.apply_fields(item, {"description": "a sunset"})
    assert item.stage is Stage.DESCRIBED


def test_has_data_false_for_all_empty():
    assert lib.has_data({"description": None, "tags": "", "title_candidates": []}) is False


def test_has_data_true_when_any_field_present():
    assert lib.has_data({"description": "x", "title_candidates": []}) is True
