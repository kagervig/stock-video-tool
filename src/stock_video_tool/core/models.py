"""Data model for a single video in the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Envato stock video categories — the model must pick exactly one of these.
CATEGORIES = [
    "Buildings", "Business", "Corporate", "Cartoons", "City", "Construction",
    "Education", "Food", "Holidays", "Industrial", "Kids", "Medical",
    "Military", "Nature", "Overhead", "People", "Religious", "Slow Motion",
    "Special Events", "Sports", "Stop Motion", "Technology", "Time Lapse",
    "Vehicles", "Weather", "Lifestyle", "Science",
]

# Fraction of the clip duration to grab each of the four thumbnails at.
# Avoids exact start/end frames, which are often black or empty.
THUMBNAIL_POSITIONS = (0.10, 0.40, 0.70, 0.90)

PRICE_SINGLE_USE = 11
PRICE_MULTI_USE = 22


class Stage(str, Enum):
    """Where a video is in the describe -> title -> tag workflow."""

    NEW = "new"
    THUMBS_READY = "thumbs_ready"
    DESCRIBED = "described"
    TITLED = "titled"
    TAGGED = "tagged"
    READY = "ready"


class ConvertStatus(str, Enum):
    NONE = "none"
    QUEUED = "queued"
    CONVERTING = "converting"
    DONE = "done"
    FAILED = "failed"


class QueueOp(str, Enum):
    """What the processing queue will do to a clip."""

    NONE = "none"
    CONVERT = "convert"          # H265 -> H264, re-encode, drops audio
    STRIP_AUDIO = "strip_audio"  # lossless -c:v copy -an, keeps container


@dataclass
class VideoItem:
    """One dropped video and everything we derive from it."""

    path: Path

    # ffprobe-derived stats
    codec: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool = False

    thumbnails: list[Path] = field(default_factory=list)

    description: str | None = None
    title: str | None = None
    title_candidates: list[str] = field(default_factory=list)
    tags: str | None = None
    category: str | None = None

    convert_status: ConvertStatus = ConvertStatus.NONE
    queue_op: QueueOp = QueueOp.NONE
    output_path: Path | None = None

    stage: Stage = Stage.NEW

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def is_h265(self) -> bool:
        return (self.codec or "").lower() in ("hevc", "h265", "h.265")

    @property
    def planned_op(self) -> QueueOp:
        """The processing a clip needs: convert H265, else strip audio, else none."""
        if self.is_h265:
            return QueueOp.CONVERT
        if self.has_audio:
            return QueueOp.STRIP_AUDIO
        return QueueOp.NONE

    @property
    def export_filename(self) -> str:
        """Name used in the CSV — the processed output if present."""
        return self.output_path.name if self.output_path else self.filename
