from __future__ import annotations

import os

from qgis.PyQt.QtCore import QByteArray, QRectF, QSettings, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QWidget

from ..utils.logging_utils import log_exception
from ..utils.resources import svg_icon

_MODEL_TRASH_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14.7404 9L14.3942 18M9.60577 18L9.25962 9M19.2276 5.79057C19.5696 5.84221 19.9104 5.89747 20.25 5.95629M19.2276 5.79057L18.1598 19.6726C18.0696 20.8448 17.0921 21.75 15.9164 21.75H8.08357C6.90786 21.75 5.93037 20.8448 5.8402 19.6726L4.77235 5.79057M19.2276 5.79057C18.0812 5.61744 16.9215 5.48485 15.75 5.39432M3.75 5.95629C4.08957 5.89747 4.43037 5.84221 4.77235 5.79057M4.77235 5.79057C5.91878 5.61744 7.07849 5.48485 8.25 5.39432M15.75 5.39432V4.47819C15.75 3.29882 14.8393 2.31423 13.6606 2.27652C13.1092 2.25889 12.5556 2.25 12 2.25C11.4444 2.25 10.8908 2.25889 10.3394 2.27652C9.16065 2.31423 8.25 3.29882 8.25 4.47819V5.39432M15.75 5.39432C14.5126 5.2987 13.262 5.25 12 5.25C10.738 5.25 9.48744 5.2987 8.25 5.39432" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
_MODEL_FIELDS_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M20.25 6.375C20.25 8.65317 16.5563 10.5 12 10.5C7.44365 10.5 3.75 8.65317 3.75 6.375M20.25 6.375C20.25 4.09683 16.5563 2.25 12 2.25C7.44365 2.25 3.75 4.09683 3.75 6.375M20.25 6.375V17.625C20.25 19.9032 16.5563 21.75 12 21.75C7.44365 21.75 3.75 19.9032 3.75 17.625V6.375M20.25 6.375V10.125M3.75 6.375V10.125M20.25 10.125V13.875C20.25 16.1532 16.5563 18 12 18C7.44365 18 3.75 16.1532 3.75 13.875V10.125M20.25 10.125C20.25 12.4032 16.5563 14.25 12 14.25C7.44365 14.25 3.75 12.4032 3.75 10.125" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def _is_dark_theme() -> bool:
    try:
        return str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower() == "dark"
    except Exception:
        return False


def _model_theme_color(name: str) -> str:
    dark = {
        "app": "#0B1020",
        "surface": "#111827",
        "surface_2": "#172033",
        "hover": "#1F2A3D",
        "border": "#334155",
        "border_soft": "rgba(148, 163, 184, 0.22)",
        "text": "#F8FAFC",
        "muted": "#CBD5E1",
        "checked": "#312E81",
        "checked_border": "#7C6CFF",
    }
    light = {
        "app": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_2": "#F8FAFC",
        "hover": "#F8FAFC",
        "border": "#DCE3EC",
        "border_soft": "rgba(17, 24, 39, 0.08)",
        "text": "#0F172A",
        "muted": "#64748B",
        "checked": "#EAF4FF",
        "checked_border": "#93C5FD",
    }
    return (dark if _is_dark_theme() else light).get(name, light["surface"])


def _force_model_white_background(widget: QWidget):
    widget.setAttribute(Qt.WA_StyledBackground, True)
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(widget.foregroundRole(), QColor(_model_theme_color("text")))
    palette.setColor(widget.backgroundRole(), QColor(_model_theme_color("surface")))
    palette.setColor(QPalette.Window, QColor(_model_theme_color("surface")))
    palette.setColor(QPalette.Base, QColor(_model_theme_color("surface")))
    palette.setColor(QPalette.AlternateBase, QColor(_model_theme_color("surface_2")))
    widget.setPalette(palette)


