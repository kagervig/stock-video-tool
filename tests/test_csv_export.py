"""Tests for core.csv_export — column order and row mapping."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from stock_video_tool.core import csv_export
from stock_video_tool.core.models import VideoItem


def _item() -> VideoItem:
    item = VideoItem(path=Path("/videos/clip.mp4"))
    item.title = "Forest Stream 4K"
    item.description = "A calm forest stream."
    item.tags = "forest, stream, water"
    item.category = "Nature"
    return item


def test_columns_match_the_envato_header_in_order():
    assert csv_export.COLUMNS[:7] == [
        "Filename", "Title", "Description", "Keywords", "Category",
        "Price: Single Use License ($USD)", "Price: Multi-use License ($USD)",
    ]
    assert csv_export.COLUMNS[-1] == "Location"
    assert len(csv_export.COLUMNS) == 25


def test_build_row_maps_pipeline_fields():
    row = csv_export.build_row(_item())
    assert row["Title"] == "Forest Stream 4K"
    assert row["Description"] == "A calm forest stream."
    assert row["Keywords"] == "forest, stream, water"
    assert row["Category"] == "Nature"


def test_build_row_description_falls_back_to_title_when_empty():
    item = _item()
    item.description = None
    assert csv_export.build_row(item)["Description"] == "Forest Stream 4K"


def test_build_row_uses_fixed_prices():
    row = csv_export.build_row(_item())
    assert row["Price: Single Use License ($USD)"] == 11
    assert row["Price: Multi-use License ($USD)"] == 22


def test_build_row_filename_is_original_when_not_processed():
    row = csv_export.build_row(_item())
    assert row["Filename"] == "clip.mp4"


def test_build_row_filename_is_processed_output_when_present():
    item = _item()
    item.output_path = Path("/videos/converted/clip.mov")
    assert csv_export.build_row(item)["Filename"] == "clip.mov"


def test_build_row_leaves_other_columns_blank():
    row = csv_export.build_row(_item())
    for column in ("Color", "Pace", "Setting", "Location", "Releases"):
        assert row[column] == ""


def test_missing_fields_empty_for_complete_item():
    item = _item()
    assert csv_export.missing_fields(item) == []


def test_missing_fields_lists_each_empty_field():
    item = VideoItem(path=Path("/videos/clip.mp4"))  # nothing filled in
    assert csv_export.missing_fields(item) == [
        "Title", "Description", "Keywords", "Category",
    ]


def test_write_csv_round_trips_with_quoted_keywords(tmp_path):
    out = tmp_path / "export.csv"
    csv_export.write_csv([_item()], out)
    with out.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    # keywords contain commas but must stay in a single cell
    assert rows[0]["Keywords"] == "forest, stream, water"
    assert rows[0]["Price: Single Use License ($USD)"] == "11"


def test_write_csv_writes_header_only_for_empty_list(tmp_path):
    out = tmp_path / "empty.csv"
    csv_export.write_csv([], out)
    with out.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [csv_export.COLUMNS]


# ---- export blockers (scaffold — implement during refactor) -------------

@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_over_limit_report_empty_when_all_within_limit():
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_over_limit_report_lists_clips_over_the_limit():
    """One "  • <name>: remove N" line per offending clip."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_incomplete_report_empty_when_all_complete():
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_incomplete_report_lists_missing_fields_per_clip():
    """One "  • <name>: missing <fields>" line per clip with gaps."""
    raise NotImplementedError
