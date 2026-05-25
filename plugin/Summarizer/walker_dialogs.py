# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Iterable, Optional

from qgis.PyQt.QtCore import QEvent, QObject, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
from .utils.i18n_runtime import tr_text as _rt
from .utils.logging_utils import log_exception
from .utils.window_theme import apply_windows_rounded_corners


WALKER_PANEL_RADIUS = 14
WALKER_BORDER = "#E5E7EB"
WALKER_TEXT = "#111827"
WALKER_MUTED = "#6B7280"
WALKER_HOVER = "#F3F4F6"
WALKER_PRIMARY = "#111111"


WALKER_DIALOG_STYLE = """
QDialog#WalkerDialog,
QDialog[walkerDialog="true"] {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
}
QFrame#WalkerDialogPanel,
QFrame[walkerPanel="true"] {
    background: #FFFFFF;
    border: none;
    border-radius: 14px;
}
QLabel#WalkerDialogTitle,
QLabel[walkerTitle="true"] {
    color: #111827;
    font-size: 17px;
    font-weight: 600;
    background: transparent;
}
QLabel#WalkerDialogLabel,
QLabel[walkerLabel="true"] {
    color: #1F2937;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel[walkerMuted="true"] {
    color: #6B7280;
    font-size: 12px;
    font-weight: 400;
    background: transparent;
}
QLabel#WalkerMessageBody {
    color: #111827;
    font-size: 12px;
    font-weight: 400;
    background: transparent;
}
QLineEdit,
QComboBox,
QSpinBox,
QPlainTextEdit,
QTextEdit {
    min-height: 34px;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0 12px;
    background: #FFFFFF;
    color: #111827;
    font-size: 12px;
    selection-background-color: #111827;
    selection-color: #FFFFFF;
}
QPlainTextEdit,
QTextEdit {
    padding: 8px 10px;
}
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QPlainTextEdit:focus,
QTextEdit:focus {
    border: 2px solid #9CA3AF;
    padding: 0 11px;
    background: #FFFFFF;
}
QPlainTextEdit:focus,
QTextEdit:focus {
    padding: 7px 9px;
}
QComboBox::drop-down {
    width: 26px;
    border: none;
}
QComboBox QAbstractItemView {
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    background: #FFFFFF;
    color: #111827;
    padding: 4px;
    selection-background-color: #F3F4F6;
    selection-color: #111827;
    outline: none;
}
QCheckBox {
    color: #111827;
    font-size: 12px;
    font-weight: 400;
    background: transparent;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #9CA3AF;
    border-radius: 3px;
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #111111;
    border-color: #111111;
}
QRadioButton {
    color: #111827;
    font-size: 12px;
    font-weight: 400;
    background: transparent;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #9CA3AF;
    border-radius: 7px;
    background: #FFFFFF;
}
QRadioButton::indicator:checked {
    border: 4px solid #111111;
    background: #FFFFFF;
}
QGroupBox {
    color: #111827;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    background: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    background: #FFFFFF;
}
QPushButton {
    min-width: 82px;
    min-height: 34px;
    border-radius: 7px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 500;
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    color: #111827;
}
QPushButton:hover {
    background: #F9FAFB;
    border-color: #D1D5DB;
}
QPushButton#SlimPrimaryButton,
QPushButton#WalkerPrimaryButton {
    background: #111111;
    border: 1px solid #111111;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#SlimPrimaryButton:hover,
QPushButton#WalkerPrimaryButton:hover {
    background: #262626;
    border-color: #262626;
}
QPushButton#SlimSecondaryButton,
QPushButton#WalkerSecondaryButton {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    color: #111827;
}
QToolButton#WalkerDialogCloseButton {
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #6B7280;
    font-size: 16px;
}
QToolButton#WalkerDialogCloseButton:hover {
    background: #F3F4F6;
    color: #111827;
}
QListWidget,
QTableWidget {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    background: #FFFFFF;
    color: #111827;
    font-size: 12px;
}
QListWidget::item {
    min-height: 28px;
    padding: 0 8px;
    border-radius: 6px;
}
QListWidget::item:selected,
QListWidget::item:hover {
    background: #F3F4F6;
    color: #111827;
}
"""


WALKER_MENU_STYLE = """
QMenu {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 4px;
    color: #111827;
    font-size: 12px;
}
QMenu::item {
    min-height: 28px;
    padding: 5px 28px 5px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #F3F4F6;
    color: #111827;
}
QMenu::separator {
    height: 1px;
    background: #E5E7EB;
    margin: 4px 6px;
}
"""


