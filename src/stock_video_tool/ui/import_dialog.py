"""Resolve the gaps when reading a Shutterstock CSV into Envato terms.

Shutterstock has no Title column, and some Shutterstock categories map back to
several Envato categories. This dialog collects, in one pass, an Envato category
for each ambiguous Shutterstock category plus a Title fill policy.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..core.csv_import import TitlePolicy


class ReverseMappingDialog(QDialog):
    """Pick an Envato category per ambiguous Shutterstock category, and a Title rule."""

    def __init__(self, ambiguous: dict[str, list[str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Shutterstock → Envato")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Shutterstock files don't carry an Envato Title or an exact category.\n"
            "Choose how to fill them in."
        ))

        form = QFormLayout()
        self._category_combos: dict[str, QComboBox] = {}
        for shutterstock_category, candidates in ambiguous.items():
            combo = QComboBox()
            combo.addItems(candidates)
            form.addRow(f"Shutterstock '{shutterstock_category}' →", combo)
            self._category_combos[shutterstock_category] = combo

        self._title_combo = QComboBox()
        self._title_combo.addItem("Use Description as Title", TitlePolicy.USE_DESCRIPTION)
        self._title_combo.addItem("Leave Title blank", TitlePolicy.LEAVE_BLANK)
        form.addRow("Title:", self._title_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def category_choices(self) -> dict[str, str]:
        return {
            category: combo.currentText()
            for category, combo in self._category_combos.items()
        }

    def title_policy(self) -> TitlePolicy:
        return self._title_combo.currentData()
