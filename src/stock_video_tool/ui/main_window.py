"""Main window: drop list, detail panel, and convert queue.

This is a UI-first scaffold. Backend steps (ffmpeg, OpenRouter) are stubbed
with placeholder data so the full flow can be clicked through before the real
implementations are wired in. Stub points are marked with `# STUB`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core import csv_export
from ..core import ffmpeg
from ..core import presentation
from ..core import library as lib
from ..core import openrouter as orc
from ..core.config import Settings
from ..core.library import Library
from ..core.stats import Stats
from ..core.models import CATEGORIES, ConvertStatus, QueueOp, Stage, VideoItem
from ..workers import CallWorker, ProbeWorker, QueueWorker
from .settings_dialog import SettingsDialog
from .widgets import DropList, TagsEdit

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".m4v", ".avi"}

DESCRIBE_LABEL = "Get video subject description (AI vision)"
TITLES_LABEL = "Approve description → generate titles"
TAGS_LABEL = "Approve title → generate 45 tags + category"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stock Video Tool")
        self.resize(1100, 720)

        self.settings = Settings.load()
        self.library = Library()
        self.stats = Stats()
        self.items: list[VideoItem] = []
        self._shown_item: VideoItem | None = None  # item backing the editors
        self._loading = False  # True while editors are populated programmatically
        self.clipboard: dict | None = None  # title/description/tags/category
        self.session_cost = 0.0  # accumulated usage.cost across all requests
        self.pool = QThreadPool()
        self._workers: set = set()  # keep workers alive until they finish
        self._queue_running = False
        self._queue_worker: QueueWorker | None = None
        self._rate_buttons: dict[str, tuple[QPushButton, QPushButton]] = {}

        self._build_toolbar()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])
        self.setCentralWidget(splitter)

        self._inflight = 0
        self._busy = QProgressBar()
        self._busy.setRange(0, 0)  # indeterminate (animated) spinner
        self._busy.setMaximumWidth(120)
        self._busy.setVisible(False)
        self.statusBar().addPermanentWidget(self._busy)

        self._show_detail(None)
        self.statusBar().showMessage("Drop video files to begin")

    def _begin_busy(self) -> None:
        self._inflight += 1
        self._busy.setVisible(True)

    def _end_busy(self) -> None:
        self._inflight = max(0, self._inflight - 1)
        if self._inflight == 0:
            self._busy.setVisible(False)

    # ---- layout builders -------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Main")
        tb.setMovable(False)

        def action(text: str, handler) -> None:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            tb.addWidget(btn)

        action("Settings", self._open_settings)
        tb.addSeparator()
        action("Copy metadata", self._copy_meta)
        action("Paste to selected", self._paste_meta)
        tb.addSeparator()
        action("Export CSV", self._export_csv)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        tb.addWidget(spacer)
        self.cost_label = QLabel()
        self._refresh_cost()
        tb.addWidget(self.cost_label)

    def _refresh_cost(self) -> None:
        self.cost_label.setText(f"  Session token cost: ${self.session_cost:.4f}  ")

    def _charge(self, section: str, cost: float) -> None:
        """Record the cost of one request and report which key was used."""
        self.session_cost += cost
        self._refresh_cost()
        key_choice = getattr(self.settings, section).key_choice
        self.statusBar().showMessage(
            f"{section} via {key_choice} key — cost ${cost:.4f} "
            f"(session ${self.session_cost:.4f})"
        )

    def _build_left(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Videos"))
        header_row.addStretch(1)
        self.clear_files_btn = QPushButton("Clear files")
        self.clear_files_btn.clicked.connect(self._clear_files)
        header_row.addWidget(self.clear_files_btn)
        layout.addLayout(header_row)
        self.list = DropList(self._add_paths)
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list, 1)

        self.queue_box = QGroupBox("Processing queue (convert / strip audio)")
        qlayout = QVBoxLayout(self.queue_box)
        self.queue_label = QLabel("Empty")
        self.queue_label.setStyleSheet("color: gray;")
        qlayout.addWidget(self.queue_label)
        queue_btn_row = QHBoxLayout()
        self.run_queue_btn = QPushButton("Run queue")
        self.run_queue_btn.clicked.connect(self._run_queue)
        self.clear_queue_btn = QPushButton("Clear queue")
        self.clear_queue_btn.clicked.connect(self._clear_queue)
        queue_btn_row.addWidget(self.run_queue_btn)
        queue_btn_row.addWidget(self.clear_queue_btn)
        qlayout.addLayout(queue_btn_row)
        layout.addWidget(self.queue_box)

        return panel

    def _build_detail(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        self.title_header = QLabel("No video selected")
        self.title_header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_header)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: gray;")
        layout.addWidget(self.stats_label)

        # thumbnails row
        self.thumbs_row = QHBoxLayout()
        thumbs_frame = QFrame()
        thumbs_frame.setLayout(self.thumbs_row)
        layout.addWidget(thumbs_frame)

        # description
        self.describe_btn = QPushButton(DESCRIBE_LABEL)
        self.describe_btn.clicked.connect(self._describe)
        layout.addWidget(self.describe_btn)
        desc_header = QHBoxLayout()
        desc_header.addWidget(QLabel("Description"))
        desc_header.addStretch(1)
        for btn in self._rating_buttons("description"):
            desc_header.addWidget(btn)
        layout.addLayout(desc_header)
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Generated description appears here — editable")
        self.desc_edit.setFixedHeight(90)
        self.desc_edit.textChanged.connect(self._on_editor_changed)
        layout.addWidget(self.desc_edit)

        # titles
        self.titles_btn = QPushButton(TITLES_LABEL)
        self.titles_btn.clicked.connect(self._gen_titles)
        layout.addWidget(self.titles_btn)
        title_row = QHBoxLayout()
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        self.title_combo.currentTextChanged.connect(self._on_editor_changed)
        self.more_titles_btn = QPushButton("More")
        self.more_titles_btn.clicked.connect(self._gen_titles)
        title_row.addWidget(QLabel("Title"))
        title_row.addWidget(self.title_combo, 1)
        title_row.addWidget(self.more_titles_btn)
        for btn in self._rating_buttons("titles"):
            title_row.addWidget(btn)
        layout.addLayout(title_row)

        # tags
        self.tags_btn = QPushButton(TAGS_LABEL)
        self.tags_btn.clicked.connect(self._gen_tags)
        layout.addWidget(self.tags_btn)
        tags_label_row = QHBoxLayout()
        tags_label_row.addWidget(QLabel("Keywords (comma-separated)"))
        tags_label_row.addStretch(1)
        self.tags_count_label = QLabel()
        tags_label_row.addWidget(self.tags_count_label)
        for btn in self._rating_buttons("tags"):
            tags_label_row.addWidget(btn)
        layout.addLayout(tags_label_row)
        self.tags_edit = TagsEdit()
        self.tags_edit.setPlaceholderText("Generated tags appear here — editable")
        self.tags_edit.setFixedHeight(70)
        self.tags_edit.textChanged.connect(self._on_editor_changed)
        self.tags_edit.editingFinished.connect(self._check_tag_limit)
        layout.addWidget(self.tags_edit)
        self._update_tag_count()

        cat_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItem("")
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.currentTextChanged.connect(self._on_editor_changed)
        cat_row.addWidget(QLabel("Category (Envato)"))
        cat_row.addWidget(self.category_combo, 1)
        layout.addLayout(cat_row)

        self.convert_btn = QPushButton("Add to convert queue")
        self.convert_btn.clicked.connect(self._add_to_queue)
        layout.addWidget(self.convert_btn)

        layout.addStretch(1)
        return panel

    # ---- data flow -------------------------------------------------------

    def _add_paths(self, paths: list[str]) -> None:
        added = 0
        for p in paths:
            path = Path(p)
            if not presentation.is_video(path):
                continue
            ##TO DO add popup error saying unsupported filetype
            item = VideoItem(path=path)
            stored = self.library.lookup(item.filename)
            if stored:
                lib.apply_fields(item, stored)
            self.items.append(item)
            self._probe(item)  # always regenerate thumbnails + re-probe stats
            added += 1
        if added:
            self._rebuild_list()
            self.statusBar().showMessage(f"Added {added} video(s) — analyzing…")

    def _rebuild_list(self) -> None:
        """Sort items alphabetically by filename and rebuild the list rows,
        keeping self.items and the list widget index-aligned."""
        keep = self._shown_item
        self.items.sort(key=lambda item: item.filename.lower())
        self.list.blockSignals(True)
        self.list.clear()
        for item in self.items:
            QListWidgetItem(presentation._row_label(item), self.list)
        self.list.blockSignals(False)
        if keep in self.items:
            self.list.setCurrentRow(self.items.index(keep))
        elif self.items:
            self.list.setCurrentRow(0)

    def _probe(self, item: VideoItem) -> None:
        """Kick off ffprobe + thumbnail generation on a background thread."""
        worker = ProbeWorker(item)
        worker.signals.finished.connect(self._on_probe_finished)
        worker.signals.failed.connect(self._on_probe_failed)
        self._track(worker)
        self._begin_busy()
        self.pool.start(worker)

    def _track(self, worker) -> None:
        """Retain a worker until it signals, so its signals aren't GC'd."""
        self._workers.add(worker)
        worker.signals.finished.connect(lambda *_: self._workers.discard(worker))
        worker.signals.failed.connect(lambda *_: self._workers.discard(worker))

    def _on_probe_finished(self, item, result, thumbs) -> None:
        self._end_busy()
        item.codec = result.codec
        item.duration = result.duration
        item.width = result.width
        item.height = result.height
        item.has_audio = result.has_audio
        item.thumbnails = list(thumbs)
        item.stage = Stage.THUMBS_READY
        idx = self.items.index(item)
        self._refresh_row(idx)
        if self._current() is item:
            self._show_detail(item)

    def _on_probe_failed(self, item, message) -> None:
        self._end_busy()
        idx = self.items.index(item)
        self.list.item(idx).setText(f"{item.filename}  [probe failed]")
        self.statusBar().showMessage(f"{item.filename}: {message}")

    def _refresh_row(self, idx: int) -> None:
        self.list.item(idx).setText(presentation._row_label(self.items[idx]))

    def _current(self) -> VideoItem | None:
        idx = self.list.currentRow()
        return self.items[idx] if 0 <= idx < len(self.items) else None

    def _on_row_changed(self, idx: int) -> None:
        self._flush(self._shown_item)
        item = self._current()
        self._show_detail(item)
        self._shown_item = item

    def _flush(self, item: VideoItem | None) -> None:
        """Commit the editor contents of the shown item and persist them."""
        if item is None or item is not self._shown_item:
            return
        item.description = self.desc_edit.toPlainText().strip() or None
        item.title = self.title_combo.currentText().strip() or None
        item.tags = self.tags_edit.toPlainText().strip() or None
        item.category = self.category_combo.currentText().strip() or None
        fields = lib.item_fields(item)
        if lib.has_data(fields):
            self.library.record(item.filename, fields)
            self._refresh_row(self.items.index(item))

    def closeEvent(self, event) -> None:
        if self._inflight > 0 or self._queue_running:
            reply = QMessageBox.question(
                self, "Work in progress",
                "Conversions or AI requests are still running. Quit anyway?\n"
                "In-progress work will be cancelled.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._flush(self._shown_item)
        self.pool.clear()           # drop queued-but-not-started work
        ffmpeg.terminate_all()      # kill running ffmpeg/ffprobe children
        self.pool.waitForDone(3000)  # bounded wait so close stays prompt
        super().closeEvent(event)

    def _show_detail(self, item: VideoItem | None) -> None:
        self._loading = True
        has = item is not None
        for w in (
            self.desc_edit, self.title_combo, self.tags_edit,
            self.category_combo, self.convert_btn,
        ):
            w.setEnabled(has)
        self._update_ai_buttons(item)

        # clear thumbnails row
        while self.thumbs_row.count():
            w = self.thumbs_row.takeAt(0).widget()
            if w:
                w.deleteLater()

        if not has:
            self.title_header.setText("No video selected")
            self.stats_label.setText("")
            self.desc_edit.clear()
            self.title_combo.clear()
            self.tags_edit.clear()
            self.category_combo.setCurrentIndex(0)
            self._update_tag_count()
            self._loading = False
            return

        self.title_header.setText(item.filename)
        self.stats_label.setText(presentation.stats_summary(item))

        self._render_thumbnails(item)

        self.desc_edit.setPlainText(item.description or "")
        self.title_combo.clear()
        self.title_combo.addItems(item.title_candidates)
        if item.title:
            self.title_combo.setCurrentText(item.title)
        self.tags_edit.setPlainText(item.tags or "")
        self.category_combo.setCurrentText(item.category or "")

        queued = item.convert_status == ConvertStatus.QUEUED
        op = item.planned_op
        self.convert_btn.setEnabled(op is not QueueOp.NONE and not queued)
        if queued:
            self.convert_btn.setText("Queued")
        elif op is QueueOp.CONVERT:
            self.convert_btn.setText("Add to queue — convert H265 → H264 (muted)")
        elif op is QueueOp.STRIP_AUDIO:
            self.convert_btn.setText("Add to queue — strip audio (lossless)")
        else:
            self.convert_btn.setText("No processing needed")

        self._update_tag_count()
        self._loading = False

    def _rating_buttons(self, query_type: str) -> tuple[QPushButton, QPushButton]:
        up = QPushButton("👍")
        down = QPushButton("👎")
        for btn in (up, down):
            btn.setFixedWidth(38)
        up.setToolTip(f"This model's {query_type} output was good")
        down.setToolTip(f"This model's {query_type} output was poor")
        up.clicked.connect(lambda: self._rate(query_type, True))
        down.clicked.connect(lambda: self._rate(query_type, False))
        self._rate_buttons[query_type] = (up, down)
        return up, down

    def _rate(self, query_type: str, good: bool) -> None:
        item = self._current()
        if not item:
            return
        model = item.models_used.get(query_type)
        if not model:
            self.statusBar().showMessage(
                f"Generate {query_type} first, then rate it"
            )
            return
        self.stats.record_rating(model, query_type, good)
        verdict = "👍 good" if good else "👎 poor"
        self.statusBar().showMessage(f"Rated {query_type} from {model}: {verdict}")

    def _update_rating_buttons(self, item: VideoItem | None) -> None:
        for query_type, (up, down) in self._rate_buttons.items():
            enabled = bool(item and item.models_used.get(query_type))
            up.setEnabled(enabled)
            down.setEnabled(enabled)

    def _update_ai_buttons(self, item: VideoItem | None) -> None:
        """Drive the AI buttons from the shown item's own running state, so each
        clip's progress is independent and switching clips never desyncs them."""
        running = item.running if item else set()
        has = item is not None
        for section, button, label in (
            ("description", self.describe_btn, DESCRIBE_LABEL),
            ("titles", self.titles_btn, TITLES_LABEL),
            ("tags", self.tags_btn, TAGS_LABEL),
        ):
            active = section in running
            button.setEnabled(has and not active)
            button.setText("Working…" if active else label)
        self.more_titles_btn.setEnabled(has and "titles" not in running)
        self._update_rating_buttons(item)

    def _render_thumbnails(self, item: VideoItem) -> None:
        labels = ("10%", "40%", "70%", "90%")
        for i, pct in enumerate(labels):
            thumb = QLabel()
            thumb.setFixedSize(150, 84)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = None
            if i < len(item.thumbnails):
                pix = QPixmap(str(item.thumbnails[i]))
            if pix and not pix.isNull():
                thumb.setPixmap(
                    pix.scaled(
                        150, 84,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                thumb.setText(pct if item.codec is None else "…")
                thumb.setStyleSheet(
                    "border: 1px solid #888; background: #222; color: #aaa;"
                )
            self.thumbs_row.addWidget(thumb)
        self.thumbs_row.addStretch(1)

    def _update_tag_count(self) -> None:
        display = presentation.tag_count_display(self.tags_edit.toPlainText())
        self.tags_count_label.setText(display.text)
        self.tags_count_label.setStyleSheet(f"color: {display.color}; font-size: 11px;")

    def _on_editor_changed(self) -> None:
        """Commit editor contents into the shown item as the user edits, so
        nothing is lost when the detail panel is later repopulated."""
        self._update_tag_count()
        if self._loading or self._shown_item is None:
            return
        item = self._shown_item
        item.description = self.desc_edit.toPlainText().strip() or None
        item.title = self.title_combo.currentText().strip() or None
        item.tags = self.tags_edit.toPlainText().strip() or None
        item.category = self.category_combo.currentText().strip() or None
        self._refresh_row(self.items.index(item))

    def _check_tag_limit(self) -> None:
        """On finishing a keyword edit, warn if over the hard limit — without
        altering the user's keywords."""
        over = orc.tags_over_limit(len(orc.parse_tags(self.tags_edit.toPlainText())))
        if over:
            QMessageBox.warning(
                self, "Too many keywords",
                f"You have {over} keyword(s) over the limit of {orc.TAG_LIMIT}. "
                f"Please remove {over}.\n\nYour keywords have not been changed.",
            )

    # ---- pipeline actions (OpenRouter) -----------------------------------

    def _client_for(self, section: str) -> tuple[orc.Client, str] | tuple[None, None]:
        """Build a client for a section, or report what's missing in Settings."""
        cfg = getattr(self.settings, section)
        model = cfg.model.strip()
        if not model:
            self.statusBar().showMessage(f"Set a model for '{section}' in Settings")
            return None, None
        key = self.settings.keys.get(cfg.key_choice)
        if not key:
            self.statusBar().showMessage(
                f"Set the {cfg.key_choice} key in Settings (used by '{section}')"
            )
            return None, None
        return orc.Client(key), model

    def _run_ai(self, section, item, fn, apply_cb) -> None:
        item.running.add(section)
        self._begin_busy()
        self._refresh_row(self.items.index(item))
        if self._current() is item:
            self._update_ai_buttons(item)
        self.statusBar().showMessage(
            f"{section} for {item.filename}: contacting OpenRouter…"
        )
        worker = CallWorker(item, fn)
        worker.signals.finished.connect(
            lambda it, res: self._ai_done(section, apply_cb, it, res)
        )
        worker.signals.failed.connect(
            lambda it, msg: self._ai_fail(section, it, msg)
        )
        self._track(worker)
        self.pool.start(worker)

    def _ai_done(self, section, apply_cb, item, result) -> None:
        item.running.discard(section)
        self._end_busy()
        apply_cb(item, result)  # updates the item (and editors, if it's shown)
        self._refresh_row(self.items.index(item))
        if self._current() is item:
            self._update_ai_buttons(item)

    def _ai_fail(self, section, item, message) -> None:
        item.running.discard(section)
        self._end_busy()
        self._refresh_row(self.items.index(item))
        if self._current() is item:
            self._update_ai_buttons(item)
        self.statusBar().showMessage(f"{item.filename}: {message}")

    def _persist(self, item: VideoItem) -> None:
        self.library.record(item.filename, lib.item_fields(item))

    def _describe(self) -> None:
        item = self._current()
        if not item:
            return
        if not item.thumbnails:
            self.statusBar().showMessage("Thumbnails are not ready yet")
            return
        client, model = self._client_for("description")
        if client is None:
            return
        thumbs = list(item.thumbnails)
        prompt = self.settings.description.prompt or None
        self._run_ai(
            "description", item,
            lambda: client.describe(thumbs, model, prompt=prompt),
            self._apply_describe,
        )

    def _apply_describe(self, item, result) -> None:
        item.description = result.text
        item.stage = Stage.DESCRIBED
        if self._current() is item:
            self.desc_edit.setPlainText(item.description)
        self._refresh_row(self.items.index(item))
        self._persist(item)
        item.models_used["description"] = result.model
        self.stats.record(result.model, "description", result.cost, result.elapsed)
        self._charge("description", result.cost)

    def _gen_titles(self) -> None:
        item = self._current()
        if not item:
            return
        description = self.desc_edit.toPlainText().strip()
        if not description:
            self.statusBar().showMessage("Write or generate a description first")
            return
        item.description = description
        client, model = self._client_for("titles")
        if client is None:
            return
        prompt = self.settings.titles.prompt or None
        self._run_ai(
            "titles", item,
            lambda: client.titles(description, model, prompt=prompt),
            self._apply_titles,
        )

    def _apply_titles(self, item, result) -> None:
        titles, chat = result
        item.title_candidates = titles
        item.stage = Stage.TITLED
        if self._current() is item:
            self.title_combo.clear()
            self.title_combo.addItems(titles)
        self._persist(item)
        item.models_used["titles"] = chat.model
        self.stats.record(chat.model, "titles", chat.cost, chat.elapsed)
        self._charge("titles", chat.cost)

    def _gen_tags(self) -> None:
        item = self._current()
        if not item:
            return
        title = self.title_combo.currentText().strip()
        description = self.desc_edit.toPlainText().strip()
        if not title:
            self.statusBar().showMessage("Choose or enter a title first")
            return
        item.title = title
        client, model = self._client_for("tags")
        if client is None:
            return
        prompt = self.settings.tags.prompt or None

        def work():
            tags, r1 = client.tags(title, description, model, prompt=prompt)
            # Category is best-effort and user-editable; a bad answer shouldn't
            # discard the tags we already paid for, so fall back to blank.
            try:
                category, r2 = client.categorize(description, CATEGORIES, model)
            except orc.OpenRouterError:
                category, r2 = "", None
            return tags, category, r1, r2

        self._run_ai("tags", item, work, self._apply_tags)

    def _apply_tags(self, item, result) -> None:
        tags, category, r1, r2 = result
        item.tags = ", ".join(tags)
        item.category = category
        item.stage = Stage.TAGGED
        if self._current() is item:
            self.tags_edit.setPlainText(item.tags)
            self.category_combo.setCurrentText(category)
        self._refresh_row(self.items.index(item))
        self._persist(item)
        item.models_used["tags"] = r1.model
        self.stats.record(r1.model, "tags", r1.cost, r1.elapsed)
        total_cost = r1.cost
        if r2 is not None:
            item.models_used["category"] = r2.model
            self.stats.record(r2.model, "category", r2.cost, r2.elapsed)
            total_cost += r2.cost
        self._charge("tags", total_cost)

    # ---- copy / paste meta ----------------------------------------------

    def _copy_meta(self) -> None:
        item = self._current()
        if not item:
            return
        self.clipboard = {
            "title": self.title_combo.currentText(),
            "description": self.desc_edit.toPlainText(),
            "tags": self.tags_edit.toPlainText(),
            "category": self.category_combo.currentText(),
        }
        self.statusBar().showMessage("Copied title, description, tags, category")

    def _paste_meta(self) -> None:
        if not self.clipboard:
            self.statusBar().showMessage("Nothing copied yet")
            return
        meta = self.clipboard
        for idx in [i.row() for i in self.list.selectedIndexes()]:
            item = self.items[idx]
            item.title = meta["title"] or None
            item.description = meta["description"] or None
            item.tags = meta["tags"] or None
            item.category = meta["category"] or None
            self._persist(item)
            self._refresh_row(idx)
        self._show_detail(self._current())
        self.statusBar().showMessage("Pasted title, description, tags, category to selected")

    # ---- convert queue ---------------------------------------------------

    def _add_to_queue(self) -> None:
        item = self._current()
        if not item or item.planned_op is QueueOp.NONE:
            return
        item.queue_op = item.planned_op
        item.convert_status = ConvertStatus.QUEUED
        self._refresh_row(self.list.currentRow())
        self._show_detail(item)
        self._update_queue_label()

    def _clear_files(self) -> None:
        if self._inflight > 0 or self._queue_running:
            self.statusBar().showMessage(
                "Wait for current work to finish before clearing files"
            )
            return
        if not self.items:
            return
        reply = QMessageBox.question(
            self, "Clear files",
            "Remove all videos from the list? Saved titles, descriptions, and "
            "tags are kept and will reload if you add the files again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._flush(self._shown_item)
        self.items.clear()
        self.list.clear()
        self._shown_item = None
        self._show_detail(None)
        self._update_queue_label()
        self.statusBar().showMessage("Cleared all files")

    def _clear_queue(self) -> None:
        if self._queue_running:
            return
        cleared = 0
        for idx, item in enumerate(self.items):
            if item.convert_status == ConvertStatus.QUEUED:
                item.convert_status = ConvertStatus.NONE
                item.queue_op = QueueOp.NONE
                self._refresh_row(idx)
                cleared += 1
        self._update_queue_label()
        if self._current():
            self._show_detail(self._current())
        self.statusBar().showMessage(
            f"Cleared {cleared} item(s) from the queue" if cleared
            else "Queue is already empty"
        )

    def _update_queue_label(self) -> None:
        self.queue_label.setText(presentation.queue_summary(self.items))

    def _run_queue(self) -> None:
        if self._queue_running:
            return
        queued = [i for i in self.items if i.convert_status == ConvertStatus.QUEUED]
        if not queued:
            self.statusBar().showMessage("Queue is empty")
            return
        self._queue_running = True
        self.run_queue_btn.setEnabled(False)
        self.clear_queue_btn.setEnabled(False)
        self._begin_busy()
        worker = QueueWorker(queued)
        worker.signals.item_started.connect(self._on_convert_started)
        worker.signals.item_done.connect(self._on_convert_done)
        worker.signals.item_failed.connect(self._on_convert_failed)
        worker.signals.finished.connect(self._on_queue_finished)
        self._queue_worker = worker  # retain reference until finished
        self.pool.start(worker)

    def _on_convert_started(self, item) -> None:
        item.convert_status = ConvertStatus.CONVERTING
        self._refresh_row(self.items.index(item))
        self.statusBar().showMessage(f"Processing {item.filename}…")

    def _on_convert_done(self, item, out) -> None:
        item.output_path = out
        item.convert_status = ConvertStatus.DONE
        self._refresh_row(self.items.index(item))
        if self._current() is item:
            self._show_detail(item)

    def _on_convert_failed(self, item, message) -> None:
        item.convert_status = ConvertStatus.FAILED
        self._refresh_row(self.items.index(item))
        self.statusBar().showMessage(f"{item.filename}: {message}")

    def _on_queue_finished(self) -> None:
        self._queue_running = False
        self._queue_worker = None
        self.run_queue_btn.setEnabled(True)
        self.clear_queue_btn.setEnabled(True)
        self._end_busy()
        self._update_queue_label()
        done = sum(1 for i in self.items if i.convert_status == ConvertStatus.DONE)
        self.statusBar().showMessage(
            f"Queue complete — {done} processed. Ready to export CSV."
        )

    # ---- settings / export ----------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.settings = Settings.load()
            self.statusBar().showMessage("Settings saved")

    def _export_csv(self) -> None:
        self._flush(self._shown_item)  # include the latest edits
        if not self.items:
            self.statusBar().showMessage("No videos to export")
            return
        over = csv_export.over_limit_report(self.items)
        if over:
            QMessageBox.warning(
                self, "Keywords over limit",
                f"These clips exceed the {orc.TAG_LIMIT}-keyword limit:\n\n"
                + "\n".join(over)
                + "\n\nRemove the extra keywords before exporting.",
            )
            return

        incomplete = csv_export.incomplete_report(self.items)
        if incomplete:
            reply = QMessageBox.question(
                self, "Missing data",
                "Some clips are missing data:\n\n" + "\n".join(incomplete)
                + "\n\nExport anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        out = (
            Path(self.settings.export_path)
            / f"stock_video_export_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        try:
            csv_export.write_csv(self.items, out)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(
            self, "Export complete",
            f"Wrote {len(self.items)} row(s) to:\n{out}",
        )
        self.statusBar().showMessage(f"Exported CSV → {out}")
