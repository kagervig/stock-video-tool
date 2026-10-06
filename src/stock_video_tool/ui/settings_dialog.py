"""Settings dialog.

Top: key management — paste a free key and a paid key once, and refresh the
live model list. Each prompt section picks a model (filtered free/paid/all,
and vision-only for Description) and which key to send it with. Bottom: the
CSV export path.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import openrouter as orc
from ..core.config import (
    KEY_FREE,
    KEY_PAID,
    SectionConfig,
    Settings,
    load_cached_models,
    save_cached_models,
)


class KeyRow(QWidget):
    """A single masked key field with a show/hide toggle."""

    def __init__(self, label: str, value: str):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(label))
        self.edit = QLineEdit(value)
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("sk-or-...")
        row.addWidget(self.edit, 1)

        show = QPushButton("Show")
        show.setCheckable(True)
        show.toggled.connect(
            lambda on: self.edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        row.addWidget(show)


class SectionBox(QGroupBox):
    """Model dropdown driven by which key is selected for this section.

    The free key shows only free models; the paid key shows only paid models.
    (Description additionally shows vision-capable models only.)
    """

    def __init__(
        self, title: str, cfg: SectionConfig, default_prompt: str,
        placeholders: str, vision_only: bool = False,
    ):
        super().__init__(title)
        self.cfg = cfg
        self.vision_only = vision_only
        self.default_prompt = default_prompt
        self._models: list[dict] = []

        form = QFormLayout(self)

        self.key_combo = QComboBox()
        self.key_combo.addItems([KEY_FREE, KEY_PAID])
        self.key_combo.setCurrentText(cfg.key_choice)
        self.key_combo.currentTextChanged.connect(self._repopulate)
        form.addRow("Use key", self.key_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(420)
        self.model_combo.view().setMinimumWidth(520)  # wider dropdown popup
        if cfg.model:
            self.model_combo.addItem(cfg.model)
            self.model_combo.setCurrentText(cfg.model)
        form.addRow("Model", self.model_combo)

        if vision_only:
            hint = QLabel("Vision-capable models only")
            hint.setStyleSheet("color: gray; font-size: 11px;")
            form.addRow("", hint)

        self.prompt_edit = QPlainTextEdit(cfg.prompt or default_prompt)
        self.prompt_edit.setFixedHeight(90)
        form.addRow("Prompt", self.prompt_edit)
        prompt_hint_row = QHBoxLayout()
        hint = QLabel(placeholders)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        reset = QPushButton("Reset to default")
        reset.clicked.connect(
            lambda: self.prompt_edit.setPlainText(self.default_prompt)
        )
        prompt_hint_row.addWidget(hint, 1)
        prompt_hint_row.addWidget(reset)
        form.addRow("", prompt_hint_row)

    def set_models(self, models: list[dict]) -> None:
        self._models = models
        self._repopulate()

    def _which(self) -> str:
        return "free" if self.key_combo.currentText() == KEY_FREE else "paid"

    def _repopulate(self) -> None:
        current = self.model_combo.currentText()
        filtered = orc.filter_models(
            self._models, which=self._which(), vision_only=self.vision_only,
        )
        ids = sorted((m["id"] for m in filtered), key=str.lower)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(ids)
        if current:
            self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)

    def apply_to(self) -> None:
        self.cfg.model = self.model_combo.currentText()
        self.cfg.model_filter = self._which()
        self.cfg.key_choice = self.key_combo.currentText()
        self.cfg.prompt = self.prompt_edit.toPlainText().strip()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(640)
        self.resize(680, 720)

        # The dialog is tall (three prompt editors), so its content scrolls.
        outer = QVBoxLayout(self)
        content = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        layout = QVBoxLayout(content)

        keys_box = QGroupBox("Key management")
        keys_layout = QVBoxLayout(keys_box)
        self.free_row = KeyRow("Free key", settings.keys.free)
        self.paid_row = KeyRow("Paid key", settings.keys.paid)
        keys_layout.addWidget(self.free_row)
        keys_layout.addWidget(self.paid_row)
        refresh_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh model list")
        self.refresh_btn.clicked.connect(self._refresh_models)
        self.refresh_status = QLabel("")
        self.refresh_status.setStyleSheet("color: gray; font-size: 11px;")
        refresh_row.addWidget(self.refresh_btn)
        refresh_row.addWidget(self.refresh_status, 1)
        keys_layout.addLayout(refresh_row)
        layout.addWidget(keys_box)

        self.desc_box = SectionBox(
            "Description (vision)", settings.description,
            default_prompt=orc.DEFAULT_DESCRIBE_PROMPT,
            placeholders="The 4 frames are attached automatically — no variables.",
            vision_only=True,
        )
        self.titles_box = SectionBox(
            "Titles", settings.titles,
            default_prompt=orc.DEFAULT_TITLES_PROMPT,
            placeholders="Variables: {description}, {count}",
        )
        self.tags_box = SectionBox(
            "Tags  (also used for Category)", settings.tags,
            default_prompt=orc.DEFAULT_TAGS_PROMPT,
            placeholders="Variables: {title}, {description}, {count}",
        )
        self.sections = [self.desc_box, self.titles_box, self.tags_box]
        for box in self.sections:
            layout.addWidget(box)

        export_box = QGroupBox("CSV export")
        export_layout = QHBoxLayout(export_box)
        self.export_edit = QLineEdit(settings.export_path)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        export_layout.addWidget(QLabel("Folder"))
        export_layout.addWidget(self.export_edit, 1)
        export_layout.addWidget(browse)
        layout.addWidget(export_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        cached = load_cached_models()
        if cached:
            for box in self.sections:
                box.set_models(cached)
            self.refresh_status.setText(
                f"{len(cached)} models cached — Refresh to update"
            )

    def _refresh_models(self) -> None:
        # Listing works with any key (or none); prefer whichever is set.
        key = self.free_row.edit.text() or self.paid_row.edit.text()
        self.refresh_status.setText("fetching…")
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            models = orc.Client(key).list_models()
        except orc.OpenRouterError as exc:
            self.refresh_status.setText(str(exc))
            return
        finally:
            self.unsetCursor()
        save_cached_models(models)
        for box in self.sections:
            box.set_models(models)
        self.refresh_status.setText(f"{len(models)} models loaded")

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose export folder", self.export_edit.text()
        )
        if folder:
            self.export_edit.setText(folder)

    def _save(self) -> None:
        self.settings.keys.free = self.free_row.edit.text()
        self.settings.keys.paid = self.paid_row.edit.text()
        for box in self.sections:
            box.apply_to()
        self.settings.export_path = self.export_edit.text()
        self.settings.save()
        self.accept()
