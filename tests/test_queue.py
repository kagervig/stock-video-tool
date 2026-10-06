"""Tests for the convert/strip-audio queue processing."""

from __future__ import annotations

from pathlib import Path

import pytest

from stock_video_tool import workers
from stock_video_tool.core import ffmpeg
from stock_video_tool.core.models import QueueOp, VideoItem
from tests.conftest import requires_ffmpeg


def test_output_path_for_convert_is_mov():
    item = VideoItem(path=Path("/videos/clip.mp4"))
    item.queue_op = QueueOp.CONVERT
    out = workers.output_path_for(item)
    assert out == Path("/videos/converted/clip.mov")


def test_output_path_for_strip_keeps_original_extension():
    item = VideoItem(path=Path("/videos/clip.mkv"))
    item.queue_op = QueueOp.STRIP_AUDIO
    out = workers.output_path_for(item)
    assert out == Path("/videos/converted/clip.mkv")


def test_process_item_without_op_raises():
    item = VideoItem(path=Path("/videos/clip.mp4"))  # queue_op defaults to NONE
    with pytest.raises(ValueError):
        workers.process_item(item)


@requires_ffmpeg
def test_process_item_converts_hevc_to_h264_muted(hevc_no_audio, tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(hevc_no_audio.read_bytes())
    item = VideoItem(path=src)
    item.queue_op = QueueOp.CONVERT
    out = workers.process_item(item)
    assert out.exists()
    result = ffmpeg.probe(out)
    assert result.codec == "h264"
    assert result.has_audio is False


@requires_ffmpeg
def test_process_item_strips_audio_from_h264(h264_with_audio, tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(h264_with_audio.read_bytes())
    item = VideoItem(path=src)
    item.queue_op = QueueOp.STRIP_AUDIO
    out = workers.process_item(item)
    assert out.exists()
    assert ffmpeg.probe(out).has_audio is False