WALKER_COMBO_POPUP_STYLE = """
QListView#WalkerComboPopup {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 4px;
    color: #111827;
    font-size: 12px;
    outline: none;
}
QListView#WalkerComboPopup::item {
    min-height: 28px;
    padding: 5px 28px 5px 12px;
    border-radius: 6px;
    color: #111827;
    background: transparent;
}
QListView#WalkerComboPopup::item:selected,
QListView#WalkerComboPopup::item:hover {
    background: #F3F4F6;
    color: #111827;
}
"""


def walker_dialog_flags():
    flags = Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    try:
        flags |= Qt.NoDropShadowWindowHint
    except Exception:
        pass
    return flags


def _disable_window_shadow(widget: QWidget) -> None:
    try:
        widget.setWindowFlags(widget.windowFlags() | Qt.NoDropShadowWindowHint)
    except Exception:
        log_exception("falha opcional ignorada")
    try:
        widget.setGraphicsEffect(None)
    except Exception:
        log_exception("falha opcional ignorada")


def _walker_overlay_parent(dialog: QDialog) -> Optional[QWidget]:
    parent = dialog.parentWidget()
    if parent is None:
        return None
    try:
        window = parent.window()
        if isinstance(window, QWidget):
            return window
    except Exception:
        log_exception("falha opcional ignorada")
    return parent


