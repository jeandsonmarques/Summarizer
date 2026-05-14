from __future__ import annotations

from typing import Dict, Optional
import re

try:
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor
    from qgis.PyQt.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSpinBox,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    Qt = QColor = None
    QCheckBox = QComboBox = QDialog = QFrame = QGridLayout = QHBoxLayout = QLabel = QLineEdit = QPushButton = QSpinBox = QToolButton = QVBoxLayout = QWidget = object

try:
    from .model_cards import _DialogDragHandle
except Exception:
    _DialogDragHandle = None

try:
    from .model_theme import _is_dark_theme
except Exception:

    def _is_dark_theme() -> bool:
        return False

try:
    from ..utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
except Exception:

    def attach_ui_font_enforcer(_widget):
        return None

    def harmonize_widget_fonts(_widget):
        return None

    def ui_font(*_args, **_kwargs):
        class _FallbackFont:
            def setPixelSize(self, _size):
                return None

            def setWeight(self, _weight):
                return None

        return _FallbackFont()

try:
    from ..utils.i18n_runtime import tr_text as _rt
except Exception:

    def _rt(text: str, **kwargs) -> str:
        return str(text).format(**kwargs) if kwargs else str(text)

try:
    from ..utils.logging_utils import log_exception
except Exception:

    def log_exception(_message: str):
        return None


CANVAS_STYLE_KEYS = ("background", "grid_color", "show_grid", "grid_size", "grid_opacity")


def default_canvas_style() -> Dict[str, object]:
    return {
        "background": "#FFFFFF",
        "grid_color": "#FFFFFF",
        "show_grid": True,
        "grid_size": 8,
        "grid_opacity": 1.0,
    }


def _normalize_color_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith("#") and re.fullmatch(r"[0-9A-Fa-f]{6}", text):
        text = f"#{text}"
    if re.fullmatch(r"#[0-9A-Fa-f]{3}", text):
        text = "#" + "".join(ch * 2 for ch in text[1:])
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.upper()
    return ""


def normalize_hex_color(value: object, fallback: str) -> str:
    candidate = _normalize_color_text(value)
    if candidate:
        if QColor is not None:
            try:
                color = QColor(candidate)
                if color.isValid():
                    return color.name().upper()
            except Exception:
                pass
        return candidate
    fallback_candidate = _normalize_color_text(fallback)
    if fallback_candidate:
        if QColor is not None:
            try:
                color = QColor(fallback_candidate)
                if color.isValid():
                    return color.name().upper()
            except Exception:
                pass
        return fallback_candidate
    if QColor is not None:
        try:
            color = QColor(str(fallback or "#FFFFFF"))
            if color.isValid():
                return color.name().upper()
        except Exception:
            pass
    return "#FFFFFF"


