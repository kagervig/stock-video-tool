"""Reusable leaf widgets, lifted out of main_window.

These are self-contained Qt widgets with no knowledge of the app's state, so
they move here as-is. Mostly a lift-and-shift: copy the existing bodies over,
then import them from main_window instead of defining them there.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QListWidget, QPlainTextEdit


class TagsEdit(QPlainTextEdit):
    """Keyword editor that emits `editingFinished` when focus leaves it.

    Used to run the hard-limit check only once the user stops editing, rather
    than on every keystroke.

    SOURCE: main_window.TagsEdit (move verbatim).
    """

    editingFinished = Signal()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class DropList(QListWidget):
    """List widget that accepts dropped video files."""

    def __init__(self, on_drop) -> None:
        super().__init__()
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        self._on_drop(paths)
        event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor("#888"))
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Drag and drop files here",
            )
            painter.end()
