"""Shared fixtures: generate real short clips with ffmpeg for integration tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(
    not HAS_FFMPEG, reason="ffmpeg/ffprobe not available on PATH"
)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


@pytest.fixture(scope="session")
def h264_with_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 2-second H264 clip that has an audio track."""
    out = tmp_path_factory.mktemp("clips") / "h264_audio.mp4"
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(out),
    ])
    return out


@pytest.fixture(scope="session")
def hevc_no_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 2-second H265 (HEVC) clip with no audio track."""
    out = tmp_path_factory.mktemp("clips") / "hevc_silent.mp4"
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
        "-c:v", "libx265", "-pix_fmt", "yuv420p", "-an",
        str(out),
    ])
    return out
