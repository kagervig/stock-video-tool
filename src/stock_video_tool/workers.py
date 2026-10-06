"""Background workers so ffmpeg work never blocks the UI thread."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from .core import ffmpeg
from .core.models import QueueOp, VideoItem

CACHE_DIR = Path.home() / "Library" / "Caches" / "StockVideoTool"


def cache_dir_for(path: Path) -> Path:
    """A stable per-file cache dir keyed on path + size + mtime."""
    try:
        stat = path.stat()
        key = f"{path}:{stat.st_size}:{int(stat.st_mtime)}"
    except OSError:
        key = str(path)
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE_DIR / digest


def output_path_for(item: VideoItem) -> Path:
    """Where a processed clip is written (convert -> .mov, strip -> same ext)."""
    out_dir = item.path.parent / "converted"
    if item.queue_op is QueueOp.CONVERT:
        return out_dir / f"{item.path.stem}.mov"
    return out_dir / f"{item.path.stem}{item.path.suffix}"


def process_item(item: VideoItem) -> Path:
    """Run the queued operation for one clip and return the output path."""
    out = output_path_for(item)
    if item.queue_op is QueueOp.CONVERT:
        ffmpeg.convert_to_h264(item.path, out)
    elif item.queue_op is QueueOp.STRIP_AUDIO:
        ffmpeg.strip_audio(item.path, out)
    else:
        raise ValueError(f"no queue operation set for {item.filename}")
    return out


class QueueSignals(QObject):
    item_started = Signal(object)        # item
    item_done = Signal(object, object)   # item, output path
    item_failed = Signal(object, str)    # item, error message
    finished = Signal()                  # whole queue processed


class QueueWorker(QRunnable):
    """Process the convert/strip queue sequentially on one background thread."""

    def __init__(self, items: list[VideoItem]) -> None:
        super().__init__()
        self.items = items
        self.signals = QueueSignals()

    def run(self) -> None:
        for item in self.items:
            self.signals.item_started.emit(item)
            try:
                out = process_item(item)
                self.signals.item_done.emit(item, out)
            except Exception as exc:  # surfaced per-item, queue continues
                self.signals.item_failed.emit(item, str(exc))
        self.signals.finished.emit()


class CallSignals(QObject):
    finished = Signal(object, object)  # item, return value
    failed = Signal(object, str)       # item, error message


class CallWorker(QRunnable):
    """Run an arbitrary callable off the UI thread (e.g. an OpenRouter call)."""

    def __init__(self, item: VideoItem, fn) -> None:
        super().__init__()
        self.item = item
        self.fn = fn
        self.signals = CallSignals()

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.item, self.fn())
        except Exception as exc:  # surfaced to the user, not swallowed
            self.signals.failed.emit(self.item, str(exc))


class ProbeSignals(QObject):
    finished = Signal(object, object, object)  # item, ProbeResult, list[Path]
    failed = Signal(object, str)               # item, error message


class ProbeWorker(QRunnable):
    """Probe a clip for stats and generate its 4 thumbnails."""

    def __init__(self, item: VideoItem) -> None:
        super().__init__()
        self.item = item
        self.signals = ProbeSignals()

    def run(self) -> None:
        path = self.item.path
        if not path.exists():
            self.signals.failed.emit(
                self.item,
                "File not found — if it's on an external drive, make sure the "
                "volume is still mounted.",
            )
            return
        if not os.access(path, os.R_OK):
            self.signals.failed.emit(
                self.item,
                "Permission denied reading this file. On an external volume, "
                "grant the app access (System Settings → Privacy & Security → "
                "Files and Folders / Full Disk Access) and re-add the file.",
            )
            return
        try:
            result = ffmpeg.probe(path)
            out_dir = cache_dir_for(path)
            expected = ffmpeg.thumbnail_paths(self.item.path, out_dir)
            if all(p.exists() for p in expected):
                thumbs = expected
            else:
                thumbs = ffmpeg.generate_thumbnails(
                    self.item.path, result.duration or 0.0, out_dir
                )
            self.signals.finished.emit(self.item, result, thumbs)
        except Exception as exc:  # surfaced to the user, not swallowed
            message = str(exc)
            if "permission denied" in message.lower():
                message = (
                    "Permission denied reading this file. On an external volume, "
                    "grant the app access in System Settings → Privacy & Security "
                    "→ Full Disk Access, then re-add the file."
                )
            self.signals.failed.emit(self.item, message)
