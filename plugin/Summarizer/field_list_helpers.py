from __future__ import annotations

from typing import Any, Dict, Optional

from qgis.PyQt.QtCore import QByteArray, QSize, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QListWidgetItem


_FIELD_SVG_TEMPLATES = {
    "text": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.5 4.5H15L19.5 9V19.125C19.5 20.1605 18.6605 21 17.625 21H7.875C6.83947 21 6 20.1605 6 19.125V6.375C6 5.33947 6.83947 4.5 7.875 4.5H7.5Z" stroke="__COLOR__" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M9 12H16.5M9 15.75H16.5" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round"/>
</svg>""",
    "numeric": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.25 4.5L6.75 19.5M15.75 4.5L14.25 19.5M4.5 9.75H18.75M3.75 14.25H18" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "date": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="4.5" y="5.25" width="15" height="13.5" rx="2" stroke="__COLOR__" stroke-width="1.5"/>
<path d="M7.5 3.75V6.75M16.5 3.75V6.75M4.5 9.75H19.5M8.25 12.75H8.26M12 12.75H12.01M15.75 12.75H15.76M8.25 15.75H8.26M12 15.75H12.01M15.75 15.75H15.76" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round"/>
</svg>""",
    "other": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 6.5V6.5M12 12V12M12 17.5V17.5" stroke="__COLOR__" stroke-width="2.5" stroke-linecap="round"/>
</svg>""",
}

_FIELD_KIND_META: Dict[str, Dict[str, str]] = {
    "text": {"label": "Texto", "badge": "TXT", "color": "#2563EB", "accent": "#DBEAFE"},
    "numeric": {"label": "Numérico", "badge": "123", "color": "#9333EA", "accent": "#F3E8FF"},
    "date": {"label": "Data", "badge": "DATA", "color": "#D97706", "accent": "#FEF3C7"},
    "other": {"label": "Outros", "badge": "OUT", "color": "#64748B", "accent": "#E5E7EB"},
}


def normalize_field_kind(kind: Optional[str]) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized in {"numeric", "number", "integer", "float", "double", "decimal", "real"}:
        return "numeric"
    if normalized in {"date", "datetime", "time"}:
        return "date"
    if normalized == "other":
        return "other"
    return "text"


def field_kind_from_data_type(data_type: Optional[str]) -> str:
    return normalize_field_kind(data_type)


def field_kind_from_field_def(field_def: Any) -> str:
    if field_def is None:
        return "other"
    try:
        if bool(field_def.isNumeric()):
            return "numeric"
    except Exception:
        pass
    type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
    if any(token in type_name for token in ("date", "time")):
        return "date"
    if any(token in type_name for token in ("int", "double", "float", "real", "numeric", "decimal")):
        return "numeric"
    if any(token in type_name for token in ("string", "text", "char")):
        return "text"
    return "other"


def field_kind_label(kind: Optional[str]) -> str:
    return _FIELD_KIND_META.get(normalize_field_kind(kind), _FIELD_KIND_META["other"])["label"]


def field_kind_badge(kind: Optional[str]) -> str:
    return _FIELD_KIND_META.get(normalize_field_kind(kind), _FIELD_KIND_META["other"])["badge"]


def field_kind_color(kind: Optional[str]) -> str:
    return _FIELD_KIND_META.get(normalize_field_kind(kind), _FIELD_KIND_META["other"])["color"]


def field_kind_accent(kind: Optional[str]) -> str:
    return _FIELD_KIND_META.get(normalize_field_kind(kind), _FIELD_KIND_META["other"])["accent"]


def field_kind_icon(kind: Optional[str], size: int = 14) -> QIcon:
    kind = normalize_field_kind(kind)
    template = _FIELD_SVG_TEMPLATES.get(kind, _FIELD_SVG_TEMPLATES["other"])
    icon = QIcon()
    for mode, color in (
        (QIcon.Normal, field_kind_color(kind)),
        (QIcon.Active, field_kind_color(kind)),
        (QIcon.Selected, field_kind_color(kind)),
        (QIcon.Disabled, "#cbd5e1"),
    ):
        svg_data = QByteArray(template.replace("__COLOR__", color).encode("utf-8"))
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def configure_field_item(
    item: QListWidgetItem,
    *,
    display_name: str,
    kind: Optional[str],
    tooltip: str = "",
    payload: Optional[Dict[str, Any]] = None,
    role: int = Qt.UserRole,
    include_badge: bool = False,
):
    kind_key = normalize_field_kind(kind)
    badge = field_kind_badge(kind_key)
    label = f"{badge}  {display_name}" if include_badge else str(display_name or "")
    item.setText(label)
    item.setIcon(field_kind_icon(kind_key))
    item.setForeground(QColor(field_kind_color(kind_key)))
    item.setToolTip(str(tooltip or f"{display_name}\nTipo: {field_kind_label(kind_key)}"))
    item.setData(role, dict(payload or {}))
    item.setData(Qt.UserRole + 1, kind_key)
    item.setData(Qt.UserRole + 2, str(display_name or ""))
    item.setData(Qt.UserRole + 3, field_kind_label(kind_key))
    item.setData(Qt.UserRole + 4, field_kind_badge(kind_key))
    item.setSizeHint(QSize(0, 24))
    return item