def normalize_canvas_style(style: Optional[Dict[str, object]] = None, *, base: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    base_style = dict(base or default_canvas_style())
    payload = dict(style or {})
    try:
        grid_size = int(round(float(payload.get("grid_size", base_style["grid_size"]))))
    except Exception:
        grid_size = int(base_style["grid_size"])
    grid_size = max(4, min(48, grid_size))
    try:
        grid_opacity = float(payload.get("grid_opacity", base_style["grid_opacity"]))
    except Exception:
        grid_opacity = float(base_style["grid_opacity"])
    grid_opacity = max(0.1, min(1.0, grid_opacity))
    background = normalize_hex_color(payload.get("background"), str(base_style["background"]))
    grid_color = normalize_hex_color(payload.get("grid_color"), str(base_style["grid_color"]))
    if background == "#FFFFFF" and grid_color == "#E5E7EB":
        grid_color = "#FFFFFF"
        grid_opacity = 1.0
    normalized = {
        "background": background,
        "grid_color": grid_color,
        "show_grid": bool(payload.get("show_grid", base_style["show_grid"])),
        "grid_size": grid_size,
        "grid_opacity": grid_opacity,
    }
    for key, value in payload.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def apply_canvas_style_to_source_meta(source_meta: Optional[Dict[str, object]], style: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    payload = dict(source_meta or {})
    payload["canvas_style"] = dict(normalize_canvas_style(style))
    return payload


def set_color_preview_chip(label: QLabel, color_value: object, fallback: str):
    color_hex = normalize_hex_color(color_value, fallback)
    label.setText(" ")
    label.setStyleSheet(
        f"""
        QLabel {{
            min-width: 22px;
            max-width: 22px;
            min-height: 22px;
            max-height: 22px;
            border-radius: 6px;
            border: 1px solid #D1D5DB;
            background: {color_hex};
        }}
        """
    )


if QDialog is not object:

    class ModelCanvasStyleDialog(QDialog):
        def __init__(self, parent=None, *, current_style: Optional[Dict[str, object]] = None):
            super().__init__(parent)
            self._initial_style = normalize_canvas_style(current_style)
            self._style_result = dict(self._initial_style)
            self._preset_signal_lock = False
            self._presets = {
                "clean": {
                    "background": "#FFFFFF",
                    "grid_color": "#FFFFFF",
                    "show_grid": True,
                    "grid_size": 8,
                    "grid_opacity": 1.0,
                },
                "soft": {
                    "background": "#F8FAFC",
                    "grid_color": "#D1D5DB",
                    "show_grid": True,
                    "grid_size": 10,
                    "grid_opacity": 0.66,
                },
                "dark": {
                    "background": "#111827",
                    "grid_color": "#374151",
                    "show_grid": True,
                    "grid_size": 8,
                    "grid_opacity": 0.6,
                },
            }
            self._build_ui()
            self._apply_style_to_controls(self._initial_style)

        def selected_style(self) -> Dict[str, object]:
            return dict(self._style_result)

        def accept(self):
            self._style_result = self._collect_style()
            super().accept()

        def _build_ui(self):
            self.setObjectName("WalkerCanvasStyleDialog")
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
            self.setModal(True)
            self.resize(560, 392)
            self.setFont(ui_font())
            self._font_enforcer = attach_ui_font_enforcer(self)
            self.setStyleSheet(
                """
                QDialog#WalkerCanvasStyleDialog {
                    background: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    border-radius: 10px;
                }
                QFrame#WalkerDialogCard {
                    background: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                }
                QFrame#WalkerDialogDragHandle {
                    background: transparent;
                    border: none;
                }
                QLabel#WalkerDialogTitle {
                    color: #111827;
                    font-size: 14px;
                    font-weight: 500;
                }
                QLabel#WalkerDialogSubtitle {
                    color: #6B7280;
                    font-size: 11px;
                }
                QLabel#WalkerFieldLabel {
                    color: #111827;
                    font-size: 12px;
                    font-weight: 400;
                }
                QLineEdit#WalkerDialogInput,
                QComboBox#WalkerDialogInput,
                QSpinBox#WalkerDialogInput {
                    min-height: 30px;
                    padding: 0 9px;
                    color: #111827;
                    background: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    border-radius: 8px;
                }
                QLineEdit#WalkerDialogInput:focus,
                QComboBox#WalkerDialogInput:focus,
                QSpinBox#WalkerDialogInput:focus {
                    border-color: #9CA3AF;
                }
                QSpinBox#WalkerDialogInput::up-button,
                QSpinBox#WalkerDialogInput::down-button {
                    width: 0px;
                    border: none;
                    background: transparent;
                    margin: 0;
                    padding: 0;
                }
                QSpinBox#WalkerDialogInput::up-arrow,
                QSpinBox#WalkerDialogInput::down-arrow {
                    width: 0px;
                    height: 0px;
                    image: none;
                }
                QCheckBox#WalkerDialogCheck {
                    color: #111827;
                    font-size: 12px;
                    font-weight: 400;
                }
                QPushButton#WalkerDialogPrimaryButton,
                QPushButton#WalkerDialogSecondaryButton {
                    min-height: 32px;
                    border-radius: 8px;
                    padding: 0 14px;
                    font-size: 12px;
                }
                QPushButton#WalkerDialogSecondaryButton {
                    color: #111827;
                    background: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    font-weight: 400;
                }
                QPushButton#WalkerDialogSecondaryButton:hover {
                    background: #F9FAFB;
                    border-color: #9CA3AF;
                }
                QPushButton#WalkerDialogPrimaryButton {
                    color: #FFFFFF;
                    background: #111827;
                    border: 1px solid #111827;
                    font-weight: 500;
                }
                QPushButton#WalkerDialogPrimaryButton:hover {
                    background: #1F2937;
                    border-color: #1F2937;
                }
                QPushButton#WalkerColorChip {
                    min-width: 22px;
                    max-width: 22px;
                    min-height: 22px;
                    max-height: 22px;
                    border-radius: 5px;
                    border: 1px solid #D1D5DB;
                    padding: 0;
                }
                QLabel#WalkerAuxText {
                    color: #6B7280;
                    font-size: 10px;
                }
                QToolButton#ConfigDialogCloseButton {
                    min-width: 22px;
                    max-width: 22px;
                    min-height: 22px;
                    max-height: 22px;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    background: transparent;
                    color: #6B7280;
                    font-size: 14px;
                }
                QToolButton#ConfigDialogCloseButton:hover {
                    color: #111827;
                    background: #F3F4F6;
                }
                """
            )
            if hasattr(self, "setStyleSheet") and _is_dark_theme():
                self.setStyleSheet(
                    """
                    QDialog#WalkerCanvasStyleDialog {
                        background: #111827;
                        border: 1px solid #374151;
                        border-radius: 10px;
                        color: #F8FAFC;
                    }
                    QFrame#WalkerDialogCard {
                        background: #1F2937;
                        border: 1px solid #374151;
                        border-radius: 8px;
                    }
                    QFrame#WalkerDialogDragHandle,
                    QLabel {
                        background: transparent;
                    }
                    QLabel#WalkerDialogTitle,
                    QLabel#WalkerFieldLabel,
                    QCheckBox#WalkerDialogCheck {
                        color: #F8FAFC;
                    }
                    QLabel#WalkerDialogSubtitle,
                    QLabel#WalkerAuxText {
                        color: #CBD5E1;
                    }
                    QLineEdit#WalkerDialogInput,
                    QComboBox#WalkerDialogInput,
                    QSpinBox#WalkerDialogInput {
                        min-height: 30px;
                        padding: 0 9px;
                        color: #F8FAFC;
                        background: #111827;
                        border: 1px solid #374151;
                        border-radius: 8px;
                        selection-background-color: #374151;
                        selection-color: #F8FAFC;
                    }
                    QLineEdit#WalkerDialogInput:focus,
                    QComboBox#WalkerDialogInput:focus,
                    QSpinBox#WalkerDialogInput:focus {
                        border-color: #7C6CFF;
                    }
                    QComboBox#WalkerDialogInput QAbstractItemView {
                        background: #1F2937;
                        color: #F8FAFC;
                        border: 1px solid #374151;
                        selection-background-color: #374151;
                        selection-color: #F8FAFC;
                    }
                    QSpinBox#WalkerDialogInput::up-button,
                    QSpinBox#WalkerDialogInput::down-button,
                    QSpinBox#WalkerDialogInput::up-arrow,
                    QSpinBox#WalkerDialogInput::down-arrow {
                        width: 0px;
                        height: 0px;
                        border: none;
                        background: transparent;
                        image: none;
                    }
                    QPushButton#WalkerDialogPrimaryButton,
                    QPushButton#WalkerDialogSecondaryButton {
                        min-height: 32px;
                        border-radius: 8px;
                        padding: 0 14px;
                        font-size: 12px;
                    }
                    QPushButton#WalkerDialogSecondaryButton {
                        color: #F8FAFC;
                        background: #1F2937;
                        border: 1px solid #374151;
                        font-weight: 400;
                    }
                    QPushButton#WalkerDialogSecondaryButton:hover {
                        background: #273449;
                        border-color: #475569;
                    }
                    QPushButton#WalkerDialogPrimaryButton {
                        color: #0B1020;
                        background: #F8FAFC;
                        border: 1px solid #F8FAFC;
                        font-weight: 500;
                    }
                    QPushButton#WalkerDialogPrimaryButton:hover {
                        background: #E2E8F0;
                        border-color: #E2E8F0;
                    }
                    QPushButton#WalkerColorChip {
                        min-width: 22px;
                        max-width: 22px;
                        min-height: 22px;
                        max-height: 22px;
                        border-radius: 5px;
                        border: 1px solid #475569;
                        padding: 0;
                    }
                    QToolButton#ConfigDialogCloseButton {
                        min-width: 22px;
                        max-width: 22px;
                        min-height: 22px;
                        max-height: 22px;
                        border: 1px solid transparent;
                        border-radius: 6px;
                        background: transparent;
                        color: #CBD5E1;
                        font-size: 14px;
                    }
                    QToolButton#ConfigDialogCloseButton:hover {
                        color: #F8FAFC;
                        background: #273449;
                    }
                    """
                )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)

            title_font = ui_font()
            title_font.setPixelSize(14)
            title_font.setWeight(600)

            body_font = ui_font()
            body_font.setPixelSize(12)

            helper_font = ui_font()
            helper_font.setPixelSize(11)

            drag_handle = _DialogDragHandle(self, self) if _DialogDragHandle is not None else QFrame(self)
            drag_handle.setObjectName("WalkerDialogDragHandle")
            drag_handle.setFixedHeight(24)
            top_bar = QHBoxLayout(drag_handle)
            top_bar.setContentsMargins(0, 0, 0, 0)
            top_bar.setSpacing(8)
            top_hint = QLabel(_rt("Configuração visual"), self)
            top_hint.setObjectName("WalkerDialogSubtitle")
            top_hint.setFont(helper_font)
            top_bar.addWidget(top_hint, 0)
            top_bar.addStretch(1)
            close_btn = QToolButton(self)
            close_btn.setObjectName("ConfigDialogCloseButton")
            close_btn.setText("×")
            close_btn.clicked.connect(self.reject)
            top_bar.addWidget(close_btn, 0)
            layout.addWidget(drag_handle, 0)

            title = QLabel(_rt("Configurar canvas"), self)
            title.setObjectName("WalkerDialogTitle")
            title.setFont(title_font)
            layout.addWidget(title, 0)

            subtitle = QLabel(_rt("Ajuste fundo, grade e densidade visual com visual minimalista."), self)
            subtitle.setObjectName("WalkerDialogSubtitle")
            subtitle.setWordWrap(True)
            subtitle.setFont(helper_font)
            layout.addWidget(subtitle, 0)

            card = QFrame(self)
            card.setObjectName("WalkerDialogCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(10)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)

            def _build_label(text: str) -> QLabel:
                label = QLabel(text, card)
                label.setObjectName("WalkerFieldLabel")
                label.setFont(body_font)
                return label

            self.theme_label = _build_label(_rt("Tema"))
            self.theme_combo = QComboBox(card)
            self.theme_combo.setObjectName("WalkerDialogInput")
            self.theme_combo.addItem(_rt("Personalizado"), "custom")
            self.theme_combo.addItem(_rt("Padrão clean"), "clean")
            self.theme_combo.addItem(_rt("Padrão suave"), "soft")
            self.theme_combo.addItem(_rt("Noturno"), "dark")
            grid.addWidget(self.theme_label, 0, 0)
            grid.addWidget(self.theme_combo, 0, 1, 1, 3)

            self.bg_label = _build_label(_rt("Cor do fundo"))
            self.bg_edit = QLineEdit(str(self._initial_style.get("background") or ""), card)
            self.bg_edit.setObjectName("WalkerDialogInput")
            self.bg_preview = QLabel(card)
            set_color_preview_chip(self.bg_preview, self.bg_edit.text(), "#FFFFFF")
            grid.addWidget(self.bg_label, 1, 0)
            grid.addWidget(self.bg_edit, 1, 1, 1, 2)
            grid.addWidget(self.bg_preview, 1, 3)

            self.grid_label = _build_label(_rt("Cor da grade"))
            self.grid_edit = QLineEdit(str(self._initial_style.get("grid_color") or ""), card)
            self.grid_edit.setObjectName("WalkerDialogInput")
            self.grid_preview = QLabel(card)
            set_color_preview_chip(self.grid_preview, self.grid_edit.text(), "#FFFFFF")
            grid.addWidget(self.grid_label, 2, 0)
            grid.addWidget(self.grid_edit, 2, 1, 1, 2)
            grid.addWidget(self.grid_preview, 2, 3)

            self.show_grid_check = QCheckBox(_rt("Mostrar grade no modo de edicao"), card)
            self.show_grid_check.setObjectName("WalkerDialogCheck")
            self.show_grid_check.setFont(body_font)
            self.show_grid_check.setChecked(bool(self._initial_style.get("show_grid", True)))
            grid.addWidget(self.show_grid_check, 3, 0, 1, 4)

            self.grid_size_label = _build_label(_rt("Tamanho da grade"))
            self.grid_size_spin = QSpinBox(card)
            self.grid_size_spin.setObjectName("WalkerDialogInput")
            self.grid_size_spin.setRange(4, 48)
            self.grid_size_spin.setValue(int(self._initial_style.get("grid_size", 8)))
            self.grid_size_spin.setButtonSymbols(QSpinBox.NoButtons)
            self.grid_size_spin.setAlignment(Qt.AlignCenter)
            grid.addWidget(self.grid_size_label, 4, 0)
            grid.addWidget(self.grid_size_spin, 4, 1)

            self.grid_opacity_label = _build_label(_rt("Opacidade da grade (%)"))
            self.grid_opacity_spin = QSpinBox(card)
            self.grid_opacity_spin.setObjectName("WalkerDialogInput")
            self.grid_opacity_spin.setRange(10, 100)
            self.grid_opacity_spin.setValue(int(round(float(self._initial_style.get("grid_opacity", 1.0)) * 100.0)))
            self.grid_opacity_spin.setButtonSymbols(QSpinBox.NoButtons)
            self.grid_opacity_spin.setAlignment(Qt.AlignCenter)
            grid.addWidget(self.grid_opacity_label, 4, 2)
            grid.addWidget(self.grid_opacity_spin, 4, 3)

            card_layout.addLayout(grid)

            palette_bg = QHBoxLayout()
            palette_bg.setContentsMargins(0, 0, 0, 0)
            palette_bg.setSpacing(6)
            palette_bg.addWidget(QLabel(_rt("Paleta fundo"), card))
            bg_quick_colors = ["#FFFFFF", "#F8FAFC", "#F3F4F6", "#F1F5F9", "#111827"]
            for color in bg_quick_colors:
                chip = QPushButton("", card)
                chip.setObjectName("WalkerColorChip")
                chip.setToolTip(color)
                chip.setStyleSheet(
                    f"QPushButton#WalkerColorChip{{background:{color};border:1px solid #D1D5DB;border-radius:6px;}}"
                )
                chip.clicked.connect(lambda checked=False, value=color: self.bg_edit.setText(value))
                palette_bg.addWidget(chip)
            palette_bg.addStretch(1)
            card_layout.addLayout(palette_bg)

            palette_grid = QHBoxLayout()
            palette_grid.setContentsMargins(0, 0, 0, 0)
            palette_grid.setSpacing(6)
            palette_grid.addWidget(QLabel(_rt("Paleta grade"), card))
            grid_quick_colors = ["#FFFFFF", "#E5E7EB", "#D1D5DB", "#9CA3AF", "#6B7280", "#374151"]
            for color in grid_quick_colors:
                chip = QPushButton("", card)
                chip.setObjectName("WalkerColorChip")
                chip.setToolTip(color)
                chip.setStyleSheet(
                    f"QPushButton#WalkerColorChip{{background:{color};border:1px solid #D1D5DB;border-radius:6px;}}"
                )
                chip.clicked.connect(lambda checked=False, value=color: self.grid_edit.setText(value))
                palette_grid.addWidget(chip)
            palette_grid.addStretch(1)
            card_layout.addLayout(palette_grid)

            helper = QLabel(_rt("Dica: use fundo claro com grade suave para um visual limpo."), card)
            helper.setObjectName("WalkerAuxText")
            helper.setWordWrap(True)
            helper.setFont(helper_font)
            card_layout.addWidget(helper, 0)

            layout.addWidget(card, 1)
            harmonize_widget_fonts(self)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(8)
            actions.addStretch(1)

            self.reset_btn = QPushButton(_rt("Restaurar padrao"), self)
            self.reset_btn.setObjectName("WalkerDialogSecondaryButton")
            self.reset_btn.setFont(body_font)
            self.cancel_btn = QPushButton(_rt("Cancelar"), self)
            self.cancel_btn.setObjectName("WalkerDialogSecondaryButton")
            self.cancel_btn.setFont(body_font)
            self.apply_btn = QPushButton(_rt("Aplicar"), self)
            self.apply_btn.setObjectName("WalkerDialogPrimaryButton")
            self.apply_btn.setFont(body_font)

            actions.addWidget(self.reset_btn, 0)
            actions.addWidget(self.cancel_btn, 0)
            actions.addWidget(self.apply_btn, 0)
            layout.addLayout(actions)

            self.bg_edit.textChanged.connect(lambda *_: self._refresh_color_previews())
            self.grid_edit.textChanged.connect(lambda *_: self._refresh_color_previews())
            self.theme_combo.currentIndexChanged.connect(self._handle_preset_changed)
            self.bg_edit.textChanged.connect(lambda *_: self._mark_custom())
            self.grid_edit.textChanged.connect(lambda *_: self._mark_custom())
            self.show_grid_check.toggled.connect(lambda *_: self._mark_custom())
            self.grid_size_spin.valueChanged.connect(lambda *_: self._mark_custom())
            self.grid_opacity_spin.valueChanged.connect(lambda *_: self._mark_custom())
            self.reset_btn.clicked.connect(self._reset_defaults)
            self.cancel_btn.clicked.connect(self.reject)
            self.apply_btn.clicked.connect(self.accept)

        def _refresh_color_previews(self):
            set_color_preview_chip(self.bg_preview, self.bg_edit.text(), "#FFFFFF")
            set_color_preview_chip(self.grid_preview, self.grid_edit.text(), "#FFFFFF")

        def _apply_style_to_controls(self, style_payload: Dict[str, object]):
            normalized = normalize_canvas_style(style_payload, base=default_canvas_style())
            self.bg_edit.setText(str(normalized.get("background") or "#FFFFFF"))
            self.grid_edit.setText(str(normalized.get("grid_color") or "#FFFFFF"))
            self.show_grid_check.setChecked(bool(normalized.get("show_grid", True)))
            self.grid_size_spin.setValue(int(normalized.get("grid_size", 8)))
            self.grid_opacity_spin.setValue(int(round(float(normalized.get("grid_opacity", 1.0)) * 100.0)))
            self._refresh_color_previews()

        def _handle_preset_changed(self, index: int):
            key = str(self.theme_combo.itemData(index) or "")
            if key not in self._presets:
                return
            self._preset_signal_lock = True
            try:
                self._apply_style_to_controls(dict(self._presets[key]))
            finally:
                self._preset_signal_lock = False

        def _mark_custom(self):
            if self._preset_signal_lock:
                return
            custom_index = self.theme_combo.findData("custom")
            if custom_index >= 0 and self.theme_combo.currentIndex() != custom_index:
                self.theme_combo.setCurrentIndex(custom_index)

        def _reset_defaults(self):
            self._preset_signal_lock = True
            try:
                self._apply_style_to_controls(default_canvas_style())
                default_index = self.theme_combo.findData("clean")
                if default_index >= 0:
                    self.theme_combo.setCurrentIndex(default_index)
            finally:
                self._preset_signal_lock = False

        def _collect_style(self) -> Dict[str, object]:
            draft = dict(self._initial_style)
            draft["background"] = normalize_hex_color(self.bg_edit.text(), str(self._initial_style.get("background") or "#FFFFFF"))
            draft["grid_color"] = normalize_hex_color(self.grid_edit.text(), str(self._initial_style.get("grid_color") or "#FFFFFF"))
            draft["show_grid"] = bool(self.show_grid_check.isChecked())
            draft["grid_size"] = int(self.grid_size_spin.value())
            draft["grid_opacity"] = max(0.1, min(1.0, float(self.grid_opacity_spin.value()) / 100.0))
            return normalize_canvas_style(draft, base=default_canvas_style())


    def open_canvas_style_dialog(parent=None, current_style: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:
        dialog = ModelCanvasStyleDialog(parent, current_style=current_style)
        if dialog.exec_() != QDialog.Accepted:
            return None
        return dialog.selected_style()

else:

    class ModelCanvasStyleDialog:  # pragma: no cover - fallback for non-QGIS imports
        pass


    def open_canvas_style_dialog(parent=None, current_style: Optional[Dict[str, object]] = None) -> Optional[Dict[str, object]]:  # pragma: no cover - fallback for non-QGIS imports
        return None


__all__ = [
    "CANVAS_STYLE_KEYS",
    "ModelCanvasStyleDialog",
    "apply_canvas_style_to_source_meta",
    "default_canvas_style",
    "normalize_canvas_style",
    "normalize_hex_color",
    "open_canvas_style_dialog",
    "set_color_preview_chip",
]
