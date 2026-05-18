from __future__ import annotations

from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtWidgets import QToolButton, QWidget

from ..utils.resources import svg_icon


_ICON_CANDIDATES = (
    "/mActionMapSettings.svg",
    "/mActionAddMapLayer.svg",
    "/mActionZoomFullExtent.svg",
    "/mActionZoomToLayer.svg",
    "/mActionMapTips.svg",
)


def _theme_icon():
    try:
        icon = svg_icon("PresentationMap.svg")
        if icon is not None and not icon.isNull():
            return icon
    except Exception:
        pass
    for icon_name in _ICON_CANDIDATES:
        try:
            icon = QgsApplication.getThemeIcon(icon_name)
        except Exception:
            icon = None
        if icon is not None and not icon.isNull():
            return icon
    return None


def create_presentation_button(parent: Optional[QWidget], controller) -> QToolButton:
    button = QToolButton(parent)
    button.setObjectName("PresentationMapButton")
    button.setCheckable(True)
    button.setAutoRaise(False)
    button.setCursor(Qt.PointingHandCursor)
    button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setText("Apresentar")
    button.setToolTip("Apresentar com mapa ao lado do dashboard")
    button.setIconSize(QSize(16, 16))
    button.setStyleSheet(
        """
        QToolButton#PresentationMapButton {
            padding: 4px 10px;
            border: 1px solid transparent;
            border-radius: 6px;
            background: transparent;
        }
        QToolButton#PresentationMapButton:hover {
            background: rgba(108, 76, 241, 0.08);
        }
        QToolButton#PresentationMapButton:checked {
            background: rgba(108, 76, 241, 0.24);
            border-color: rgba(108, 76, 241, 0.62);
            color: #2b1f75;
            font-weight: 400;
        }
        QToolButton#PresentationMapButton:checked:hover {
            background: rgba(108, 76, 241, 0.30);
        }
        """
    )

    icon = _theme_icon()
    if icon is not None:
        button.setIcon(icon)

    if controller is not None:
        button.toggled.connect(controller.toggle)
        state_changed = getattr(controller, "stateChanged", None)
        if state_changed is not None:
            state_changed.connect(lambda checked, btn=button: _sync_checked_state(btn, checked))
        try:
            button.setChecked(bool(getattr(controller, "is_active", lambda: False)()))
        except Exception:
            pass

    return button


def _sync_checked_state(button: QToolButton, checked: bool):
    if button is None:
        return
    try:
        button.blockSignals(True)
        button.setChecked(bool(checked))
    finally:
        try:
            button.blockSignals(False)
        except Exception:
            pass
