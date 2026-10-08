"""Pure presentation logic: turning model state into display strings.

These functions have no Qt dependency so they can be unit-tested directly.
They are extracted from MainWindow, where they were previously methods that
built strings inline. Moving them here is the single biggest test-coverage win
in the refactor — each branch (codec present, description set, over tag limit,
etc.) becomes an isolated, assertable case.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import VideoItem, ConvertStatus, QueueOp
from . import openrouter as orc

# Suffixes accepted from a drag-and-drop. Lives here (not the UI) so the filter
# is testable and reusable.
# SOURCE: main_window.VIDEO_SUFFIXES
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".m4v", ".avi"}


@dataclass
class TagCount:
    """The rendered keyword counter: the label text plus a CSS colour.

    SOURCE: main_window._update_tag_count builds `text` and `color` inline.
    """

    text: str
    color: str


def is_video(path: Path) -> bool:
    """True when a path has a recognized video suffix.

    SOURCE: the `path.suffix.lower() not in VIDEO_SUFFIXES` check in
    main_window._add_paths.
    """
    return path.suffix.lower() in VIDEO_SUFFIXES

def _row_label(item: VideoItem) -> str:
        if item.codec is None:
            return f"{item.filename}  [analyzing…]"
        marks = []
        if item.description:
            marks.append("D")
        if item.title:
            marks.append("T")
        if item.tags:
            marks.append("K")
        if item.running:
            marks.append("⋯ " + "/".join(sorted(item.running)))
        if item.is_h265:
            marks.append("H265")
        elif item.has_audio:
            marks.append("audio")
        if item.convert_status == ConvertStatus.QUEUED:
            marks.append("⏳")
        elif item.convert_status == ConvertStatus.CONVERTING:
            marks.append("⚙ processing")
        elif item.convert_status == ConvertStatus.DONE:
            marks.append("✓")
        elif item.convert_status == ConvertStatus.FAILED:
            marks.append("✗ failed")
        suffix = f"  [{' '.join(marks)}]" if marks else ""
        return f"{item.filename}{suffix}"
        
def queue_summary(items: list[VideoItem]) -> str:
    """One-line summary of the processing queue, e.g. "2 convert, 1 strip audio".

    Returns "Empty" when nothing is queued.

    SOURCE: main_window._update_queue_label (the string it builds; the label
    widget's setText stays in the UI).
    """
    queued = [i for i in items if i.convert_status == ConvertStatus.QUEUED]
    #for i in items, if status == queued, append(i) to queued
    converts = sum(1 for i in queued if i.queue_op is QueueOp.CONVERT)
    #for each queued item, if status is convert, add 1 to converts, sum all the 1s
    strips = sum(1 for i in queued if i.queue_op is QueueOp.STRIP_AUDIO)
    return f"{converts} convert, {strips} strip audio" if queued else "Empty"


def tag_count_display(text: str) -> TagCount:
    """Render the keyword counter for the current Keywords text.

    Three bands: within the soft target (gray, or green at exactly TAG_COUNT),
    past the soft target but within the hard limit (amber), and over the hard
    limit (red, with "remove N").

    SOURCE: main_window._update_tag_count. Uses openrouter.parse_tags,
    tags_over_limit, TAG_COUNT, TAG_LIMIT.
    """
    over = orc.tags_over_limit(count)
    if over:
        text = f"{count} / {orc.TAG_COUNT} — remove {over} (max {orc.TAG_LIMIT})"
        color = "#c62828"  # red: over the hard limit
    elif count > orc.TAG_COUNT:
        text = f"{count} / {orc.TAG_COUNT}"
        color = "#f9a825"  # amber: past the soft target but within the limit
    else:
        text = f"{count} / {orc.TAG_COUNT}"
        color = "#2e7d32" if count == orc.TAG_COUNT else "gray"
