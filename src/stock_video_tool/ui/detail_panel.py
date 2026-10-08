"""Right panel: the detail/editor view for the selected clip.

Header + stats line, the four thumbnails, the three AI buttons with their
editors (description / titles / keywords), rating buttons, the live tag
counter, the category dropdown, and the "add to queue" button.

Communicates outward via signals (what the user wants to do) and takes state in
via `show_item`. It reads editor contents back into an item via `read_into`.
MainWindow owns the pipeline and the VideoItem; this panel just renders one.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ..core.models import VideoItem

# Signals this panel should expose:
#   describeRequested()         -> MainWindow._describe
#   titlesRequested()           -> MainWindow._gen_titles   (both the main and "More" buttons)
#   tagsRequested()             -> MainWindow._gen_tags
#   addToQueueRequested()       -> MainWindow._add_to_queue
#   rated(str, bool)            -> MainWindow._rate(query_type, good)
#   edited()                    -> MainWindow commits editors into the shown item
#   tagEditingFinished()        -> MainWindow._check_tag_limit


class DetailPanel(QWidget):
    """The editor view for one VideoItem.

    SOURCE: main_window._build_detail builds the widget tree; _show_detail,
    _render_thumbnails, _update_ai_buttons, _rating_buttons, _update_rating_buttons,
    _update_tag_count, and the editor-sync in _on_editor_changed all become
    methods here.
    """

    def __init__(self) -> None:
        super().__init__()
        raise NotImplementedError

    # ---- state in -------------------------------------------------------

    def show_item(self, item: VideoItem | None) -> None:
        """Populate every widget from `item` (or clear + disable when None).

        Set a `_loading` guard True for the duration so programmatic setText
        doesn't echo back through the `edited` signal.

        SOURCE: main_window._show_detail (plus _render_thumbnails,
        _update_ai_buttons, _update_tag_count which it calls).
        """
        raise NotImplementedError

    def read_into(self, item: VideoItem) -> None:
        """Commit the current editor contents into `item` (description, title,
        tags, category). Used on selection change, before export, and on close.

        SOURCE: the field-copying in main_window._flush / _on_editor_changed.
        """
        raise NotImplementedError

    def set_ai_running(self, item: VideoItem | None) -> None:
        """Reflect the item's in-flight AI steps on the three buttons
        (disabled + "Working…") and enable rating only where a model produced
        output.

        SOURCE: main_window._update_ai_buttons + _update_rating_buttons.
        """
        raise NotImplementedError

    # ---- private builders (stubs to flesh out) --------------------------

    def _render_thumbnails(self, item: VideoItem) -> None:
        """SOURCE: main_window._render_thumbnails."""
        raise NotImplementedError

    def _update_tag_count(self) -> None:
        """Set the counter label from presentation.tag_count_display.

        SOURCE: main_window._update_tag_count (logic now in core.presentation;
        this just applies text + stylesheet).
        """
        raise NotImplementedError