def center_dialog_on_parent(dialog: QDialog) -> None:
    parent = _walker_overlay_parent(dialog) or dialog.parentWidget()
    if parent is None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        dialog.move(rect.center().x() - dialog.width() // 2, rect.center().y() - dialog.height() // 2)
        return
    try:
        center = parent.mapToGlobal(parent.rect().center())
        dialog.move(center.x() - dialog.width() // 2, center.y() - dialog.height() // 2)
    except Exception:
        log_exception("falha opcional ignorada")


def show_walker_modal_overlay(dialog: QDialog) -> Optional[QFrame]:
    parent = _walker_overlay_parent(dialog)
    if parent is None:
        return None
    overlay = QFrame(parent)
    overlay.setObjectName("WalkerModalOverlay")
    overlay.setStyleSheet("QFrame#WalkerModalOverlay { background: rgba(0, 0, 0, 128); }")
    overlay.setGeometry(parent.rect())
    overlay.show()
    overlay.raise_()
    dialog.raise_()
    return overlay


def apply_walker_dialog(widget: QWidget) -> None:
    widget.setProperty("walkerDialog", True)
    widget.setStyleSheet(WALKER_DIALOG_STYLE)
    widget.setFont(ui_font(10))
    try:
        widget.setAttribute(Qt.WA_StyledBackground, True)
    except Exception:
        pass
    harmonize_widget_fonts(widget)
    try:
        for combo in widget.findChildren(QComboBox):
            apply_walker_combo(combo)
    except Exception:
        log_exception("falha opcional ignorada")
    if isinstance(widget, QDialog):
        apply_windows_rounded_corners(widget)
        QTimer.singleShot(0, lambda: apply_windows_rounded_corners(widget))


class _WalkerModalChromeFilter(QObject):
    def __init__(self, dialog: QDialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.overlay: Optional[QFrame] = None

    def eventFilter(self, watched, event):  # noqa: N802 - Qt naming style
        if watched is not self.dialog:
            return False
        event_type = event.type()
        if event_type == QEvent.Show:
            self._show_overlay()
            center_dialog_on_parent(self.dialog)
            apply_walker_dialog(self.dialog)
            self.dialog.raise_()
            QTimer.singleShot(0, self.dialog.raise_)
        elif event_type in (QEvent.Hide, QEvent.Close):
            self._hide_overlay()
        elif event_type == QEvent.Resize and self.overlay is not None:
            parent = _walker_overlay_parent(self.dialog)
            if parent is not None:
                self.overlay.setGeometry(parent.rect())
        return False

    def _show_overlay(self) -> None:
        self._hide_overlay()
        self.overlay = show_walker_modal_overlay(self.dialog)

    def _hide_overlay(self) -> None:
        if self.overlay is None:
            return
        self.overlay.hide()
        self.overlay.deleteLater()
        self.overlay = None


def install_walker_modal_chrome(dialog: QDialog) -> None:
    dialog.setProperty("walkerDialog", True)
    dialog.setWindowFlags(walker_dialog_flags())
    _disable_window_shadow(dialog)
    dialog.setAttribute(Qt.WA_StyledBackground, True)
    apply_walker_dialog(dialog)
    if getattr(dialog, "_walker_modal_chrome_filter", None) is None:
        event_filter = _WalkerModalChromeFilter(dialog)
        dialog._walker_modal_chrome_filter = event_filter
        dialog.installEventFilter(event_filter)


def add_walker_close_button(layout: QHBoxLayout, dialog: QDialog) -> QToolButton:
    button = QToolButton(dialog)
    button.setObjectName("WalkerDialogCloseButton")
    button.setText(chr(215))
    button.clicked.connect(dialog.reject)
    layout.addWidget(button, 0, Qt.AlignTop)
    return button


def apply_walker_buttons(
    *,
    primary: Iterable[Optional[QPushButton]] = (),
    secondary: Iterable[Optional[QPushButton]] = (),
) -> None:
    for button in primary:
        if button is not None:
            button.setObjectName("WalkerPrimaryButton")
    for button in secondary:
        if button is not None:
            button.setObjectName("WalkerSecondaryButton")


def apply_walker_menu(menu: QMenu) -> QMenu:
    _disable_window_shadow(menu)
    try:
        menu.setAttribute(Qt.WA_StyledBackground, True)
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        menu.setAutoFillBackground(False)
    except Exception:
        log_exception("falha opcional ignorada")
    try:
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    except Exception:
        log_exception("falha opcional ignorada")
    menu.setStyleSheet(WALKER_MENU_STYLE)
    menu.setFont(ui_font(10))
    return menu


def apply_walker_combo(combo: QComboBox) -> QComboBox:
    combo.setFont(ui_font(10))
    try:
        view = combo.view()
        if not isinstance(view, QListView):
            view = QListView(combo)
            combo.setView(view)
        view.setObjectName("WalkerComboPopup")
        view.setFont(ui_font(10))
        view.setFrameShape(QFrame.NoFrame)
        view.setAttribute(Qt.WA_StyledBackground, True)
        view.setAttribute(Qt.WA_TranslucentBackground, True)
        view.setAutoFillBackground(False)
        view.viewport().setAutoFillBackground(False)
        view.setStyleSheet(WALKER_COMBO_POPUP_STYLE)
        try:
            view.setWindowFlags(view.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        except Exception:
            log_exception("falha opcional ignorada")
    except Exception:
        log_exception("falha opcional ignorada")
    return combo


class WalkerModalDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, *, width: int = 500):
        super().__init__(parent)
        self._walker_overlay: Optional[QFrame] = None
        self.setObjectName("WalkerDialog")
        self.setModal(True)
        self.setWindowFlags(walker_dialog_flags())
        _disable_window_shadow(self)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(width)
        self.setFont(ui_font(10))
        self._font_enforcer = attach_ui_font_enforcer(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("WalkerDialogPanel")
        root.addWidget(self.panel)

        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(24, 22, 24, 22)
        self.panel_layout.setSpacing(10)
        apply_walker_dialog(self)

    def showEvent(self, event):  # noqa: N802 - Qt naming style
        super().showEvent(event)
        self._hide_walker_overlay()
        self._walker_overlay = show_walker_modal_overlay(self)
        center_dialog_on_parent(self)
        apply_walker_dialog(self)
        self.raise_()
        QTimer.singleShot(0, self._ensure_visible)

    def closeEvent(self, event):  # noqa: N802 - Qt naming style
        self._hide_walker_overlay()
        super().closeEvent(event)

    def hideEvent(self, event):  # noqa: N802 - Qt naming style
        self._hide_walker_overlay()
        super().hideEvent(event)

    def _hide_walker_overlay(self) -> None:
        overlay = self._walker_overlay
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
            self._walker_overlay = None

    def _ensure_visible(self) -> None:
        if not self.isVisible():
            return
        apply_windows_rounded_corners(self)
        self.setWindowOpacity(1.0)
        self.panel.show()
        self.panel.raise_()
        self.update()

    def add_header(self, title: str, icon: Optional[QIcon] = None) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(8)
        if icon is not None and not icon.isNull():
            icon_label = QLabel(self.panel)
            icon_label.setPixmap(icon.pixmap(18, 18))
            header.addWidget(icon_label, 0, Qt.AlignVCenter)
        title_label = QLabel(title, self.panel)
        title_label.setObjectName("WalkerDialogTitle")
        header.addWidget(title_label, 1, Qt.AlignVCenter)
        close_btn = QToolButton(self.panel)
        close_btn.setObjectName("WalkerDialogCloseButton")
        close_btn.setText(chr(215))
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignTop)
        self.panel_layout.addLayout(header)
        return header


class WalkerMessageDialog(WalkerModalDialog):
    def __init__(
        self,
        title: str,
        text: str,
        parent: Optional[QWidget] = None,
        *,
        icon: Optional[QIcon] = None,
        buttons: int = QMessageBox.Ok,
        default_button: int = QMessageBox.Ok,
    ):
        super().__init__(parent, width=500)
        self.setWindowTitle(title)
        self._clicked = QMessageBox.NoButton
        self.add_header(title, icon)

        body = QLabel(text, self.panel)
        body.setObjectName("WalkerMessageBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.panel_layout.addWidget(body)
        self.panel_layout.addSpacing(8)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)
        for standard in self._button_order(buttons):
            button = QPushButton(self._button_text(standard), self.panel)
            is_primary = int(standard) == int(default_button) or standard in (QMessageBox.Ok, QMessageBox.Yes)
            apply_walker_buttons(primary=[button] if is_primary else [], secondary=[] if is_primary else [button])
            button.clicked.connect(lambda _checked=False, value=standard: self._finish(value))
            row.addWidget(button)
            if int(standard) == int(default_button):
                button.setDefault(True)
        self.panel_layout.addLayout(row)

    def _finish(self, button: int) -> None:
        self._clicked = button
        if button in (QMessageBox.Cancel, QMessageBox.No, QMessageBox.Close):
            self.reject()
        else:
            self.accept()

    def clicked_button(self) -> int:
        return int(self._clicked or QMessageBox.NoButton)

    @staticmethod
    def _button_order(mask: int) -> list[int]:
        order = [
            QMessageBox.Yes,
            QMessageBox.No,
            QMessageBox.Ok,
            QMessageBox.Cancel,
            QMessageBox.Save,
            QMessageBox.Discard,
            QMessageBox.Close,
        ]
        result = [button for button in order if int(mask) & int(button)]
        return result or [QMessageBox.Ok]

    @staticmethod
    def _button_text(button: int) -> str:
        mapping = {
            int(QMessageBox.Ok): "OK",
            int(QMessageBox.Cancel): _rt("Cancelar"),
            int(QMessageBox.Yes): _rt("Sim"),
            int(QMessageBox.No): _rt("Não"),
            int(QMessageBox.Save): _rt("Salvar"),
            int(QMessageBox.Discard): _rt("Descartar"),
            int(QMessageBox.Close): _rt("Fechar"),
        }
        return mapping.get(int(button), "OK")


def _standard_icon(parent: Optional[QWidget], icon: QStyle.StandardPixmap) -> QIcon:
    widget = parent if parent is not None else QApplication.activeWindow()
    style = widget.style() if widget is not None else QApplication.style()
    return style.standardIcon(icon)


def walker_message(parent: Optional[QWidget], title: str, text: str, *, icon: Optional[QIcon] = None) -> None:
    dialog = WalkerMessageDialog(title, text, parent, icon=icon, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok)
    dialog.exec_()


def walker_info(parent: Optional[QWidget], title: str, text: str) -> None:
    walker_message(parent, title, text, icon=_standard_icon(parent, QStyle.SP_MessageBoxInformation))


def walker_warning(parent: Optional[QWidget], title: str, text: str) -> None:
    walker_message(parent, title, text, icon=_standard_icon(parent, QStyle.SP_MessageBoxWarning))


def walker_error(parent: Optional[QWidget], title: str, text: str) -> None:
    walker_message(parent, title, text, icon=_standard_icon(parent, QStyle.SP_MessageBoxCritical))


def walker_confirm(
    parent: Optional[QWidget],
    title: str,
    text: str,
    *,
    buttons: int = QMessageBox.Yes | QMessageBox.No,
    default_button: int = QMessageBox.No,
) -> int:
    dialog = WalkerMessageDialog(
        title,
        text,
        parent,
        icon=_standard_icon(parent, QStyle.SP_MessageBoxQuestion),
        buttons=buttons,
        default_button=default_button,
    )
    dialog.exec_()
    return dialog.clicked_button()


class WalkerMessageBox:
    Ok = QMessageBox.Ok
    Cancel = QMessageBox.Cancel
    Yes = QMessageBox.Yes
    No = QMessageBox.No
    Save = QMessageBox.Save
    Discard = QMessageBox.Discard
    Close = QMessageBox.Close
    Abort = QMessageBox.Abort
    Retry = QMessageBox.Retry
    Ignore = QMessageBox.Ignore
    NoButton = QMessageBox.NoButton

    @staticmethod
    def information(parent: Optional[QWidget], title: str, text: str, *args, **kwargs) -> int:
        del args, kwargs
        walker_info(parent, title, text)
        return int(QMessageBox.Ok)

    @staticmethod
    def warning(parent: Optional[QWidget], title: str, text: str, *args, **kwargs) -> int:
        del args, kwargs
        walker_warning(parent, title, text)
        return int(QMessageBox.Ok)

    @staticmethod
    def critical(parent: Optional[QWidget], title: str, text: str, *args, **kwargs) -> int:
        del args, kwargs
        walker_error(parent, title, text)
        return int(QMessageBox.Ok)

    @staticmethod
    def question(
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: int = QMessageBox.Yes | QMessageBox.No,
        defaultButton: int = QMessageBox.No,
        *args,
        **kwargs,
    ) -> int:
        del args
        if "default_button" in kwargs:
            defaultButton = kwargs.pop("default_button")
        if "defaultButton" in kwargs:
            defaultButton = kwargs.pop("defaultButton")
        return walker_confirm(parent, title, text, buttons=buttons, default_button=defaultButton)
