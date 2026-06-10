# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
from typing import Any, List, Optional

from qgis.PyQt.QtCore import QEvent, QObject, QTimer
from qgis.PyQt.QtGui import QFont, QFontDatabase
from qgis.PyQt.QtWidgets import QWidget

from ..utils.logging_utils import log_exception
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "fonts", "Inter")
_FONT_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "Inter-Bold.ttf",
)
_REGISTERED_FAMILIES: Optional[List[str]] = None


def ensure_ui_fonts_registered() -> List[str]:
    global _REGISTERED_FAMILIES
    if _REGISTERED_FAMILIES is not None:
        return list(_REGISTERED_FAMILIES)

    families: List[str] = []
    for filename in _FONT_FILES:
        path = os.path.join(_FONT_DIR, filename)
        if not os.path.exists(path):
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id == -1:
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family and family not in families:
                families.append(family)

    _REGISTERED_FAMILIES = families
    return list(_REGISTERED_FAMILIES)


def ui_font_family(default: str = "Inter") -> str:
    families = ensure_ui_fonts_registered()
    return families[0] if families else default


def ui_font_stack() -> str:
    family = ui_font_family()
    return f'"{family}", sans-serif'


def _qfont_weight(name: str, fallback: int = 50) -> Any:
    try:
        return getattr(QFont.Weight, name)
    except Exception:
        return getattr(QFont, name, fallback)


def _qfont_stretch(name: str, fallback: int = 100) -> Any:
    try:
        return getattr(QFont.Stretch, name)
    except Exception:
        return getattr(QFont, name, fallback)


def _qevent_type(name: str) -> Any:
    try:
        return getattr(QEvent.Type, name)
    except Exception:
        return getattr(QEvent, name, None)


def ui_font(point_size: Optional[int] = None, weight=None) -> QFont:
    font = QFont(ui_font_family())
    if point_size is not None:
        font.setPointSize(point_size)
    if weight is None:
        weight = _qfont_weight("Normal", 50)
    font.setWeight(weight)
    font.setStretch(_qfont_stretch("Unstretched", 100))
    font.setKerning(True)
    return font


def harmonize_font_family(font: Optional[QFont]) -> QFont:
    resolved = QFont(font) if font is not None else QFont()
    resolved.setFamily(ui_font_family())
    resolved.setStretch(_qfont_stretch("Unstretched", 100))
    resolved.setKerning(True)
    return resolved


def harmonize_widget_fonts(root: Optional[QObject]) -> None:
    if root is None:
        return
    widgets: List[QWidget] = []
    if isinstance(root, QWidget):
        widgets.append(root)
    try:
        widgets.extend(root.findChildren(QWidget))
    except Exception:
        log_exception("falha opcional ignorada")
    for widget in widgets:
        try:
            widget.setFont(harmonize_font_family(widget.font()))
        except Exception:
            continue


class _UiFontEnforcer(QObject):
    def eventFilter(self, watched, event):
        if event is not None and event.type() == _qevent_type("ChildAdded"):
            child = event.child()
            if child is not None:
                QTimer.singleShot(0, lambda c=child: harmonize_widget_fonts(c))
        return False


def attach_ui_font_enforcer(root: Optional[QWidget]) -> Optional[QObject]:
    if root is None:
        return None
    existing = getattr(root, "_ui_font_enforcer", None)
    if existing is not None:
        return existing
    enforcer = _UiFontEnforcer(root)
    root.installEventFilter(enforcer)
    setattr(root, "_ui_font_enforcer", enforcer)
    QTimer.singleShot(0, lambda: harmonize_widget_fonts(root))
    return enforcer
