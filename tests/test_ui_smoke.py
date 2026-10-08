"""Offscreen smoke tests for the extracted UI panels.

These don't assert pixels — they construct each widget offscreen and exercise
the state-in methods, which catches the class of bug that bit this app before
(signals GC'd, editors repopulated from stale items, buttons desynced). Run
with the offscreen platform so no display is needed:

    QT_QPA_PLATFORM=offscreen pytest tests/test_ui_smoke.py

Scaffold: fill these in as you build the panels. Keep each test to one
behaviour (see .claude/rules/testing.md).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.skip(reason="scaffold — implement during refactor")


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the test session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ---- VideoListPanel -----------------------------------------------------

def test_video_list_panel_constructs(qapp):
    raise NotImplementedError


def test_video_list_panel_set_rows_populates_list(qapp):
    raise NotImplementedError


def test_video_list_panel_set_queue_summary_updates_label(qapp):
    raise NotImplementedError


# ---- DetailPanel --------------------------------------------------------

def test_detail_panel_constructs(qapp):
    raise NotImplementedError


def test_detail_panel_show_item_populates_editors(qapp):
    raise NotImplementedError


def test_detail_panel_show_none_clears_and_disables(qapp):
    raise NotImplementedError


def test_detail_panel_read_into_commits_editor_text(qapp):
    """Editing then read_into(item) writes description/title/tags/category."""
    raise NotImplementedError
