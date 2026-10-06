"""Tests for VideoItem derived properties."""

from __future__ import annotations

from pathlib import Path

from stock_video_tool.core.models import VideoItem


def test_size_mb_reports_file_size_in_megabytes(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\0" * (2 * 1024 * 1024))
    item = VideoItem(path=src)
    assert item.size_mb == 2.0


def test_size_mb_is_none_when_file_missing():
    item = VideoItem(path=Path("/videos/does-not-exist.mp4"))
    assert item.size_mb is None
