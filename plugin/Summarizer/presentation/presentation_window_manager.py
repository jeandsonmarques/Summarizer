from __future__ import annotations

from typing import Any, Optional

from qgis.PyQt.QtCore import QObject, QRect, Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    from qgis.gui import QgsMapCanvas
except Exception:  # pragma: no cover - optional in pure-python tests
    QgsMapCanvas = None

from ..utils.logging_utils import log_exception, log_info, log_warning


class PresentationWindowManager(QObject):
    """Handles geometry for the Summarizer and the presentation map view."""

    MAP_CANVAS_TITLE = "Summarizer - Mapa"

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

    def find_parent_dock(self, widget):
        return self._dock_from_parent_chain(widget)

    def find_map_view_dock(self, canvas=None):
        dock = self._dock_from_parent_chain(canvas)
        if dock is not None:
            log_info("Presentation: dock Summarizer - Mapa encontrado por parent")
            return dock

        main_window = self._main_window()
        docks = []
        if main_window is not None:
            try:
                docks = list(main_window.findChildren(QDockWidget) or [])
            except Exception:
                docks = []

        dock = self._dock_from_title(docks, exact=True)
        if dock is not None:
            log_info("Presentation: dock Summarizer - Mapa encontrado por title")
            return dock

        dock = self._dock_from_title(docks, exact=False)
        if dock is not None:
            log_info("Presentation: dock Summarizer - Mapa encontrado por partial title")
            return dock

        dock = self._dock_from_descendants(docks, canvas)
        if dock is not None:
            log_info("Presentation: dock Summarizer - Mapa encontrado por content")
            return dock

        log_warning("Presentation: nao encontrou dock Summarizer - Mapa nesta tentativa")
        return None

    def _dock_from_parent_chain(self, widget):
        current = widget
        visited = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, QDockWidget):
                return current
            try:
                parent_widget = current.parentWidget()
            except Exception:
                parent_widget = None
            if parent_widget is not None:
                current = parent_widget
                continue
            try:
                current = current.parent()
            except Exception:
                current = None
        return None

    def _dock_from_title(self, docks, *, exact: bool):
        if not docks:
            return None
        for dock in docks:
            if not isinstance(dock, QDockWidget):
                continue
            title = self._dock_title(dock)
            if exact and title == self.MAP_CANVAS_TITLE:
                return dock
            if not exact and self.MAP_CANVAS_TITLE in title:
                return dock
        return None

    def _dock_from_descendants(self, docks, canvas):
        if not docks:
            return None
        for dock in docks:
            if not isinstance(dock, QDockWidget):
                continue
            if self._dock_contains_canvas(dock, canvas):
                return dock
        return None

    def _dock_contains_canvas(self, dock, canvas):
        if dock is None:
            return False
        descendants = self._dock_descendants(dock)
        if canvas is not None:
            for child in descendants:
                if child is canvas:
                    return True
        for child in descendants:
            if self._widget_matches_canvas(child):
                return True
        return False

    def _dock_descendants(self, dock):
        if dock is None:
            return []
        try:
            return list(dock.findChildren(QWidget))
        except Exception:
            return []

    def _widget_matches_canvas(self, widget):
        if widget is None:
            return False
        if QgsMapCanvas is not None and isinstance(widget, QgsMapCanvas):
            return self._canvas_matches_title(widget)
        title = self._widget_title(widget)
        object_name = self._widget_object_name(widget)
        if title == self.MAP_CANVAS_TITLE or object_name == self.MAP_CANVAS_TITLE:
            return True
        return self.MAP_CANVAS_TITLE in title or self.MAP_CANVAS_TITLE in object_name

    def _dock_title(self, dock):
        return self._widget_title(dock)

    def _widget_title(self, widget):
        if widget is None:
            return ""
        for attr in ("windowTitle", "title"):
            getter = getattr(widget, attr, None)
            if callable(getter):
                try:
                    value = getter()
                except Exception:
                    continue
                text = str(value or "").strip()
                if text:
                    return text
        return ""

    def _widget_object_name(self, widget):
        if widget is None:
            return ""
        getter = getattr(widget, "objectName", None)
        if callable(getter):
            try:
                return str(getter() or "").strip()
            except Exception:
                return ""
        return ""

    def position_plugin_left(self, *, raise_window: bool = True):
        plugin_window = self._plugin_window()
        available = self._available_geometry(plugin_window)
        if plugin_window is None or available is None:
            return False

        left_rect, _ = self._split_geometry(available)
        try:
            self._detach_plugin_window(plugin_window)
            self._show_normal(plugin_window)
            self._apply_geometry(plugin_window, left_rect)
            try:
                plugin_window.resize(left_rect.size())
            except Exception:
                pass
            try:
                plugin_window.move(left_rect.topLeft())
            except Exception:
                pass
            self._apply_window_handle_geometry(plugin_window, left_rect)
            if raise_window:
                self._raise_widget(plugin_window)
            try:
                plugin_window.setGeometry(QRect(left_rect))
            except Exception:
                pass
            return True
        except Exception:
            log_exception("falha ao posicionar o Summarizer a esquerda")
            return False

    def position_map_view_right(self, canvas, dock=None):
        dock = dock or self.find_map_view_dock(canvas)
        if dock is None:
            log_warning("Presentation: nao encontrou dock Summarizer - Mapa nesta tentativa")
            return False

        available = (
            self._available_geometry(self._plugin_window())
            or self._available_geometry(self._main_window())
            or self._available_geometry(dock)
        )
        if available is None:
            return False

        _, target_rect = self._split_geometry(available)
        try:
            self._force_map_dock_floating(dock, target_rect)
            return True
        except Exception:
            log_exception("falha ao posicionar a visualizacao de mapa a direita")
            return False

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
                pass
            panel_layout.addWidget(canvas)

        self._map_panel.setVisible(True)
        try:
            canvas.show()
        except Exception:
            pass
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
            pass

    def detach_embedded_canvas_only(self):
        canvas = self._embedded_canvas
        self._embedded_canvas = None
        if canvas is None:
            return
        try:
            canvas.setParent(None)
        except Exception:
            pass

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
                pass
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
            pass

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
                pass
            try:
                map_panel.setParent(None)
            except Exception:
                pass
            try:
                layout.removeWidget(splitter)
            except Exception:
                pass
            try:
                layout.insertWidget(index, content, 1)
            except Exception:
                layout.addWidget(content, 1)
            try:
                splitter.setParent(None)
                splitter.deleteLater()
            except Exception:
                pass
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
                continue
        return True

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
            pass

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
        try:
            parent = window.parentWidget()
        except Exception:
            parent = None
        try:
            flags = window.windowFlags()
        except Exception:
            flags = None
        return {
            "geometry": QRect(geometry),
            "maximized": maximized,
            "minimized": minimized,
            "parent": parent,
            "flags": flags,
        }

    def _restore_window_state(self, window: QWidget, snapshot: Optional[dict]):
        if window is None or not snapshot:
            return False

        geometry = snapshot.get("geometry")
        maximized = bool(snapshot.get("maximized"))
        minimized = bool(snapshot.get("minimized"))
        parent = snapshot.get("parent")
        flags = snapshot.get("flags")

        self._restore_plugin_parent(window, parent, flags)

        try:
            if hasattr(window, "showNormal"):
                window.showNormal()
        except Exception:
            pass

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

    def _available_geometry(self, window: QWidget) -> Optional[QRect]:
        screen = self._screen_for_widget(window)
        if screen is not None:
            try:
                geometry = screen.availableGeometry()
            except Exception:
                geometry = None
            if geometry is not None and not geometry.isNull():
                return QRect(geometry)

        try:
            primary = QApplication.primaryScreen()
        except Exception:
            primary = None
        if primary is not None:
            try:
                geometry = primary.availableGeometry()
            except Exception:
                geometry = None
            if geometry is not None and not geometry.isNull():
                return QRect(geometry)
        return None

    def _screen_for_widget(self, widget: QWidget):
        if widget is None:
            return None
        try:
            handle = widget.windowHandle()
        except Exception:
            handle = None
        if handle is None:
            return None
        try:
            return handle.screen()
        except Exception:
            return None

    def _split_geometry(self, available: QRect):
        left_width = max(480, int(round(available.width() * 0.5)))
        right_width = max(480, available.width() - left_width)
        left_rect = QRect(available.x(), available.y(), left_width, available.height())
        right_rect = QRect(available.x() + left_width, available.y(), right_width, available.height())
        return left_rect, right_rect

    def _show_normal(self, window: QWidget):
        if window is None:
            return
        for method_name in ("showNormal", "show"):
            method = getattr(window, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    continue

    def _apply_geometry(self, window: QWidget, geometry: QRect):
        if window is None or geometry is None:
            return
        try:
            window.setGeometry(QRect(geometry))
        except Exception:
            log_exception("falha ao ajustar a geometria da janela")

    def _apply_window_handle_geometry(self, window: QWidget, geometry: QRect):
        if window is None or geometry is None:
            return
        try:
            handle = window.windowHandle()
        except Exception:
            handle = None
        if handle is None:
            return
        try:
            handle.setGeometry(QRect(geometry))
        except Exception:
            pass

    def _detach_plugin_window(self, window: QWidget):
        if window is None:
            return
        try:
            parent = window.parentWidget()
        except Exception:
            parent = None
        if parent is None:
            return
        try:
            flags = window.windowFlags()
            window.setParent(
                None,
                flags
                | Qt.Window
                | Qt.WindowTitleHint
                | Qt.WindowSystemMenuHint
                | Qt.WindowMinimizeButtonHint
                | Qt.WindowMaximizeButtonHint
                | Qt.WindowCloseButtonHint,
            )
            window.show()
            log_info("Presentation: Summarizer destacado da janela principal do QGIS")
        except Exception:
            log_warning("Presentation: falha ao destacar o Summarizer da janela principal do QGIS")

    def _restore_plugin_parent(self, window: QWidget, parent, flags):
        if window is None:
            return
        if parent is None and flags is None:
            return
        try:
            if parent is not None and window.parentWidget() is not parent:
                if flags is None:
                    window.setParent(parent)
                else:
                    window.setParent(parent, flags)
                window.show()
                return
        except Exception:
            log_warning("Presentation: falha ao restaurar parent do Summarizer")
        if flags is not None:
            try:
                window.setWindowFlags(flags)
                window.show()
            except Exception:
                pass

    def _raise_widget(self, window: QWidget):
        if window is None:
            return
        for method_name in ("raise_", "activateWindow"):
            method = getattr(window, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    continue

    def _force_map_dock_floating(self, dock: QDockWidget, right_rect: QRect):
        if dock is None:
            return False

        self._ensure_dock_features(dock)
        self._restrict_map_dock_to_float(dock)

        try:
            dock.setFloating(True)
            log_info("Presentation: setFloating aplicado em Summarizer - Mapa")
        except Exception:
            log_warning("Presentation: falha ao aplicar setFloating em Summarizer - Mapa")

        try:
            user_visible = getattr(dock, "setUserVisible", None)
            if callable(user_visible):
                user_visible(True)
        except Exception:
            pass
        try:
            dock.show()
        except Exception:
            pass
        try:
            dock.setFloating(True)
        except Exception:
            pass
        geometry_target = self._floating_geometry_target(dock) or dock
        try:
            dock.raise_()
        except Exception:
            pass
        try:
            geometry_target.setGeometry(QRect(right_rect))
        except Exception:
            log_exception("falha ao aplicar geometria no dock de mapa")
        try:
            geometry_target.resize(right_rect.size())
        except Exception:
            pass
        try:
            geometry_target.move(right_rect.topLeft())
        except Exception:
            pass
        try:
            activate = getattr(geometry_target, "activateWindow", None)
            if callable(activate):
                activate()
        except Exception:
            pass
        try:
            geometry_target.setGeometry(QRect(right_rect))
        except Exception:
            pass
        try:
            dock.setFloating(True)
        except Exception:
            pass
        return True

    def _floating_geometry_target(self, dock: QDockWidget):
        if dock is None:
            return None
        try:
            if bool(dock.isFloating()):
                return dock
        except Exception:
            pass
        window_getter = getattr(dock, "window", None)
        if not callable(window_getter):
            return None
        try:
            candidate = window_getter()
        except Exception:
            return None
        if not isinstance(candidate, QWidget):
            return None
        if candidate is self._main_window() or candidate is self._plugin_window():
            return None
        title = self._widget_title(candidate)
        if title and self.MAP_CANVAS_TITLE not in title:
            return None
        return candidate

    def _restrict_map_dock_to_float(self, dock: QDockWidget):
        if dock is None:
            return
        setter = getattr(dock, "setAllowedAreas", None)
        if not callable(setter):
            return
        try:
            current = getattr(dock, "allowedAreas", None)
            if callable(current):
                try:
                    previous = current()
                    if dock.property("_summarizer_previous_allowed_areas") is None:
                        dock.setProperty("_summarizer_previous_allowed_areas", previous)
                except Exception:
                    pass
            setter(Qt.NoDockWidgetArea)
            log_info("Presentation: allowedAreas restringido para NoDockWidgetArea")
        except Exception:
            log_warning("Presentation: falha ao restringir allowedAreas do dock de mapa")

    def restore_map_dock_areas(self, dock: QDockWidget):
        if dock is None:
            return
        previous = None
        try:
            previous = dock.property("_summarizer_previous_allowed_areas")
        except Exception:
            previous = None
        setter = getattr(dock, "setAllowedAreas", None)
        if not callable(setter):
            return
        try:
            if previous is None:
                setter(Qt.AllDockWidgetAreas)
            else:
                setter(previous)
        except Exception:
            pass
        try:
            dock.setProperty("_summarizer_previous_allowed_areas", None)
        except Exception:
            pass

    def _ensure_dock_features(self, dock: QDockWidget):
        if dock is None:
            return
        features = None
        getter = getattr(dock, "features", None)
        if callable(getter):
            try:
                features = getter()
            except Exception:
                features = None
        if features is None:
            return
        try:
            dock.setFeatures(
                features
                | QDockWidget.DockWidgetClosable
                | QDockWidget.DockWidgetMovable
                | QDockWidget.DockWidgetFloatable
            )
            log_info("Presentation: features de fechamento/flutuação reforcadas no dock")
        except Exception:
            log_warning("Presentation: falha ao reforcar features do dock de mapa")

    def _presentation_target(self, canvas):
        if canvas is None:
            return None
        dock = self.find_map_view_dock(canvas)
        if dock is not None:
            return dock
        if isinstance(canvas, QWidget):
            return canvas
        window = getattr(canvas, "window", None)
        if callable(window):
            try:
                result = window()
            except Exception:
                result = None
            if isinstance(result, QWidget):
                return result
        return None

    def _main_window(self):
        getter = getattr(self.iface, "mainWindow", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

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

    def _canvas_matches_title(self, canvas: Any) -> bool:
        if canvas is None:
            return False
        title = self._canvas_title(canvas)
        if title == self.MAP_CANVAS_TITLE:
            return True
        object_name = str(getattr(canvas, "objectName", lambda: "")() or "").strip()
        return object_name == self.MAP_CANVAS_TITLE

    def _canvas_title(self, canvas: Any) -> str:
        if canvas is None:
            return ""
        for attr in ("windowTitle", "title"):
            getter = getattr(canvas, attr, None)
            if callable(getter):
                try:
                    value = getter()
                except Exception:
                    continue
                text = str(value or "").strip()
                if text:
                    return text
        return ""

    def _has_saved_state(self):
        return self._saved_plugin_state is not None

    def _clear_state(self):
        self._saved_plugin_state = None
