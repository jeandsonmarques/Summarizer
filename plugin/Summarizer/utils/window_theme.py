from __future__ import annotations

import sys

from qgis.PyQt.QtWidgets import QWidget


def apply_windows_title_bar_theme(widget: QWidget, dark: bool) -> bool:
    """Ask Windows to draw a dark native title bar for this Qt window."""
    if widget is None or not sys.platform.startswith("win"):
        return False
    try:
        hwnd = int(widget.winId())
    except Exception:
        return False
    if not hwnd:
        return False
    try:
        import ctypes

        value = ctypes.c_int(1 if dark else 0)
        # Windows 10 20H1+ uses 20; older builds used 19.
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_int(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if result == 0:
                return True
    except Exception:
        return False
    return False
