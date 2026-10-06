"""Tests for core.ffmpeg — ffprobe parsing, command builders, and real runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from stock_video_tool.core import ffmpeg
from tests.conftest import requires_ffmpeg

# --- parse_probe (pure, no ffmpeg needed) ---------------------------------

_PROBE_H264_AUDIO = {
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
    "format": {"duration": "12.5"},
}

_PROBE_HEVC_SILENT = {
    "streams": [
        {"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 2160},
    ],
    "format": {"duration": "8.0"},
}


def test_parse_probe_reads_video_codec_and_size():
    result = ffmpeg.parse_probe(_PROBE_H264_AUDIO)
    assert result.codec == "h264"
    assert result.width == 1920
    assert result.height == 1080


def test_parse_probe_reads_duration_as_float():
    result = ffmpeg.parse_probe(_PROBE_H264_AUDIO)
    assert result.duration == pytest.approx(12.5)


def test_parse_probe_detects_audio_track_present():
    result = ffmpeg.parse_probe(_PROBE_H264_AUDIO)
    assert result.has_audio is True


def test_parse_probe_detects_audio_track_absent():
    result = ffmpeg.parse_probe(_PROBE_HEVC_SILENT)
    assert result.has_audio is False


def test_parse_probe_reads_hevc_codec():
    result = ffmpeg.parse_probe(_PROBE_HEVC_SILENT)
    assert result.codec == "hevc"


def test_parse_probe_raises_when_no_video_stream():
    data = {"streams": [{"codec_type": "audio", "codec_name": "aac"}], "format": {}}
    with pytest.raises(ffmpeg.FfmpegError):
        ffmpeg.parse_probe(data)


def test_parse_probe_falls_back_to_stream_duration():
    data = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 10,
             "height": 10, "duration": "5.0"},
        ],
        "format": {},
    }
    assert ffmpeg.parse_probe(data).duration == pytest.approx(5.0)


# --- command builders (pure) ----------------------------------------------

def test_thumbnail_command_seeks_before_input():
    cmd = ffmpeg.build_thumbnail_command(Path("in.mp4"), 3.0, Path("out.png"))
    assert cmd.index("-ss") < cmd.index("-i")


def test_thumbnail_command_scales_to_720_and_grabs_one_frame():
    cmd = ffmpeg.build_thumbnail_command(Path("in.mp4"), 3.0, Path("out.png"))
    assert "scale=-2:720" in cmd
    assert "-frames:v" in cmd and "1" in cmd


def test_convert_command_uses_h264_crf18_and_drops_audio():
    cmd = ffmpeg.build_convert_command(Path("in.mp4"), Path("out.mov"))
    assert "libx264" in cmd
    assert cmd[cmd.index("-crf") + 1] == "18"
    assert "-an" in cmd


def test_strip_audio_command_copies_video_and_drops_audio():
    cmd = ffmpeg.build_strip_audio_command(Path("in.mp4"), Path("out.mp4"))
    assert "copy" in cmd
    assert "-an" in cmd
    assert "libx264" not in cmd  # must not re-encode


def test_thumbnail_positions_are_four_spread_through_the_clip():
    assert len(ffmpeg.THUMBNAIL_POSITIONS) == 4
    assert all(0.0 < p < 1.0 for p in ffmpeg.THUMBNAIL_POSITIONS)


# --- integration: real ffmpeg runs ----------------------------------------

@requires_ffmpeg
def test_probe_real_h264_clip_with_audio(h264_with_audio: Path):
    result = ffmpeg.probe(h264_with_audio)
    assert result.codec == "h264"
    assert result.has_audio is True
    assert result.duration == pytest.approx(2.0, abs=0.3)


@requires_ffmpeg
def test_probe_real_hevc_clip_without_audio(hevc_no_audio: Path):
    result = ffmpeg.probe(hevc_no_audio)
    assert result.codec == "hevc"
    assert result.has_audio is False


@requires_ffmpeg
def test_probe_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(ffmpeg.FfmpegError):
        ffmpeg.probe(tmp_path / "does_not_exist.mp4")


@requires_ffmpeg
def test_generate_thumbnails_creates_four_png_files(h264_with_audio, tmp_path):
    thumbs = ffmpeg.generate_thumbnails(h264_with_audio, 2.0, tmp_path)
    assert len(thumbs) == 4
    for t in thumbs:
        assert t.exists()
        assert t.stat().st_size > 0


@requires_ffmpeg
def test_generate_thumbnails_are_720_high(h264_with_audio, tmp_path):
    thumbs = ffmpeg.generate_thumbnails(h264_with_audio, 2.0, tmp_path)
    assert ffmpeg.probe(thumbs[0]).height == 720


@requires_ffmpeg
def test_convert_produces_h264_without_audio(hevc_no_audio, tmp_path):
    out = tmp_path / "converted.mov"
    ffmpeg.convert_to_h264(hevc_no_audio, out)
    result = ffmpeg.probe(out)
    assert result.codec == "h264"
    assert result.has_audio is False


@requires_ffmpeg
def test_strip_audio_removes_audio_and_keeps_h264(h264_with_audio, tmp_path):
    out = tmp_path / "stripped.mp4"
    ffmpeg.strip_audio(h264_with_audio, out)
    result = ffmpeg.probe(out)
    assert result.has_audio is False
    assert result.codec == "h264"


@requires_ffmpeg
def test_convert_leaves_no_output_or_temp_on_failure(tmp_path):
    bogus = tmp_path / "not_a_video.mp4"
    bogus.write_bytes(b"garbage")
    out = tmp_path / "out.mov"
    with pytest.raises(ffmpeg.FfmpegError):
        ffmpeg.convert_to_h264(bogus, out)
    assert not out.exists()
    assert list(tmp_path.glob(".*.part*")) == []  # temp cleaned up


def test_terminate_all_is_a_noop_when_nothing_running():
    ffmpeg.terminate_all()  # must not raise with an empty registry
