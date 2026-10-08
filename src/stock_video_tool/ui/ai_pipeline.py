"""Orchestration for the per-clip OpenRouter calls.

Pulls the trickiest bookkeeping out of MainWindow: marking a clip's AI step as
running, the indeterminate busy spinner, the CallWorker lifecycle (including the
reference-retention that keeps a worker's signals from being GC'd before the
pool thread emits), and the success/failure fan-out.

MainWindow keeps ownership of VideoItem and the apply callbacks (which write the
result into the item and record stats/cost); this class only runs the work and
reports back through the callbacks passed to the constructor.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThreadPool

from ..core.models import VideoItem
from ..workers import CallWorker


class AiPipeline:
    """Runs section callables off the UI thread and tracks per-clip progress.

    Collaborators are passed in as callbacks so this class stays decoupled from
    the window's widgets:
      on_busy(delta)         +1 when a call starts, -1 when it ends
      on_item_changed(item)  refresh the item's row + buttons if it's shown
      on_status(message)     status-bar text
      on_failed(item, msg)   surface an error for a clip

    SOURCE: main_window._run_ai / _ai_done / _ai_fail / _track.
    """

    def __init__(
        self,
        pool: QThreadPool,
        on_busy: Callable[[int], None],
        on_item_changed: Callable[[VideoItem], None],
        on_status: Callable[[str], None],
        on_failed: Callable[[VideoItem, str], None],
    ) -> None:
        self._pool = pool
        self._on_busy = on_busy
        self._on_item_changed = on_item_changed
        self._on_status = on_status
        self._on_failed = on_failed
        self._workers: set = set()  # retain workers until they signal

    def run(
        self,
        section: str,
        item: VideoItem,
        fn: Callable[[], object],
        apply_cb: Callable[[VideoItem, object], None],
    ) -> None:
        """Start `fn` on a worker; on success call `apply_cb(item, result)`.

        Adds `section` to item.running, bumps busy, wires the worker signals to
        _done/_fail, retains the worker, and starts it on the pool.

        SOURCE: main_window._run_ai.
        """
        raise NotImplementedError

    def _done(
        self,
        section: str,
        apply_cb: Callable[[VideoItem, object], None],
        item: VideoItem,
        result: object,
    ) -> None:
        """Discard running flag, drop busy, run apply_cb, refresh the item.

        SOURCE: main_window._ai_done.
        """
        raise NotImplementedError

    def _fail(self, section: str, item: VideoItem, message: str) -> None:
        """Discard running flag, drop busy, refresh the item, surface the error.

        SOURCE: main_window._ai_fail.
        """
        raise NotImplementedError
