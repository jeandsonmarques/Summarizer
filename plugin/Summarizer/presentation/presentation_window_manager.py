# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Optional

from qgis.PyQt.QtCore import QObject, QRect, Qt
from qgis.PyQt.QtWidgets import QFrame, QSizePolicy, QSplitter, QToolBar, QVBoxLayout, QWidget

from ..utils.logging_utils import log_exception


class PresentationWindowManager(QObject):
    """Manages the embedded presentation map layout inside Summarizer."""

    def __init__(self, iface, plugin_window):
        super().__init__(plugin_window)
        self.iface = iface
        self.plugin_window = plugin_window
        self._saved_plugin_state: Optional[dict] = None
        self._map_panel: Optional[QFrame] = None
        self._map_toolbar: Optional[QToolBar] = None
        self._embedded_canvas = None
        self._splitter: Optional[QSplitter] = None
        self._content_frame: Optional[QWidget] = None
        self._content_insert_index: Optional[int] = None
        self._active = False

    def save_window_state(self):
        plugin_window = self._plugin_window()
        if plugin_window is None:
            return False
        if self._saved_plugin_state is None:
            self._saved_plugin_state = self._capture_window_state(plugin_window)
        return self._saved_plugin_state is not None

    def restore_window_state(self):
        plugin_window = self._plugin_window()
        if plugin_window is None:
            self._clear_state()
            return False
        restored = self._restore_window_state(plugin_window, self._saved_plugin_state)
        self._clear_state()
        return restored

    def enter_side_by_side_layout(self, canvas=None):
        if not self.save_window_state():
            return False
        if canvas is None:
            self.restore_window_state()
            return False
        if not self.attach_embedded_map_canvas(canvas):
            self.restore_window_state()
            return False
        self._active = True
        return True

    def exit_side_by_side_layout(self):
        if not self._has_saved_state():
            self._active = False
            return False
        self.detach_embedded_map_canvas()
        restored = self.restore_window_state()
        self._active = False
        return restored

    def cleanup(self):
        try:
            self.exit_side_by_side_layout()
        finally:
            self._clear_state()
            self._active = False

    def is_active(self):
        return bool(self._active)

    def attach_embedded_map_canvas(self, canvas):
        if canvas is None:
            return False
        central = self._central_frame()
        if central is None:
            return False
        layout = central.layout()
        if layout is None:
            return False

        if self._map_panel is None:
            self._map_panel = self._create_map_panel(central)

        if not self._ensure_splitter_layout(central, layout, self._map_panel):
            return False

        panel_layout = self._map_panel.layout()
        if panel_layout is None:
            return False

        self._ensure_map_toolbar(panel_layout)
        if self._embedded_canvas is not canvas:
            self.detach_embedded_canvas_only()
            self._embedded_canvas = canvas
            try:
                canvas.setParent(self._map_panel)
            except Exception:
                log_exception("falha opcional ignorada")
            panel_layout.addWidget(canvas)

        self._map_panel.setVisible(True)
        try:
            canvas.show()
        except Exception:
            log_exception("falha opcional ignorada")
        return True

    def detach_embedded_map_canvas(self):
        self.detach_embedded_canvas_only()
        panel = self._map_panel
        self._map_panel = None
        self._map_toolbar = None
        if panel is None:
            return
        self._restore_content_layout(panel)
        try:
            panel.setParent(None)
            panel.deleteLater()
        except Exception:
            log_exception("falha opcional ignorada")

    def detach_embedded_canvas_only(self):
        canvas = self._embedded_canvas
        self._embedded_canvas = None
        if canvas is None:
            return
        try:
            canvas.setParent(None)
        except Exception:
            log_exception("falha opcional ignorada")

    def configure_map_toolbar(self, actions):
        toolbar = self._map_toolbar
        if toolbar is None:
            return False
        try:
            toolbar.clear()
        except Exception:
            return False
        for action in actions or []:
            try:
                toolbar.addAction(action)
            except Exception:
                log_exception("falha opcional ignorada")
                continue
        return True

    def _ensure_splitter_layout(self, central, layout, map_panel):
        splitter = self._splitter
        content = self._content_frame or self._main_content_frame()
        if content is None:
            return False

        if splitter is None:
            splitter = self._create_splitter(central)
            self._splitter = splitter
            self._content_frame = content
            self._content_insert_index = max(0, layout.indexOf(content))
            try:
                layout.removeWidget(content)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                layout.insertWidget(self._content_insert_index, splitter, 1)
            except Exception:
                layout.addWidget(splitter, 1)
            try:
                splitter.addWidget(content)
            except Exception:
                return False

        if self._splitter_index(map_panel) < 0:
            try:
                splitter.addWidget(map_panel)
            except Exception:
                return False

        self._apply_splitter_defaults(splitter)
        return True

    def _create_splitter(self, parent):
        splitter = QSplitter(Qt.Horizontal, parent)
        splitter.setObjectName("PresentationMapSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.setStyleSheet(
            """
            QSplitter#PresentationMapSplitter::handle {
                background: transparent;
                border: 0;
            }
            QSplitter#PresentationMapSplitter::handle:hover {
                background: transparent;
            }
            """
        )
        return splitter

    def _apply_splitter_defaults(self, splitter):
        if splitter is None or splitter.count() < 2:
            return
        try:
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
            if not any(splitter.sizes()):
                splitter.setSizes([1, 1])
        except Exception:
            log_exception("falha opcional ignorada")

    def _restore_content_layout(self, map_panel):
        splitter = self._splitter
        content = self._content_frame
        central = self._central_frame()
        layout = central.layout() if central is not None else None

        if splitter is not None and content is not None and layout is not None:
            index = self._content_insert_index
            if index is None or index < 0:
                index = max(0, layout.indexOf(splitter))
            try:
                content.setParent(None)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                map_panel.setParent(None)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                layout.removeWidget(splitter)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                layout.insertWidget(index, content, 1)
            except Exception:
                layout.addWidget(content, 1)
            try:
                splitter.setParent(None)
                splitter.deleteLater()
            except Exception:
                log_exception("falha opcional ignorada")
        else:
            self._remove_widget_from_parent_layout(map_panel)

        self._splitter = None
        self._content_frame = None
        self._content_insert_index = None

    def _splitter_index(self, widget):
        splitter = self._splitter
        if splitter is None or widget is None:
            return -1
        try:
            return splitter.indexOf(widget)
        except Exception:
            return -1

    def _create_map_panel(self, parent):
        panel = QFrame(parent)
        panel.setObjectName("PresentationEmbeddedMapPanel")
        panel.setMinimumWidth(420)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        panel.setStyleSheet(
            """
            QFrame#PresentationEmbeddedMapPanel {
                border-left: 1px solid rgba(15, 23, 42, 0.14);
                background: #f8fafc;
            }
            """
        )
        return panel

    def _ensure_map_toolbar(self, panel_layout):
        if self._map_toolbar is not None:
            return self._map_toolbar
        toolbar = QToolBar(self._map_panel)
        toolbar.setObjectName("PresentationEmbeddedMapToolbar")
        toolbar.setIconSize(self._toolbar_icon_size())
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(
            """
            QToolBar#PresentationEmbeddedMapToolbar {
                border: 0;
                border-bottom: 1px solid rgba(15, 23, 42, 0.12);
                background: #f8fafc;
                spacing: 2px;
                padding: 3px 5px;
            }
            """
        )
        panel_layout.addWidget(toolbar)
        self._map_toolbar = toolbar
        return toolbar

    def _toolbar_icon_size(self):
        from qgis.PyQt.QtCore import QSize

        return QSize(18, 18)

    def _remove_widget_from_parent_layout(self, widget):
        if widget is None:
            return
        try:
            parent = widget.parentWidget()
        except Exception:
            parent = None
        if parent is None:
            return
        layout = parent.layout()
        if layout is None:
            return
        try:
            layout.removeWidget(widget)
            layout.invalidate()
        except Exception:
            log_exception("falha opcional ignorada")

    def _central_frame(self):
        ui = getattr(self.plugin_window, "ui", None)
        central = getattr(ui, "central_frame", None)
        if isinstance(central, QWidget):
            return central
        return None

    def _main_content_frame(self):
        ui = getattr(self.plugin_window, "ui", None)
        content = getattr(ui, "content_frame", None)
        if isinstance(content, QWidget):
            return content
        return None

    def _capture_window_state(self, window: QWidget) -> Optional[dict]:
        if window is None:
            return None
        try:
            geometry = window.geometry()
        except Exception:
            geometry = None
        if geometry is None:
            return None
        try:
            maximized = bool(window.isMaximized())
        except Exception:
            maximized = False
        try:
            minimized = bool(window.isMinimized())
        except Exception:
            minimized = False
        return {
            "geometry": QRect(geometry),
            "maximized": maximized,
            "minimized": minimized,
        }

    def _restore_window_state(self, window: QWidget, snapshot: Optional[dict]):
        if window is None or not snapshot:
            return False

        geometry = snapshot.get("geometry")
        maximized = bool(snapshot.get("maximized"))
        minimized = bool(snapshot.get("minimized"))

        try:
            if hasattr(window, "showNormal"):
                window.showNormal()
        except Exception:
            log_exception("falha opcional ignorada")

        if geometry is not None:
            try:
                window.setGeometry(QRect(geometry))
            except Exception:
                log_exception("falha ao restaurar a geometria do Summarizer")

        try:
            if minimized and hasattr(window, "showMinimized"):
                window.showMinimized()
            elif maximized and hasattr(window, "showMaximized"):
                window.showMaximized()
        except Exception:
            log_exception("falha ao restaurar o estado do Summarizer")
            return False

        return True

    def _plugin_window(self):
        widget = self.plugin_window
        if widget is None:
            return None
        if isinstance(widget, QWidget):
            return widget
        window = getattr(widget, "window", None)
        if callable(window):
            try:
                result = window()
            except Exception:
                result = None
            if isinstance(result, QWidget):
                return result
        return None

    def _has_saved_state(self):
        return self._saved_plugin_state is not None

    def _clear_state(self):
        self._saved_plugin_state = None