def _model_builder_trash_icon(size: int = 14) -> QIcon:
    icon = QIcon()
    for mode, color in (
        (QIcon.Normal, "#EF4444"),
        (QIcon.Active, "#DC2626"),
        (QIcon.Selected, "#DC2626"),
        (QIcon.Disabled, "#FCA5A5"),
    ):
        svg_data = QByteArray(_MODEL_TRASH_SVG.replace("__COLOR__", color).encode("utf-8"))
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def _model_panel_fields_icon(size: int = 14) -> QIcon:
    icon = QIcon()
    normal = "#CBD5E1" if _is_dark_theme() else "#475569"
    active = "#F8FAFC" if _is_dark_theme() else "#334155"
    disabled = "#64748B" if _is_dark_theme() else "#CBD5E1"
    for mode, color in (
        (QIcon.Normal, normal),
        (QIcon.Active, active),
        (QIcon.Selected, active),
        (QIcon.Disabled, disabled),
    ):
        svg_data = QByteArray(_MODEL_FIELDS_SVG.replace("__COLOR__", color).encode("utf-8"))
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def _model_panel_chevron_icon(direction: str = "right", size: int = 20) -> QIcon:
    path_d = "M9 5 L15 12 L9 19" if str(direction or "").lower() == "right" else "M15 5 L9 12 L15 19"
    template = (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{path_d}" stroke="__COLOR__" stroke-width="2.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )
    icon = QIcon()
    normal = "#CBD5E1" if _is_dark_theme() else "#334155"
    active = "#F8FAFC" if _is_dark_theme() else "#111827"
    disabled = "#64748B" if _is_dark_theme() else "#CBD5E1"
    for mode, color in (
        (QIcon.Normal, normal),
        (QIcon.Active, active),
        (QIcon.Selected, active),
        (QIcon.Disabled, disabled),
    ):
        try:
            svg_data = QByteArray(template.replace("__COLOR__", color).encode("utf-8"))
            renderer = QSvgRenderer(svg_data)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap, mode)
        except Exception:
            log_exception("falha opcional ignorada")
    return icon


def _model_tinted_svg_icon(icon_name: str, size: int = 18, accent_color: str = "") -> QIcon:
    plugin_root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(plugin_root, "resources", "SVG", icon_name)
    if not os.path.exists(path):
        return svg_icon(icon_name)
    icon = QIcon()
    accent = QColor(str(accent_color or ""))
    if accent.isValid():
        normal = accent.name()
        active = accent.lighter(112).name()
        disabled = accent.lighter(165).name()
    else:
        normal = "#E5E7EB" if _is_dark_theme() else "#334155"
        active = "#FFFFFF" if _is_dark_theme() else "#111827"
        disabled = "#64748B" if _is_dark_theme() else "#CBD5E1"
    for mode, color in (
        (QIcon.Normal, normal),
        (QIcon.Active, active),
        (QIcon.Selected, active),
        (QIcon.Disabled, disabled),
    ):
        try:
            with open(path, "rb") as handle:
                renderer = QSvgRenderer(QByteArray(handle.read()))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            viewbox = renderer.viewBoxF()
            if viewbox.isValid() and viewbox.width() > 0 and viewbox.height() > 0:
                scale = min(size / viewbox.width(), size / viewbox.height()) * 0.9
                target_w = viewbox.width() * scale
                target_h = viewbox.height() * scale
                renderer.render(painter, QRectF((size - target_w) / 2, (size - target_h) / 2, target_w, target_h))
            else:
                renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(color))
            painter.end()
            icon.addPixmap(pixmap, mode)
        except Exception:
            log_exception("falha opcional ignorada")
            return svg_icon(icon_name)
    return icon


def fill_model_theme_tokens(style: str) -> str:
    replacements = {
        "__CHECKED_BORDER__": _model_theme_color("checked_border"),
        "__BORDER_SOFT__": _model_theme_color("border_soft"),
        "__SURFACE_2__": _model_theme_color("surface_2"),
        "__CHECKED__": _model_theme_color("checked"),
        "__SURFACE__": _model_theme_color("surface"),
        "__BORDER__": _model_theme_color("border"),
        "__MUTED__": _model_theme_color("muted"),
        "__HOVER__": _model_theme_color("hover"),
        "__TEXT__": _model_theme_color("text"),
    }
    for token, value in replacements.items():
        style = style.replace(token, value)
    return style


__all__ = [
    "_force_model_white_background",
    "_is_dark_theme",
    "_model_builder_trash_icon",
    "_model_panel_chevron_icon",
    "_model_panel_fields_icon",
    "_model_theme_color",
    "_model_tinted_svg_icon",
    "fill_model_theme_tokens",
]
