# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QAction, QMenu

try:
    from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsMapToolZoom
except Exception:  # pragma: no cover - optional in pure-python tests
    QgsMapCanvas = None
    QgsMapToolPan = None
    QgsMapToolZoom = None

from .presentation_window_manager import PresentationWindowManager
from ..utils.i18n_runtime import tr_text as _rt
from ..utils.logging_utils import log_exception
from ..walker_dialogs import apply_walker_menu


class PresentationMapController(QObject):
    """Controls the native presentation canvas and side-by-side layout."""

    stateChanged = pyqtSignal(bool)
    MAP_CANVAS_TITLE = "Summarizer - Mapa"

    def __init__(self, iface, plugin_window):
        super().__init__(plugin_window)
        self.iface = iface
        self.plugin_window = plugin_window
        self.window_manager = PresentationWindowManager(iface, plugin_window)
        self._tracked_canvas = None
        self._pan_tool = None
        self._zoom_in_tool = None
        self._zoom_out_tool = None
        self._closing_internal = False

    def open(self):
        canvas = self._ensure_presentation_canvas()
        if canvas is None:
            self._set_state(False)
            return False

        try:
            active = self.window_manager.enter_side_by_side_layout(canvas)
        except Exception:
            log_exception("falha ao organizar a visualizacao de mapa lado a lado")
            active = False

        if active:
            self._configure_embedded_toolbar(canvas)
            self.sync_with_main_canvas()
            self.refresh()

        self._set_state(bool(active))
        return bool(active)

    def close(self):
        canvas = self._presentation_canvas()
        had_canvas = canvas is not None
        had_layout = self.window_manager.is_active()

        if not had_canvas and not had_layout:
            self._set_state(False)
            return False

        self._closing_internal = True
        try:
            try:
                self.window_manager.exit_side_by_side_layout()
            except Exception:
                log_exception("falha ao restaurar a geometria do Summarizer")
            if had_canvas:
                self._close_presentation_canvas(canvas)
        finally:
            self._closing_internal = False

        self._clear_tracking()
        self._set_state(False)
        return True

    def toggle(self, checked: bool):
        if checked:
            return self.open()
        return self.close()

    def sync_with_main_canvas(self):
        canvas = self._presentation_canvas()
        if canvas is None:
            return False
        self._bind_canvas(canvas)

        main_canvas = self._main_canvas()
        if main_canvas is None:
            return False

        self._copy_canvas_state(main_canvas, canvas)
        return True

    def refresh(self):
        canvas = self._presentation_canvas()
        if canvas is None:
            return False

        self.sync_with_main_canvas()
        return self._refresh_canvas(canvas)

    def refresh_after_chart_selection(self, layer=None):
        if not self.is_active():
            return False

        canvas = self._presentation_canvas()
        if canvas is None:
            return False

        refreshed = self.refresh()
        if layer is not None:
            self._try_zoom_to_selected(canvas, layer)
        return refreshed

    def cleanup(self):
        try:
            self.close()
        finally:
            self.window_manager.cleanup()
            self._clear_tracking()
            self._set_state(False)

    def sync_presentation_map(self):
        return self.refresh()

    def is_active(self):
        try:
            return bool(self.window_manager.is_active())
        except Exception:
            return False

    def _ensure_presentation_canvas(self):
        if self._tracked_canvas is not None:
            return self._tracked_canvas
        if QgsMapCanvas is None:
            return None

        try:
            canvas = QgsMapCanvas(self.plugin_window)
        except Exception:
            log_exception("falha ao criar a visualizacao de mapa de apresentacao")
            return None

        if canvas is None:
            return None

        self._set_canvas_title(canvas, self.MAP_CANVAS_TITLE)
        self._init_canvas_tools(canvas)
        self._bind_canvas(canvas)
        return canvas

    def _init_canvas_tools(self, canvas):
        if canvas is None:
            return
        if QgsMapToolPan is not None and self._pan_tool is None:
            try:
                self._pan_tool = QgsMapToolPan(canvas)
                canvas.setMapTool(self._pan_tool)
            except Exception:
                self._pan_tool = None
        if QgsMapToolZoom is not None and self._zoom_in_tool is None:
            try:
                self._zoom_in_tool = QgsMapToolZoom(canvas, False)
            except Exception:
                self._zoom_in_tool = None
        if QgsMapToolZoom is not None and self._zoom_out_tool is None:
            try:
                self._zoom_out_tool = QgsMapToolZoom(canvas, True)
            except Exception:
                self._zoom_out_tool = None

    def _presentation_canvas(self):
        return self._tracked_canvas

    def _bind_canvas(self, canvas: Any):
        if canvas is None or self._tracked_canvas is canvas:
            return
        self._tracked_canvas = canvas
        destroyed = getattr(canvas, "destroyed", None)
        if destroyed is not None:
            try:
                destroyed.connect(self._on_canvas_destroyed)
            except Exception:
                log_exception("falha ao acompanhar fechamento do mapa de apresentacao")

    def _on_canvas_destroyed(self, *args):
        if self._closing_internal:
            self._clear_tracking()
            self._set_state(False)
            return
        self._handle_external_close()

    def _handle_external_close(self):
        try:
            self.window_manager.exit_side_by_side_layout()
        except Exception:
            log_exception("falha ao restaurar a geometria apos fechar o mapa")
        self._clear_tracking()
        self._set_state(False)

    def _close_presentation_canvas(self, canvas: Any):
        self.window_manager.detach_embedded_canvas_only()
        self._pan_tool = None
        self._zoom_in_tool = None
        self._zoom_out_tool = None
        for method_name in ("close", "deleteLater"):
            method = getattr(canvas, method_name, None)
            if not callable(method):
                continue
            try:
                method()
            except Exception:
                log_exception("falha opcional ignorada")
                continue
        return True

    def _main_canvas(self):
        getter = getattr(self.iface, "mapCanvas", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

    def _copy_canvas_state(self, source: Any, target: Any):
        if source is None or target is None:
            return
        self._copy_layers(source, target)
        self._copy_crs(source, target)
        self._copy_extent(source, target)
        self._copy_rotation(source, target)

    def _copy_layers(self, source: Any, target: Any):
        getter = getattr(source, "layers", None)
        setter = getattr(target, "setLayers", None)
        if not callable(getter) or not callable(setter):
            return
        try:
            setter(list(getter() or []))
        except Exception:
            log_exception("falha ao copiar camadas para a visualizacao de mapa de apresentacao")

    def _copy_crs(self, source: Any, target: Any):
        getter = getattr(source, "destinationCrs", None)
        crs = None
        if callable(getter):
            try:
                crs = getter()
            except Exception:
                crs = None
        if crs is None:
            map_settings_getter = getattr(source, "mapSettings", None)
            if callable(map_settings_getter):
                try:
                    map_settings = map_settings_getter()
                except Exception:
                    map_settings = None
                if map_settings is not None:
                    settings_getter = getattr(map_settings, "destinationCrs", None)
                    if callable(settings_getter):
                        try:
                            crs = settings_getter()
                        except Exception:
                            crs = None
        setter = getattr(target, "setDestinationCrs", None)
        if crs is None or not callable(setter):
            return
        try:
            setter(crs)
        except Exception:
            log_exception("falha ao copiar CRS para a visualizacao de mapa de apresentacao")

    def _copy_extent(self, source: Any, target: Any):
        getter = getattr(source, "extent", None)
        setter = getattr(target, "setExtent", None)
        if not callable(getter) or not callable(setter):
            return
        try:
            setter(getter())
        except Exception:
            log_exception("falha ao copiar extensao para a visualizacao de mapa de apresentacao")

    def _copy_rotation(self, source: Any, target: Any):
        getter = getattr(source, "rotation", None)
        setter = getattr(target, "setRotation", None)
        if not callable(getter) or not callable(setter):
            return
        try:
            setter(float(getter() or 0.0))
        except Exception:
            log_exception("falha ao copiar rotacao para a visualizacao de mapa de apresentacao")

    def _refresh_canvas(self, canvas: Any):
        if canvas is None:
            return False
        refresher = getattr(canvas, "refresh", None)
        if not callable(refresher):
            return False
        try:
            refresher()
            return True
        except Exception:
            log_exception("falha ao atualizar a visualizacao de mapa de apresentacao")
            return False

    def _try_zoom_to_selected(self, canvas: Any, layer: Any):
        if canvas is None or layer is None:
            return
        zoom = getattr(canvas, "zoomToSelected", None)
        if not callable(zoom):
            return
        try:
            zoom(layer)
        except Exception:
            log_exception("falha ao aplicar zoom na selecao do mapa de apresentacao")

    def _raise_canvas(self, canvas: Any):
        if canvas is None:
            return
        for method_name in ("show", "raise_", "activateWindow"):
            method = getattr(canvas, method_name, None)
            if not callable(method):
                continue
            try:
                method()
            except Exception:
                log_exception("falha opcional ignorada")
                continue

    def _configure_embedded_toolbar(self, canvas):
        actions = [
            self._make_action("/mActionPan.svg", "Mover mapa", lambda: self._set_map_tool(self._pan_tool)),
            self._make_action("/mActionZoomIn.svg", "Aproximar", lambda: self._set_map_tool(self._zoom_in_tool)),
            self._make_action("/mActionZoomOut.svg", "Afastar", lambda: self._set_map_tool(self._zoom_out_tool)),
            self._make_action("/mActionZoomFullExtent.svg", "Extensao total", self._zoom_full_extent),
            self._make_action("/mActionZoomToSelected.svg", "Zoom na selecao", self._zoom_to_current_selection),
            self._make_action("/mActionRefresh.svg", "Atualizar mapa", self.refresh),
            self._make_action("/mActionMapSettings.svg", "Configuracoes", self._show_map_options_menu),
        ]
        try:
            self.window_manager.configure_map_toolbar(actions)
        except Exception:
            log_exception("falha ao configurar toolbar do mapa de apresentacao")

    def _make_action(self, icon_name: str, text: str, callback):
        action = QAction(self._theme_icon(icon_name), text, self.plugin_window)
        action.setToolTip(text)
        try:
            action.triggered.connect(callback)
        except Exception:
            log_exception("falha opcional ignorada")
        return action

    def _theme_icon(self, icon_name: str):
        try:
            return QgsApplication.getThemeIcon(icon_name)
        except Exception:
            return None

    def _set_map_tool(self, tool):
        canvas = self._presentation_canvas()
        if canvas is None or tool is None:
            return
        try:
            canvas.setMapTool(tool)
        except Exception:
            log_exception("falha ao ativar ferramenta do mapa de apresentacao")

    def _zoom_full_extent(self):
        canvas = self._presentation_canvas()
        if canvas is None:
            return
        for method_name in ("zoomToFullExtent", "zoomFullExtent"):
            method = getattr(canvas, method_name, None)
            if callable(method):
                try:
                    method()
                    canvas.refresh()
                    return
                except Exception:
                    log_exception("falha opcional ignorada")
                    continue

    def _zoom_to_current_selection(self):
        canvas = self._presentation_canvas()
        if canvas is None:
            return
        for layer in self._selected_layers():
            self._try_zoom_to_selected(canvas, layer)
            return

    def _selected_layers(self):
        main_canvas = self._main_canvas()
        layers = []
        getter = getattr(main_canvas, "layers", None)
        if callable(getter):
            try:
                layers = list(getter() or [])
            except Exception:
                layers = []
        for layer in layers:
            selected_count = getattr(layer, "selectedFeatureCount", None)
            if callable(selected_count):
                try:
                    if selected_count() > 0:
                        yield layer
                except Exception:
                    log_exception("falha opcional ignorada")
                    continue

    def _show_map_options_menu(self):
        canvas = self._presentation_canvas()
        if canvas is None:
            return
        menu = apply_walker_menu(QMenu(self.plugin_window))
        menu.addAction(_rt("Sincronizar com mapa principal"), self.sync_with_main_canvas)
        menu.addAction(_rt("Atualizar"), self.refresh)
        menu.addAction(_rt("Extensão total"), self._zoom_full_extent)
        menu.addAction(_rt("Zoom na seleção"), self._zoom_to_current_selection)
        try:
            menu.exec_(self.plugin_window.cursor().pos())
        except Exception:
            log_exception("falha opcional ignorada")

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
                    log_exception("falha opcional ignorada")
                    continue
                text = str(value or "").strip()
                if text:
                    return text
        return ""

    def _set_canvas_title(self, canvas: Any, title: str):
        if canvas is None:
            return
        for attr in ("setWindowTitle", "setTitle", "setObjectName"):
            setter = getattr(canvas, attr, None)
            if callable(setter):
                try:
                    setter(str(title or ""))
                except Exception:
                    log_exception("falha opcional ignorada")
                    continue

    def _clear_tracking(self):
        self._tracked_canvas = None

    def _set_state(self, active: bool):
        try:
            self.stateChanged.emit(bool(active))
        except Exception:
            log_exception("falha ao notificar estado do modo apresentacao")
