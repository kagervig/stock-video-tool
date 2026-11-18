"""Tests for core.csv_import — format detection, reverse mapping, row parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from stock_video_tool.core import csv_export, csv_import
from stock_video_tool.core.csv_import import TitlePolicy


def _write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    import csv

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


# ---- format detection ----------------------------------------------------

def test_detect_format_recognizes_envato_header():
    assert csv_import.detect_format(csv_export.COLUMNS) is csv_export.ENVATO


def test_detect_format_recognizes_shutterstock_header():
    assert csv_import.detect_format(csv_export.SHUTTERSTOCK_COLUMNS) is csv_export.SHUTTERSTOCK


def test_detect_format_returns_none_for_unknown_header():
    assert csv_import.detect_format(["foo", "bar"]) is None


def test_read_csv_raises_on_unrecognized_header(tmp_path):
    path = _write(tmp_path / "bad.csv", ["foo", "bar"], [["1", "2"]])
    with pytest.raises(ValueError):
        csv_import.read_csv(path)


def test_read_csv_returns_format_and_rows(tmp_path):
    path = tmp_path / "ss.csv"
    csv_export.write_csv([], path, csv_export.SHUTTERSTOCK)
    fmt, rows = csv_import.read_csv(path)
    assert fmt is csv_export.SHUTTERSTOCK


# ---- inverse category map ------------------------------------------------

def test_inverse_map_lists_all_envato_sources_for_a_shutterstock_category():
    assert csv_import.SHUTTERSTOCK_TO_ENVATO["People"] == [
        "Kids", "People", "Lifestyle", "Military",
    ]


def test_resolve_category_auto_resolves_single_candidate():
    assert csv_import.resolve_envato_category("Transportation") == "Vehicles"


def test_resolve_category_uses_choice_for_ambiguous():
    resolved = csv_import.resolve_envato_category("People", {"People": "Kids"})
    assert resolved == "Kids"


def test_resolve_category_blank_for_ambiguous_without_choice():
    assert csv_import.resolve_envato_category("People") == ""


def test_resolve_category_blank_for_unmapped():
    assert csv_import.resolve_envato_category("Not A Category") == ""


def test_choice_returns_single_candidate_for_unambiguous_category():
    assert csv_import.envato_for_shutterstock_choice("Transportation", None) == "Vehicles"


def test_choice_keeps_current_envato_when_it_still_fits():
    assert csv_import.envato_for_shutterstock_choice("People", "Military") == "Military"


def test_choice_falls_to_first_candidate_when_current_does_not_fit():
    assert csv_import.envato_for_shutterstock_choice("People", "Nature") == "Kids"


def test_choice_blank_for_unmapped_category():
    assert csv_import.envato_for_shutterstock_choice("Not A Category", "Nature") == ""


def test_ambiguous_categories_omits_single_candidate_and_blank():
    rows = [
        {"Categories": "Transportation"},  # single candidate -> auto
        {"Categories": "People"},          # multiple -> needs a pick
        {"Categories": ""},                # blank -> skipped
    ]
    assert list(csv_import.ambiguous_shutterstock_categories(rows)) == ["People"]


# ---- row -> item ----------------------------------------------------------

def _envato_row() -> dict:
    return {
        "Filename": "clip.mov",
        "Title": "Forest Stream 4K",
        "Description": "A calm forest stream.",
        "Keywords": "forest, stream",
        "Category": "Nature",
    }


def test_item_from_envato_row_maps_all_fields():
    item = csv_import.item_from_row(_envato_row(), csv_export.ENVATO)
    assert (item.filename, item.title, item.description, item.tags, item.category) == (
        "clip.mov", "Forest Stream 4K", "A calm forest stream.", "forest, stream", "Nature",
    )


def test_item_from_shutterstock_row_reverse_maps_category():
    row = {"Filename": "clip.mov", "Description": "d", "Keywords": "k",
           "Categories": "Transportation"}
    item = csv_import.item_from_row(row, csv_export.SHUTTERSTOCK)
    assert item.category == "Vehicles"


def test_item_from_shutterstock_row_leaves_title_blank_by_default():
    row = {"Filename": "clip.mov", "Description": "d", "Keywords": "k", "Categories": ""}
    item = csv_import.item_from_row(row, csv_export.SHUTTERSTOCK)
    assert item.title is None


def test_item_from_shutterstock_row_uses_description_as_title_when_asked():
    row = {"Filename": "clip.mov", "Description": "d", "Keywords": "k", "Categories": ""}
    item = csv_import.item_from_row(
        row, csv_export.SHUTTERSTOCK, title_policy=TitlePolicy.USE_DESCRIPTION,
    )
    assert item.title == "d"


def test_blank_columns_become_none():
    row = {"Filename": "clip.mov", "Title": "", "Description": "",
           "Keywords": "", "Category": ""}
    item = csv_import.item_from_row(row, csv_export.ENVATO)
    assert [item.title, item.description, item.tags, item.category] == [
        None, None, None, None,
    ]


# ---- round-trip through the writer ---------------------------------------

def test_envato_to_shutterstock_round_trip_preserves_clean_fields(tmp_path):
    src = tmp_path / "envato.csv"
    item = csv_import.item_from_row(_envato_row(), csv_export.ENVATO)
    csv_export.write_csv([item], src, csv_export.ENVATO)

    fmt, rows = csv_import.read_csv(src)
    out_items = csv_import.items_from_rows(rows, fmt)
    out = tmp_path / "shutterstock.csv"
    csv_export.write_csv(out_items, out, csv_export.SHUTTERSTOCK)

    _, ss_rows = csv_import.read_csv(out)
    assert ss_rows[0]["Keywords"] == "forest, stream"
    assert ss_rows[0]["Categories"] == "Nature"
