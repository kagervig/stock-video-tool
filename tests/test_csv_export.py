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


# ---- Shutterstock format -------------------------------------------------

def test_shutterstock_columns_match_the_template_header_in_order():
    assert csv_export.SHUTTERSTOCK_COLUMNS == [
        "Filename", "Description", "Keywords", "Categories",
        "Editorial", "Mature content", "illustration",
    ]


def test_shutterstock_row_puts_the_title_in_the_description_column():
    # Shutterstock has no Title column; its Description field is the headline,
    # so the pipeline Title goes there.
    assert csv_export.build_shutterstock_row(_item())["Description"] == "Forest Stream 4K"


def test_shutterstock_row_maps_keywords_into_the_keywords_column():
    assert csv_export.build_shutterstock_row(_item())["Keywords"] == "forest, stream, water"


def test_shutterstock_row_description_column_falls_back_to_description_when_no_title():
    item = _item()
    item.title = None
    assert csv_export.build_shutterstock_row(item)["Description"] == "A calm forest stream."


def test_shutterstock_row_uses_original_filename_even_when_processed():
    item = _item()
    item.output_path = Path("/videos/converted/clip.mov")
    # Shutterstock accepts H265, so the original is uploaded, not the re-encode.
    assert csv_export.build_shutterstock_row(item)["Filename"] == "clip.mp4"


def test_shutterstock_row_maps_envato_category_to_shutterstock():
    item = _item()
    item.category = "Vehicles"
    assert csv_export.build_shutterstock_row(item)["Categories"] == "Transportation"


def test_shutterstock_row_leaves_category_blank_when_unmapped():
    item = _item()
    item.category = "Time Lapse"  # capture technique, no Shutterstock equivalent
    assert csv_export.build_shutterstock_row(item)["Categories"] == ""


def test_shutterstock_row_defaults_flag_columns_to_no():
    row = csv_export.build_shutterstock_row(_item())
    assert [row["Editorial"], row["Mature content"], row["illustration"]] == [
        "no", "no", "no",
    ]


def test_write_csv_uses_shutterstock_columns_when_given_that_format(tmp_path):
    out = tmp_path / "shutterstock.csv"
    csv_export.write_csv([_item()], out, csv_export.SHUTTERSTOCK)
    with out.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["Categories"] == "Nature"


def test_shutterstock_categories_are_the_distinct_map_targets_sorted():
    assert csv_export.SHUTTERSTOCK_CATEGORIES == sorted(
        set(csv_export.ENVATO_TO_SHUTTERSTOCK_CATEGORY.values())
    )


def test_every_shutterstock_category_maps_back_to_envato():
    for category in csv_export.SHUTTERSTOCK_CATEGORIES:
        assert category in csv_export.ENVATO_TO_SHUTTERSTOCK_CATEGORY.values()


def test_forbidden_shutterstock_chars_empty_for_clean_text():
    assert csv_export.forbidden_shutterstock_chars("Forest Stream 4K") == []


def test_forbidden_shutterstock_chars_lists_present_chars_in_rule_order():
    assert csv_export.forbidden_shutterstock_chars("A & B > C / D") == [">", "/", "&"]


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
