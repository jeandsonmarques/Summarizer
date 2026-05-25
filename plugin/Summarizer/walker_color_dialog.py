# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .utils.i18n_runtime import tr_text as _rt
from .walker_dialogs import WalkerModalDialog, apply_walker_buttons


_BASIC_COLORS = (
    "#000000",
    "#FFFFFF",
    "#EF4444",
    "#F97316",
    "#F59E0B",
    "#FACC15",
    "#84CC16",
    "#22C55E",
    "#14B8A6",
    "#06B6D4",
    "#3B82F6",
    "#6366F1",
    "#8B5CF6",
    "#A855F7",
    "#EC4899",
    "#F43F5E",
    "#64748B",
    "#94A3B8",
    "#CBD5E1",
    "#E2E8F0",
)


def _valid_color(value: object, fallback: str = "#FFFFFF") -> QColor:
    color = QColor(str(value or ""))
    if not color.isValid():
        color = QColor(fallback)
    if not color.isValid():
        color = QColor("#FFFFFF")
    return color


class WalkerColorDialog(WalkerModalDialog):
    def __init__(self, parent: Optional[QWidget] = None, *, initial: object = "#FFFFFF", title: str = ""):
        super().__init__(parent, width=420)
        self.setWindowTitle(title or _rt("Escolher cor"))
        self._selected = _valid_color(initial)
        self.add_header(self.windowTitle())

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        self.preview = QLabel(self.panel)
        self.preview.setFixedHeight(46)
        self.preview.setAlignment(Qt.AlignCenter)
        body.addWidget(self.preview)

        self.hex_edit = QLineEdit(self._selected.name().upper(), self.panel)
        self.hex_edit.setPlaceholderText("#5A3FE6")
        self.hex_edit.textChanged.connect(self._on_hex_changed)
        body.addWidget(self.hex_edit)

        palette = QGridLayout()
        palette.setContentsMargins(0, 4, 0, 0)
        palette.setHorizontalSpacing(6)
        palette.setVerticalSpacing(6)
        for index, color in enumerate(_BASIC_COLORS):
            button = QPushButton("", self.panel)
            button.setFixedSize(30, 24)
            button.setToolTip(color)
            button.setStyleSheet(
                f"QPushButton {{ background: {color}; border: 1px solid #D1D5DB; border-radius: 6px; }}"
                "QPushButton:hover { border: 2px solid #111827; }"
            )
            button.clicked.connect(lambda _checked=False, value=color: self._set_color(value))
            palette.addWidget(button, index // 10, index % 10)
        body.addLayout(palette)
        self.panel_layout.addLayout(body)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 8, 0, 0)
        actions.setSpacing(8)
        actions.addStretch(1)
        self.ok_btn = QPushButton("OK", self.panel)
        self.cancel_btn = QPushButton(_rt("Cancelar"), self.panel)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        actions.addWidget(self.ok_btn)
        actions.addWidget(self.cancel_btn)
        apply_walker_buttons(primary=[self.ok_btn], secondary=[self.cancel_btn])
        self.panel_layout.addLayout(actions)
        self._refresh_preview()

    def selected_color(self) -> QColor:
        return QColor(self._selected)

    def _set_color(self, value: object) -> None:
        color = _valid_color(value, self._selected.name())
        self._selected = color
        self.hex_edit.setText(color.name().upper())
        self._refresh_preview()

    def _on_hex_changed(self, text: str) -> None:
        color = QColor(str(text or "").strip())
        if color.isValid():
            self._selected = color
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        color = self._selected.name().upper()
        text_color = "#FFFFFF" if self._selected.lightness() < 120 else "#111827"
        self.preview.setText(color)
        self.preview.setStyleSheet(
            f"QLabel {{ background: {color}; color: {text_color}; border: 1px solid #D1D5DB; border-radius: 8px; font-weight: 600; }}"
        )


def walker_get_color(initial: object, parent: Optional[QWidget] = None, title: str = "") -> QColor:
    dialog = WalkerColorDialog(parent, initial=initial, title=title or _rt("Escolher cor"))
    if dialog.exec_() == QDialog.Accepted:
        return dialog.selected_color()
    return QColor()
