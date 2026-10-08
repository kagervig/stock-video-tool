"""Left panel: the drop list of videos plus the processing-queue box.

Owns its own widgets and communicates with MainWindow only through signals
(user intent going out) and a few setter methods (state coming in). It never
touches VideoItem or app state directly — MainWindow stays the single owner of
`self.items` and decides what each signal means.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

# Signals this panel should expose (define as class attributes with Signal(...)):
#   filesDropped(list)          # dropped local paths -> MainWindow._add_paths
#   rowChanged(int)             # selection changed  -> MainWindow._on_row_changed
#   runQueueRequested()         #                     -> MainWindow._run_queue
#   clearQueueRequested()       #                     -> MainWindow._clear_queue
#   clearFilesRequested()       #                     -> MainWindow._clear_files


class VideoListPanel(QWidget):
    """Drop list + clear-files button + the convert/strip queue box.

    SOURCE: main_window._build_left (the whole method's widget tree moves here).
    The DropList comes from ui.widgets.
    """

    def __init__(self) -> None:
        super().__init__()
        raise NotImplementedError

    # ---- state in (called by MainWindow) --------------------------------

    def set_rows(self, labels: list[str]) -> None:
        """Replace all list rows. Block signals while rebuilding so selection
        churn doesn't fire rowChanged mid-rebuild.

        SOURCE: the list-rebuild half of main_window._rebuild_list.
        """
        raise NotImplementedError

    def refresh_row(self, idx: int, label: str) -> None:
        """Update the text of one existing row.

        SOURCE: main_window._refresh_row (it currently also computes the label;
        here the caller passes the already-computed presentation.row_label).
        """
        raise NotImplementedError

    def set_queue_summary(self, text: str) -> None:
        """Set the queue box's summary label (e.g. presentation.queue_summary).

        SOURCE: the setText in main_window._update_queue_label.
        """
        raise NotImplementedError

    def set_queue_running(self, running: bool) -> None:
        """Enable/disable the run + clear queue buttons while a queue runs.

        SOURCE: the button toggling in main_window._run_queue / _on_queue_finished.
        """
        raise NotImplementedError

    # ---- selection helpers (read by MainWindow) -------------------------

    def current_row(self) -> int:
        """SOURCE: main_window.list.currentRow()."""
        raise NotImplementedError

    def set_current_row(self, idx: int) -> None:
        raise NotImplementedError

    def selected_rows(self) -> list[int]:
        """Rows selected for paste-to-many.

        SOURCE: the `[i.row() for i in self.list.selectedIndexes()]` in
        main_window._paste_meta.
        """
        raise NotImplementedError
