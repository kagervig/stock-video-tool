"""Offscreen tests for MainWindow behaviour that isn't covered by the pure
core tests. Run with the offscreen platform so no display is needed:

    QT_QPA_PLATFORM=offscreen pytest tests/test_main_window.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the test session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_navigating_to_untitled_clip_does_not_inherit_previous_title(qapp):
    """A clip whose title is pure line-edit text (no candidates) must not leak
    into the next clip's title field when switching rows."""
    from stock_video_tool.core.models import VideoItem
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    titled = VideoItem(path=Path("/videos/a.mp4"))
    titled.title = "Sunset Beach"  # title with no candidates -> line-edit text only
    untitled = VideoItem(path=Path("/videos/b.mp4"))
    window.items = [titled, untitled]
    window._rebuild_list()

    window.list.setCurrentRow(0)
    window.list.setCurrentRow(1)

    assert window.title_combo.currentText() == ""


def test_generated_titles_apply_to_a_clip_that_is_not_on_screen(qapp, monkeypatch):
    """A titles result that arrives after the user switched clips must still set
    the originating clip's title, not just stash the candidate list."""
    from stock_video_tool.core.models import VideoItem
    from stock_video_tool.core.openrouter import ChatResult
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    monkeypatch.setattr(window.stats, "record", lambda *a, **k: None)
    generating = VideoItem(path=Path("/videos/a.mp4"))
    other = VideoItem(path=Path("/videos/b.mp4"))
    window.items = [generating, other]
    window._rebuild_list()
    window.list.setCurrentRow(1)  # the user has navigated to a different clip

    window._apply_titles(
        generating, (["First", "Second"], ChatResult(text="", cost=0.0, model="m"))
    )

    assert generating.title == "First"


def test_duplicate_filename_rows_are_painted_red(qapp):
    """Two loaded clips sharing a filename are highlighted red in the list."""
    from PySide6.QtGui import QColor

    from stock_video_tool.core.models import VideoItem
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    window.items = [VideoItem(path=Path("/a/clip.mp4")), VideoItem(path=Path("/b/clip.mp4"))]
    window._rebuild_list()

    assert window.list.item(0).foreground().color() == QColor("#c62828")


def test_unique_filename_rows_are_not_painted_red(qapp):
    from PySide6.QtGui import QColor

    from stock_video_tool.core.models import VideoItem
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    window.items = [VideoItem(path=Path("/a/one.mp4")), VideoItem(path=Path("/b/two.mp4"))]
    window._rebuild_list()

    assert window.list.item(0).foreground().color() != QColor("#c62828")


def test_title_with_forbidden_chars_is_flagged_in_shutterstock_mode(qapp):
    """A title containing a Shutterstock-forbidden char highlights the title box."""
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    window.marketplace = "Shutterstock"
    window.title_combo.setCurrentText("Rock & Roll")

    assert window.title_combo.styleSheet() != ""


def test_title_with_forbidden_chars_is_not_flagged_in_envato_mode(qapp):
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    window.marketplace = "Envato"
    window.title_combo.setCurrentText("Rock & Roll")

    assert window.title_combo.styleSheet() == ""


def test_queue_selected_queues_every_selected_processable_clip(qapp):
    """Selecting multiple clips and clicking once queues all that need work."""
    from stock_video_tool.core.models import ConvertStatus, VideoItem
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    a = VideoItem(path=Path("/v/a.mp4"))
    a.has_audio = True  # -> planned_op STRIP_AUDIO
    b = VideoItem(path=Path("/v/b.mp4"))
    b.has_audio = True
    window.items = [a, b]
    window._rebuild_list()
    window.list.selectAll()

    window._queue_selected()

    assert [a.convert_status, b.convert_status] == [
        ConvertStatus.QUEUED, ConvertStatus.QUEUED,
    ]


def test_queue_selected_skips_clips_that_need_no_processing(qapp):
    from stock_video_tool.core.models import ConvertStatus, VideoItem
    from stock_video_tool.ui.main_window import MainWindow

    window = MainWindow()
    clean = VideoItem(path=Path("/v/clean.mp4"))  # no audio, not H265 -> no op
    window.items = [clean]
    window._rebuild_list()
    window.list.selectAll()

    window._queue_selected()

    assert clean.convert_status == ConvertStatus.NONE
