"""ffprobe/ffmpeg wrappers: probe stats, thumbnails, convert, strip audio.

Command builders are kept as pure functions so they can be tested without
running ffmpeg. The runner functions execute them and raise FfmpegError with
context on failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .models import THUMBNAIL_POSITIONS

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Matches the reference to-mov script: near-lossless, muted, faststart .mov.
CONVERT_CRF = "18"
CONVERT_PRESET = "medium"


class FfmpegError(RuntimeError):
    """Raised when ffprobe/ffmpeg fails or returns unusable output."""


@dataclass
class ProbeResult:
    codec: str
    duration: float | None
    width: int
    height: int
    has_audio: bool


# --- command builders (pure) ----------------------------------------------

def build_probe_command(src: Path) -> list[str]:
    return [
        FFPROBE, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(src),
    ]


def build_thumbnail_command(src: Path, timestamp: float, out: Path) -> list[str]:
    # -ss before -i: fast input seek to the frame we want.
    return [
        FFMPEG, "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(src),
        "-frames:v", "1",
        "-vf", "scale=-2:720",
        "-q:v", "2",
        str(out),
    ]


def build_convert_command(src: Path, out: Path) -> list[str]:
    return [
        FFMPEG, "-y",
        "-i", str(src),
        "-c:v", "libx264", "-preset", CONVERT_PRESET, "-crf", CONVERT_CRF,
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(out),
    ]


def build_strip_audio_command(src: Path, out: Path) -> list[str]:
    # Lossless: copy the video stream untouched, drop audio.
    return [
        FFMPEG, "-y",
        "-i", str(src),
        "-c:v", "copy",
        "-an",
        "-movflags", "+faststart",
        str(out),
    ]


# --- parsing (pure) -------------------------------------------------------

def parse_probe(data: dict) -> ProbeResult:
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise FfmpegError("no video stream found")

    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = _first_duration(data.get("format", {}).get("duration"),
                               video.get("duration"))

    return ProbeResult(
        codec=video.get("codec_name", ""),
        duration=duration,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        has_audio=has_audio,
    )


def _first_duration(*candidates: str | None) -> float | None:
    for value in candidates:
        if value:
            try:
                return float(value)
            except ValueError:
                continue
    return None


# --- runners --------------------------------------------------------------

def probe(src: Path) -> ProbeResult:
    result = _run(build_probe_command(src))
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FfmpegError(f"could not parse ffprobe output for {src}") from exc
    return parse_probe(data)


def thumbnail_paths(
    src: Path, out_dir: Path,
    positions: tuple[float, ...] = THUMBNAIL_POSITIONS,
) -> list[Path]:
    """The paths generate_thumbnails would produce (for cache reuse checks)."""
    return [out_dir / f"{src.stem}_thumb{i}.png" for i in range(len(positions))]


def generate_thumbnails(
    src: Path, duration: float, out_dir: Path,
    positions: tuple[float, ...] = THUMBNAIL_POSITIONS,
) -> list[Path]:
    """Grab one 720p frame at each fraction of the clip duration."""
    out_dir.mkdir(parents=True, exist_ok=True)
    outs = thumbnail_paths(src, out_dir, positions)
    for fraction, out in zip(positions, outs):
        timestamp = duration * fraction
        _run_atomic(out, lambda tmp, t=timestamp: build_thumbnail_command(src, t, tmp))
    return outs


def convert_to_h264(src: Path, out: Path) -> None:
    _run_atomic(out, lambda tmp: build_convert_command(src, tmp))


def strip_audio(src: Path, out: Path) -> None:
    _run_atomic(out, lambda tmp: build_strip_audio_command(src, tmp))


def _run_atomic(out: Path, build) -> None:
    """Write to a temp file (same extension so ffmpeg picks the format), then
    atomically move it into place, so a killed/failed run leaves no partial
    output behind."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.stem}.part{out.suffix}")
    try:
        _run(build(tmp))
        os.replace(tmp, out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


# Child processes currently running, so shutdown can terminate them instead of
# leaving orphans.
_active: set[subprocess.Popen] = set()
_active_lock = threading.Lock()


def terminate_all() -> None:
    """Terminate any running ffmpeg/ffprobe children (called on app shutdown)."""
    with _active_lock:
        procs = list(_active)
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except FileNotFoundError as exc:
        raise FfmpegError(f"{cmd[0]} not found on PATH") from exc
    with _active_lock:
        _active.add(proc)
    try:
        stdout, stderr = proc.communicate()
    finally:
        with _active_lock:
            _active.discard(proc)
    if proc.returncode != 0:
        tail = (stderr or "").strip().splitlines()[-3:]
        raise FfmpegError(
            f"{cmd[0]} failed ({proc.returncode}): {' '.join(tail)}"
        )
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
