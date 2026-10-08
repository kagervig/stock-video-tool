"""Tests for core.presentation — pure display-string logic.

Scaffold: each test names a behaviour to cover during the refactor. Remove the
skip marker and fill in Arrange/Act/Assert as you implement each function. Build
VideoItem instances directly (see tests/test_queue.py for the pattern) — no Qt,
no filesystem needed except where a real file size matters.
"""

from __future__ import annotations
from pathlib import Path
from stock_video_tool.core import presentation

import pytest


# ---- is_video -----------------------------------------------------------

def test_is_video_true_for_known_suffix():
    assert presentation.is_video(Path("/videos/clip.mp4")) is True


def test_is_video_false_for_non_video():
    assert presentation.is_video(Path("/videos/notes.txt")) is False


def test_is_video_is_case_insensitive():
    assert presentation.is_video(Path("/videos/CLIP.MOV")) is True

def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES

# ---- row_label ----------------------------------------------------------

def test_row_label_shows_analyzing_before_probe():
    """codec is None -> "<name>  [analyzing…]"."""
    raise NotImplementedError


def test_row_label_marks_description_title_tags():
    """description/title/tags set -> D / T / K marks."""
    raise NotImplementedError


def test_row_label_shows_running_steps():
    """item.running -> "⋯ <sorted steps>" mark."""
    raise NotImplementedError


def test_row_label_marks_h265():
    raise NotImplementedError


def test_row_label_marks_audio_when_not_h265():
    raise NotImplementedError


def test_row_label_shows_convert_status_glyph():
    """QUEUED/CONVERTING/DONE/FAILED each render their glyph."""
    raise NotImplementedError


def test_row_label_plain_name_when_no_marks():
    raise NotImplementedError


# ---- queue_summary ------------------------------------------------------

def test_queue_summary_empty_when_nothing_queued():
    raise NotImplementedError


def test_queue_summary_counts_converts_and_strips():
    raise NotImplementedError


# ---- tag_count_display --------------------------------------------------

def test_tag_count_gray_below_target():
    raise NotImplementedError


def test_tag_count_green_at_target():
    raise NotImplementedError


def test_tag_count_amber_past_target_within_limit():
    raise NotImplementedError


def test_tag_count_red_and_remove_n_over_limit():
    raise NotImplementedError
