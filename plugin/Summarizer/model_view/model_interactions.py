from __future__ import annotations

from qgis.PyQt.QtCore import QPoint


def event_point(event, *, prefer_global: bool = False) -> QPoint:
    """Return a QPoint extracted from a Qt event with broad compatibility."""
    if event is None:
        return QPoint()

    if prefer_global:
        try:
            pos = event.globalPosition()
            return QPoint(int(pos.x()), int(pos.y()))
        except Exception:
            try:
                return event.globalPos()
            except Exception:
                return QPoint()

    try:
        pos = event.position()
        return QPoint(int(pos.x()), int(pos.y()))
    except Exception:
        try:
            return event.pos()
        except Exception:
            return QPoint()
