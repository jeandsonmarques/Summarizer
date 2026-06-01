# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
import re
import tempfile
import uuid
from datetime import datetime
from string import Template
from typing import Dict, List, Optional

import pandas as pd
from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsMapLayerStyle,
    QgsMessageLog,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QSettings,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
    QVariant,
)
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
try:  # pragma: no cover - QtSql availability depends on the QGIS install
    from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery
except Exception:  # pragma: no cover
    QSqlDatabase = None
    QSqlQuery = None

from .browser_integration import (
    connection_registry,
    register_browser_provider,
    unregister_browser_provider,
)
from .export_manager import ExportManager
from .interactive_table import InteractiveTable
from .layout_nav import SidebarController
from .palette import palette_context
from .pivot_table_widget import PivotTableWidget
from .presentation import PresentationMapController, create_presentation_button
from .slim_dialogs import SlimDialogBase, SlimLayerSelectionDialog
from .summary_view.summary_calculations import (
    build_dataframe_summary as _summary_build_dataframe_summary,
)
from .summary_view.summary_calculations import (
    calculate_advanced_summary as _summary_calculate_advanced_summary,
)
from .summary_view.summary_calculations import (
    filter_empty_matches as _summary_filter_empty_matches,
)
from .summary_view.summary_calculations import (
    is_meaningful_value as _summary_is_meaningful_value,
)
from .summary_view.summary_chart_preview import (
    chart_preview_style_block as _summary_chart_preview_style_block,
)
from .summary_view.summary_chart_preview import (
    update_charts_preview as _summary_update_charts_preview,
)
from .summary_view.summary_export_controller import SummaryExportController
from .summary_view.summary_layer_io import (
    build_geometry_lookup as _summary_build_geometry_lookup,
)
from .summary_view.summary_layer_io import (
    create_layer_from_dataframe as _summary_create_layer_from_dataframe,
)
from .summary_view.summary_layer_io import (
    create_memory_table_from_dataframe as _summary_create_memory_table_from_dataframe,
)
from .walker_dialogs import (
    WALKER_DIALOG_STYLE,
    WalkerMessageBox as QMessageBox,
    add_walker_close_button,
    apply_walker_buttons,
    apply_walker_menu,
    install_walker_modal_chrome,
)
from .summary_view.summary_layer_io import (
    export_layer_to_gpkg as _summary_export_layer_to_gpkg,
)
from .summary_view.summary_layer_io import (
    format_comparison_values as _summary_format_comparison_values,
)
from .summary_view.summary_layer_io import (
    geometry_from_lookup as _summary_geometry_from_lookup,
)
from .summary_view.summary_layer_io import (
    make_unique_field_name as _summary_make_unique_field_name,
)
from .summary_view.summary_layer_io import (
    map_series_to_variant as _summary_map_series_to_variant,
)
from .summary_view.summary_layer_io import (
    python_value as _summary_python_value,
)
from .summary_view.summary_layer_io import (
    sanitize_field_name as _summary_sanitize_field_name,
)
from .summary_view.summary_layer_io import (
    unique_layer_name as _summary_unique_layer_name,
)
from .summary_view.summary_layer_io import (
    variant_type_for_series as _summary_variant_type_for_series,
)
from .summary_view.summary_materialize_dialog import (
    materialize_dataframe_dialog as _summary_materialize_dataframe_dialog,
)
from .summary_view.summary_results_view import (
    build_summary_unavailable_html as _summary_build_unavailable_html,
)
from .summary_view.summary_results_view import (
    build_summary_welcome_html as _summary_build_welcome_html,
)
from .summary_view.summary_results_view import (
    display_advanced_summary as _summary_display_advanced_summary,
)
from .summary_view.summary_results_view import (
    escape_html as _summary_escape_html,
)
from .summary_view.summary_results_view import (
    set_results_view as _summary_set_results_view,
)
from .summary_view.summary_results_view import (
    show_results_message as _summary_show_results_message,
)
from .summary_view.summary_results_view import (
    show_summary_welcome as _summary_show_summary_welcome,
)
from .ui_main_dialog import Ui_SummarizerDialog
from .utils.fonts import attach_ui_font_enforcer, ensure_ui_fonts_registered, harmonize_widget_fonts
from .utils.i18n_runtime import apply_widget_translations as _apply_i18n_widgets
from .utils.i18n_runtime import tr_text as _rt_runtime
from .utils.logging_utils import log_exception
from .utils.plugin_logging import log_error
from .utils.resources import svg_icon
from .utils.window_theme import apply_windows_title_bar_theme

PROTECTED_COLUMNS_DEFAULT = {"__feature_id", "__geometry_wkb", "__target_feature_id"}


def __apply_theme_once(target):
    """Tenta aplicar o stylesheet do plugin uma única vez."""
    try:
        ensure_ui_fonts_registered()
        base_dir = os.path.dirname(__file__)
        qss_path = os.path.join(base_dir, "resources", "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as handler:
                qss = handler.read()
            try:
                qss = Template(qss).safe_substitute(palette_context())
            except Exception:
                log_exception("falha opcional ignorada")
            if hasattr(target, "iface") and hasattr(target.iface, "mainWindow"):
                target.iface.mainWindow().setStyleSheet(qss)
            elif hasattr(target, "setStyleSheet"):
                target.setStyleSheet(qss)
    except Exception:
        log_exception("falha opcional ignorada")


class Summarizer:
    def __init__(self, iface):
        try:
            __apply_theme_once(self)
        except Exception:
            log_exception("falha opcional ignorada")

        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.translator = None
        self._active_locale = ""
        self._apply_translator()

        self.actions = []
        self.menu = self.tr("Summarizer")
        self.dlg = None
        self._browser_provider = None
        self._database_explorer_activation_error = ""

    def tr(self, message):
        return QCoreApplication.translate("Summarizer", message)

    def _translation_dir(self) -> str:
        return os.path.join(self.plugin_dir, "i18n")

    def _available_translation_locales(self) -> Dict[str, str]:
        directory = self._translation_dir()
        locales: Dict[str, str] = {}
        try:
            if not os.path.isdir(directory):
                return locales
            for filename in os.listdir(directory):
                if not filename.startswith("Summarizer_") or not filename.endswith(".qm"):
                    continue
                locale = filename[len("Summarizer_") : -3].strip()
                if not locale:
                    continue
                locales[locale] = os.path.join(directory, filename)
        except Exception:
            return {}
        return locales

    def _preferred_locale(self) -> str:
        settings = QSettings()
        forced_locale = str(settings.value("Summarizer/uiLocale", "") or "").strip()
        if forced_locale and forced_locale.lower() != "auto":
            short = forced_locale.split("_", 1)[0].split("-", 1)[0].lower()
            return forced_locale if short in {"pt", "en", "es"} else "en"
        user_locale = str(settings.value("locale/userLocale", "") or "").strip()
        short = user_locale.split("_", 1)[0].split("-", 1)[0].lower() if user_locale else ""
        if short in {"pt", "en", "es"}:
            return user_locale or short
        return "en"

    def _resolve_translation_path(self, locale_code: str, available: Dict[str, str]) -> str:
        if not locale_code:
            return ""
        exact = available.get(locale_code)
        if exact:
            return exact
        lowered = locale_code.lower()
        for key, path in available.items():
            if key.lower() == lowered:
                return path
        short = locale_code.split("_", 1)[0].lower()
        for key, path in available.items():
            key_lower = key.lower()
            if key_lower == short or key_lower.startswith(f"{short}_"):
                return path
        return ""

    def _apply_translator(self):
        try:
            if self.translator is not None:
                QCoreApplication.removeTranslator(self.translator)
        except Exception:
            log_exception("falha opcional ignorada")
        self.translator = None
        self._active_locale = ""

        available = self._available_translation_locales()
        if not available:
            return

        preferred = self._preferred_locale()
        candidates = [preferred]
        if "_" in preferred:
            candidates.append(preferred.split("_", 1)[0])
        for candidate in candidates:
            path = self._resolve_translation_path(candidate, available)
            if not path:
                continue
            translator = QTranslator()
            try:
                loaded = translator.load(path)
            except Exception:
                loaded = False
            if loaded:
                QCoreApplication.installTranslator(translator)
                self.translator = translator
                locale_name = os.path.basename(path)[len("Summarizer_") : -3]
                self._active_locale = locale_name
                break

    def reload_dialog_for_language(self):
        try:
            if self.dlg is not None:
                self.dlg.close()
                self.dlg.deleteLater()
        except Exception:
            log_exception("falha opcional ignorada")
        self.dlg = None
        QTimer.singleShot(0, self.run)

    def _ensure_dialog(self):
        self._apply_translator()
        if self.dlg is not None:
            dialog_locale = str(getattr(self.dlg, "_active_locale", "") or "")
            has_translator = bool(self.translator is not None)
            dialog_has_translator = bool(getattr(self.dlg, "_has_translation", False))
            if dialog_locale == self._active_locale and dialog_has_translator == has_translator:
                return
            try:
                self.dlg.close()
                self.dlg.deleteLater()
            except Exception:
                log_exception("falha opcional ignorada")
            self.dlg = None
        if self.dlg is None:
            self.dlg = SummarizerDialog(
                self.iface,
                plugin_host=self,
                active_locale=self._active_locale,
                has_translation=bool(self.translator is not None),
            )

    def initGui(self):
        plugin_icon = svg_icon("PowerPages.svg")
        self.action = QAction(
            plugin_icon,
            self.tr("Summarizer"),
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.action.setWhatsThis(
            self.tr("Resume dados de diferentes camadas")
        )

        self.actions.append(self.action)
        self.iface.addPluginToMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)

        # Add Integration menu action (standalone page)
        self.integration_action = QAction(
            plugin_icon,
            self.tr("Conexão"),
            self.iface.mainWindow(),
        )
        self.integration_action.triggered.connect(self.open_integration_dialog)
        self.actions.append(self.integration_action)
        self.iface.addPluginToMenu(self.menu, self.integration_action)

        try:
            if self._browser_provider is None:
                self._browser_provider = register_browser_provider()
        except Exception as exc:
            self._browser_provider = None
            message = f"Falha ao registrar nó Summarizer no Navegador: {exc}"
            QgsMessageLog.logMessage(message, "Summarizer", Qgis.Critical)
            log_error(message)

    def unload(self):
        try:
            if self.dlg is not None:
                self.dlg.close()
                self.dlg.deleteLater()
        except Exception:
            log_exception("falha opcional ignorada")
        self.dlg = None
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self._browser_provider is not None:
            try:
                unregister_browser_provider(self._browser_provider)
            finally:
                self._browser_provider = None
        try:
            if hasattr(self, "presentation_controller") and self.presentation_controller:
                self.presentation_controller.cleanup()
        except Exception:
            log_exception("falha opcional ignorada")

    def run(self):
        try:
            __apply_theme_once(self)
        except Exception:
            log_exception("falha opcional ignorada")

        self._ensure_dialog()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def open_integration_dialog(self):
        # Open as a full page inside the main plugin dialog, similar to 'Sobre'
        try:
            self._ensure_dialog()
            self.dlg.show()
            self.dlg.raise_()
            self.dlg.activateWindow()
            if hasattr(self.dlg, "sidebar") and self.dlg.sidebar:
                try:
                    self.dlg.sidebar.show_integration_page()
                except Exception:
                    log_exception("falha opcional ignorada")
        except Exception as exc:
            QMessageBox.critical(self.iface.mainWindow(), "Conexão", f"Falha ao abrir: {exc}")

    # Exposed to SidebarController to open the in-dialog full page
    def open_external_integration_dialog(self):
        try:
            self._ensure_dialog()
            self.dlg.show()
            self.dlg.raise_()
            self.dlg.activateWindow()
            if hasattr(self.dlg, "sidebar") and self.dlg.sidebar:
                self.dlg.sidebar.show_integration_page()
        except Exception as exc:
            QMessageBox.critical(self, "Conexão", f"Falha ao abrir: {exc}")

    def _get_layer_by_name(self, layer_name: str):
        """Retorna a primeira camada cujo nome corresponde exatamente ao informado."""
        if not layer_name:
            return None

        matches = QgsProject.instance().mapLayersByName(layer_name)
        return matches[0] if matches else None


class SummarizerDialog(QDialog):
    def __init__(
        self,
        iface,
        plugin_host=None,
        active_locale: str = "",
        has_translation: bool = False,
    ):
        super().__init__(iface.mainWindow())
        self._enable_native_window_controls()
        self.iface = iface
        self._plugin_host = plugin_host
        self._active_locale = str(active_locale or "")
        self._has_translation = bool(has_translation)
        self._language_settings_key = "Summarizer/uiLocale"
        self._theme_settings_key = "Summarizer/uiTheme"
        self.ui = Ui_SummarizerDialog()
        self.ui.setupUi(self)
        self._square_scopes = []
        for attr in ("pageResultados",):
            scope = getattr(self.ui, attr, None)
            if scope is not None:
                scope.setProperty("squareScope", True)
                self._square_scopes.append(scope)
        self._square_theme_applied = False
        self.presentation_controller = None
        self.presentation_map_controller = None
        self.presentation_map_btn = None
        try:
            self.presentation_controller = PresentationMapController(self.iface, self)
            self.presentation_map_controller = self.presentation_controller
        except Exception:
            self.presentation_controller = None
            self.presentation_map_controller = None
            log_exception("falha opcional ignorada")
        try:
            minimize_btn = getattr(self.ui, "minimize_btn", None)
            if minimize_btn is not None:
                minimize_btn.clicked.connect(self.showMinimized)
            maximize_btn = getattr(self.ui, "maximize_btn", None)
            if maximize_btn is not None:
                maximize_btn.setVisible(False)
        except Exception:
            log_exception("falha opcional ignorada")
        self._init_language_button()
        self._init_theme_button()
        self._init_presentation_button()

        # External integration state (not used in main dialog anymore)
        self.external_df = None
        self.external_last_path_key = "Summarizer/external/lastPath"

        self.setWindowIcon(svg_icon("PowerPages.svg"))

        context = palette_context()
        base_font = QFont(context.get("font_family", "Inter"))
        base_font.setPixelSize(int(context.get("font_body_px", 13)))
        base_font.setWeight(QFont.Normal)
        self.setFont(base_font)
        self._font_enforcer = attach_ui_font_enforcer(self)

        self.export_manager = ExportManager()
        self.dashboard_widget = None
        self.model_manager = None
        self._model_backend_host = None
        self._model_scene = None
        self._model_view = None
        self.model_tab = None
        self.integration_panel = None
        self.integration_scroll = None
        self.database_explorer_panel = None
        self._database_explorer_connection_meta = {}
        self._database_explorer_layer_objects = {}
        self._defer_page_build = True
        self._deferred_page_build_queue = []
        # Inject QuickOSM-like sidebar navigation without altering the ui file
        try:
            self.sidebar = SidebarController(self)
        except Exception:
            self.sidebar = None
        try:
            connection_registry.connectionsChanged.connect(self._refresh_database_sidebar_state)
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            QgsProject.instance().layersRemoved.connect(self._handle_database_layers_removed)
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            self._set_ribbon_visible(False)
        except Exception:
            log_exception("falha opcional ignorada")

        self.export_formats = {
            "Excel (.xlsx)": {"filter": "Excel (*.xlsx)", "extension": ".xlsx"},
            "CSV (.csv)": {"filter": "CSV (*.csv)", "extension": ".csv"},
            "PDF (.pdf)": {"filter": "PDF (*.pdf)", "extension": ".pdf"},
            "JSON (.json)": {"filter": "JSON (*.json)", "extension": ".json"},
        }
        self._timestamp_pattern = re.compile(r"_\d{8}_\d{6}$")
        self._updating_export_path = False
        self._export_base_path = ""

        self.current_summary_data = None
        self.integration_datasets: Dict[str, pd.DataFrame] = {}
        self._active_numeric_field = None

        self.ui.export_format_combo.addItems(self.export_formats.keys())
        self.ui.export_format_combo.setCurrentIndex(0)

        self._apply_card_markers()

        # Prepare widgets for the Results view
        try:
            layout = self.ui.results_body_layout
            self.pivot_widget = PivotTableWidget(
                iface=self.iface,
                parent=self.ui.results_body,
                host=self,
            )
            self.pivot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(self.pivot_widget)
            try:
                self.pivot_widget.set_layer_combo(self.ui.layer_combo)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                self.pivot_widget.set_auto_update_checkbox(self.ui.auto_update_check)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                self.pivot_widget.add_dashboard_button(self.ui.dashboard_btn)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                self.ui.results_header_frame.setVisible(False)
            except Exception:
                log_exception("falha opcional ignorada")

            self.summary_message_widget = QTextEdit(self.ui.results_body)
            self.summary_message_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.summary_message_widget.setReadOnly(True)
            self.summary_message_widget.setStyleSheet(
                Template(
                    "font-family: ${font_ui_stack}; font-size: ${font_body_px}px;"
                ).safe_substitute(context)
            )
            self.summary_message_widget.setVisible(False)
            layout.addWidget(self.summary_message_widget)

            self.table_view = InteractiveTable(self.ui.results_body)
            self.table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(self.table_view)
            self.table_view.setVisible(False)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Falha ao construir a aba de tabela dinamica: {exc}",
                "Summarizer",
                Qgis.Critical,
            )
            self.pivot_widget = None
            self.summary_message_widget = None
            self.table_view = None

        self.setup_connections()
        self.load_layers()
        self.apply_styles()
        harmonize_widget_fonts(self)
        apply_windows_title_bar_theme(self, self._current_theme_mode() == "dark")
        self.on_export_format_changed()

        try:
            self.show_summary_welcome()
        except Exception:
            log_exception("falha opcional ignorada")
        QTimer.singleShot(0, self._reset_initial_summary_layer_selection)

        try:
            self._init_ribbon_actions()
        except Exception:
            log_exception("falha opcional ignorada")

        try:
            self._apply_runtime_translations()
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            self.apply_styles()
        except Exception:
            log_exception("falha opcional ignorada")
        QTimer.singleShot(0, self._refresh_database_sidebar_state)
        QTimer.singleShot(250, self._finish_deferred_initial_page_build)

    def _enable_native_window_controls(self):
        try:
            flags = self.windowFlags()
            flags |= (
                Qt.Window
                | Qt.WindowTitleHint
                | Qt.WindowSystemMenuHint
                | Qt.WindowMinimizeButtonHint
                | Qt.WindowMaximizeButtonHint
                | Qt.WindowCloseButtonHint
            )
            self.setWindowFlags(flags)
        except Exception:
            log_exception("falha opcional ignorada")

    def closeEvent(self, event):
        try:
            if hasattr(self, "presentation_controller") and self.presentation_controller:
                self.presentation_controller.cleanup()
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            host = getattr(self, "_plugin_host", None)
            if host is not None and getattr(host, "dlg", None) is self:
                host.dlg = None
        except Exception:
            log_exception("falha opcional ignorada")
        super().closeEvent(event)

    def _finish_deferred_initial_page_build(self):
        self._defer_page_build = False
        try:
            current_page = self.ui.stackedWidget.currentWidget()
        except Exception:
            current_page = None
        builders = []
        if current_page is self.ui.pageModel:
            builders.append(("model", self._ensure_model_page))
        elif current_page is self.ui.pageIntegracao:
            builders.append(("integration", self._ensure_integration_page))

        for name, builder in (
            ("model", self._ensure_model_page),
            ("integration", self._ensure_integration_page),
            ("dashboard", self._ensure_dashboard_widget),
        ):
            if all(existing_name != name for existing_name, _ in builders):
                builders.append((name, builder))

        self._deferred_page_build_queue = builders
        self._prewarm_next_deferred_page()

    def _prewarm_next_deferred_page(self):
        if not self._deferred_page_build_queue:
            return
        _name, builder = self._deferred_page_build_queue.pop(0)
        try:
            builder()
        except Exception:
            log_exception("falha opcional ignorada")
        QTimer.singleShot(350, self._prewarm_next_deferred_page)

    def toggle_window_state(self):
        if self.isMaximized():
            self.showNormal()
            try:
                self.ui.maximize_btn.setText("Max")
                self.ui.maximize_btn.setToolTip(_rt_runtime("Maximizar"))
            except Exception:
                log_exception("falha opcional ignorada")
        else:
            self.showMaximized()
            try:
                self.ui.maximize_btn.setText("Res")
                self.ui.maximize_btn.setToolTip(_rt_runtime("Restaurar"))
            except Exception:
                log_exception("falha opcional ignorada")

    def _normalize_locale_choice(self, locale_code: str) -> str:
        code = str(locale_code or "").strip()
        if not code:
            return "auto"
        if code.lower() == "auto":
            return "auto"
        if code.startswith("qgis_") or code.startswith("qgis-"):
            code = code[5:]
        short = re.split(r"[-_]", code, maxsplit=1)[0].lower()
        if short in {"pt", "en", "es"}:
            return short
        return "auto"

    def _effective_locale_choice(self, locale_code: str) -> str:
        normalized = self._normalize_locale_choice(locale_code)
        if normalized != "auto":
            return normalized
        try:
            user_locale = str(QSettings().value("locale/userLocale", "") or "").strip().lower()
        except Exception:
            user_locale = ""
        if user_locale.startswith("qgis_") or user_locale.startswith("qgis-"):
            user_locale = user_locale[5:]
        short = re.split(r"[-_]", user_locale, maxsplit=1)[0].lower() if user_locale else ""
        return short if short in {"pt", "en", "es"} else "en"

    def _current_locale_choice(self) -> str:
        raw = str(QSettings().value(self._language_settings_key, "auto") or "").strip()
        return self._normalize_locale_choice(raw)

    def _language_button_text(self, choice: str) -> str:
        normalized = self._normalize_locale_choice(choice)
        if normalized == "auto":
            return "Auto"
        return normalized.upper()[:4]

    def _language_label(self, choice: str) -> str:
        normalized = self._normalize_locale_choice(choice)
        labels = {
            "auto": _rt_runtime("Automático"),
            "pt": _rt_runtime("Português"),
            "en": "English",
            "es": "Español",
        }
        if normalized == "auto":
            effective = self._effective_locale_choice(choice)
            return f"{labels['auto']} · {labels.get(effective, effective.upper())}"
        return labels.get(normalized, normalized.upper())

    def _refresh_language_button(self):
        btn = getattr(self.ui, "language_btn", None)
        if btn is None:
            return
        choice = self._current_locale_choice()
        try:
            btn.setIcon(svg_icon("Globe.svg"))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        except Exception:
            log_exception("falha opcional ignorada")
        btn.setText(self._language_button_text(choice))
        btn.setToolTip(f"{_rt_runtime('Idioma')}: {self._language_label(choice)}")

    def _set_locale_choice(self, locale_code: str):
        normalized = self._normalize_locale_choice(locale_code)
        current = self._current_locale_choice()
        if normalized == current:
            return
        settings = QSettings()
        settings.setValue(self._language_settings_key, normalized)
        self._refresh_language_button()
        host = getattr(self, "_plugin_host", None)
        if host is not None and hasattr(host, "reload_dialog_for_language"):
            host.reload_dialog_for_language()

    def _build_language_menu(self) -> QMenu:
        menu = apply_walker_menu(QMenu(self))
        choice = self._current_locale_choice()
        options = [
            ("auto", _rt_runtime("Automático")),
            ("pt", _rt_runtime("Português")),
            ("en", "English"),
            ("es", "Español"),
        ]
        for code, label in options:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(choice == code)
            action.triggered.connect(lambda _checked=False, c=code: self._set_locale_choice(c))
        return menu

    def _show_language_menu(self):
        btn = getattr(self.ui, "language_btn", None)
        if btn is None:
            return
        menu = self._build_language_menu()
        menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _init_language_button(self):
        btn = getattr(self.ui, "language_btn", None)
        if btn is None:
            return
        try:
            btn.clicked.connect(self._show_language_menu)
        except Exception:
            log_exception("falha opcional ignorada")
        self._refresh_language_button()

    def _normalize_theme_mode(self, value: str) -> str:
        mode = str(value or "").strip().lower()
        return "dark" if mode == "dark" else "light"

    def _current_theme_mode(self) -> str:
        raw = str(QSettings().value(self._theme_settings_key, "light") or "light")
        return self._normalize_theme_mode(raw)

    def _theme_label(self, mode: str) -> str:
        if self._normalize_theme_mode(mode) == "dark":
            return _rt_runtime("Escuro")
        return _rt_runtime("Claro")

    def _refresh_theme_button(self):
        btn = getattr(self.ui, "theme_btn", None)
        if btn is None:
            return
        mode = self._current_theme_mode()
        try:
            btn.setIcon(svg_icon("Theme.svg"))
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        except Exception:
            log_exception("falha opcional ignorada")
        btn.setText("")
        btn.setToolTip(f"{_rt_runtime('Tema')}: {self._theme_label(mode)}")

    def _set_theme_mode(self, mode: str):
        normalized = self._normalize_theme_mode(mode)
        current = self._current_theme_mode()
        if normalized == current:
            return
        QSettings().setValue(self._theme_settings_key, normalized)
        self.apply_styles()
        self._refresh_theme_button()
        apply_windows_title_bar_theme(self, normalized == "dark")

    def _build_theme_menu(self) -> QMenu:
        menu = apply_walker_menu(QMenu(self))
        current = self._current_theme_mode()
        for mode, label in (("light", _rt_runtime("Claro")), ("dark", _rt_runtime("Escuro"))):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current == mode)
            action.triggered.connect(lambda _checked=False, m=mode: self._set_theme_mode(m))
        return menu

    def _show_theme_menu(self):
        btn = getattr(self.ui, "theme_btn", None)
        if btn is None:
            return
        menu = self._build_theme_menu()
        menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _init_theme_button(self):
        btn = getattr(self.ui, "theme_btn", None)
        if btn is None:
            return
        try:
            btn.clicked.connect(self._show_theme_menu)
        except Exception:
            log_exception("falha opcional ignorada")
        self._refresh_theme_button()

    def _init_presentation_button(self):
        if self.presentation_map_btn is not None:
            return

        controller = getattr(self, "presentation_controller", None)
        if controller is None:
            return

        header_widget = getattr(self.ui, "header_widget", None)
        if header_widget is None:
            return

        try:
            btn = create_presentation_button(header_widget, controller)
        except Exception:
            log_exception("falha opcional ignorada")
            return

        try:
            layout = header_widget.layout()
            theme_btn = getattr(self.ui, "theme_btn", None)
            if layout is not None and theme_btn is not None:
                index = layout.indexOf(theme_btn)
                if index >= 0:
                    layout.insertWidget(index + 1, btn)
                else:
                    layout.addWidget(btn)
            elif layout is not None:
                layout.addWidget(btn)
        except Exception:
            log_exception("falha opcional ignorada")
            try:
                btn.setParent(None)
            except Exception:
                pass
            return

        self.presentation_map_btn = btn

    def _mark_theme_mode(self, mode: str):
        normalized = self._normalize_theme_mode(mode)
        widgets = [self]
        try:
            widgets.extend(self.findChildren(QWidget))
        except Exception:
            log_exception("falha opcional ignorada")
        for widget in widgets:
            try:
                widget.setProperty("themeMode", normalized)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            except Exception:
                continue

    def _refresh_theme_aware_children(self):
        for attr, method_name in (
            ("pivot_widget", "_apply_styles"),
            ("dashboard_widget", "_apply_styles"),
            ("integration_panel", "_apply_panel_styles"),
            ("model_tab", "_apply_visual_side_panel_styles"),
            ("model_tab", "_apply_dark_theme_overlay"),
            ("model_tab", "_refresh_theme_icons"),
        ):
            widget = getattr(self, attr, None)
            method = getattr(widget, method_name, None) if widget is not None else None
            if method is None:
                continue
            try:
                method()
            except Exception:
                log_exception("falha opcional ignorada")

    def _apply_runtime_translations(self):
        _apply_i18n_widgets(self)

    # ---------------------------------------------------------------- Ribbon
    def _init_ribbon_actions(self):
        ui = self.ui
        btn = getattr(ui, "ribbon_get_data_btn", None)
        if btn is not None:
            btn.clicked.connect(self.open_get_data_dialog)
        self._set_ribbon_visible(False)

    def _set_ribbon_visible(self, visible: bool):
        bar = getattr(self.ui, "ribbon_bar", None)
        if bar is None:
            return
        bar.setVisible(bool(visible))
        # Garantir que o stack de páginas nunca seja ocultado
        stacked = getattr(self.ui, "stackedWidget", None)
        if stacked is not None:
            stacked.setVisible(True)
        central = getattr(self.ui, "central_frame", None)
        if central is not None:
            central.setVisible(True)

    def _apply_card_markers(self):
        """Marca frames e layouts para o tema de cards."""
        cards = [
            getattr(self.ui, "results_header_frame", None),
            getattr(self.ui, "export_card", None),
        ]
        for card in cards:
            if card is not None:
                card.setProperty("card", True)

        titles = [
            getattr(self.ui, "export_info_label", None),
        ]
        for label in titles:
            if label is not None:
                label.setProperty("cardTitle", True)

        layout = getattr(self.ui, "results_body_layout", None)
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

    def apply_styles(self):
        """Aplica o style.qss oficial do plugin (arquivo principal de temas)."""
        style_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
        theme_mode = self._current_theme_mode()
        self._mark_theme_mode(theme_mode)
        if not os.path.exists(style_path):
            self._apply_square_theme()
            return

        try:
            with open(style_path, "r", encoding="utf-8") as handler:
                template = Template(handler.read())
            context = palette_context(theme_mode)
            self.setStyleSheet(template.safe_substitute(context))
        except Exception:
            try:
                with open(style_path, "r", encoding="utf-8") as handler:
                    self.setStyleSheet(handler.read())
            except Exception:
                log_exception("falha opcional ignorada")
        harmonize_widget_fonts(self)
        self._refresh_theme_aware_children()
        self._mark_theme_mode(theme_mode)
        if getattr(self, "sidebar", None) is not None:
            try:
                self.sidebar.refresh_styles()
            except Exception:
                log_exception("falha opcional ignorada")
        self._square_theme_applied = False
        self._apply_square_theme()
        self._refresh_theme_button()
        apply_windows_title_bar_theme(self, theme_mode == "dark")

    def showEvent(self, event):
        super().showEvent(event)
        try:
            apply_windows_title_bar_theme(self, self._current_theme_mode() == "dark")
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_square_theme(self):
        if getattr(self, "_square_theme_applied", False):
            return
        if not getattr(self, "_square_scopes", None):
            return
        square_path = os.path.join(os.path.dirname(__file__), "ui", "square.qss")
        if not os.path.exists(square_path):
            return
        try:
            with open(square_path, "r", encoding="utf-8") as handler:
                square_qss = handler.read()
        except Exception:
            return
        existing = self.styleSheet() or ""
        combined = f"{existing}\n{square_qss}" if existing else square_qss
        self.setStyleSheet(combined)
        self._square_theme_applied = True

    def set_model_toolbar_visible(self, visible: bool):
        self._set_ribbon_visible(bool(visible))

    def setup_connections(self):
        self.ui.layer_combo.layerChanged.connect(self.on_layer_changed)
        self.ui.dashboard_btn.clicked.connect(self.show_dashboard)

        self.ui.export_execute_btn.clicked.connect(self.export_results)
        self.ui.export_browse_btn.clicked.connect(self.choose_export_path)
        self.ui.export_format_combo.currentIndexChanged.connect(
            self.on_export_format_changed
        )
        self.ui.export_path_edit.editingFinished.connect(self.on_export_path_edited)
        # External integration connections removed (handled by dedicated dialog)

    def _set_results_view(self, mode: str):
        """Switch between pivot (summary), message (HTML) and table (comparison) views."""
        _summary_set_results_view(
            getattr(self, "pivot_widget", None),
            getattr(self, "summary_message_widget", None),
            getattr(self, "table_view", None),
            mode,
        )

    def show_results_message(self, html: str):
        """Display HTML content in the results area."""
        message_widget = getattr(self, "summary_message_widget", None)
        if message_widget is None:
            return
        _summary_show_results_message(
            message_widget,
            html,
            set_results_view=self._set_results_view,
        )

    def show_summary_welcome(self):
        _summary_show_summary_welcome(
            getattr(self, "pivot_widget", None),
            getattr(self, "summary_message_widget", None),
            set_results_view=self._set_results_view,
            set_ribbon_visible=self._set_ribbon_visible,
            welcome_html=_summary_build_welcome_html(
                _rt_runtime("Selecione uma camada e clique em Gerar Resumo.")
            ),
        )

    def _reset_initial_summary_layer_selection(self):
        combo = getattr(self.ui, "layer_combo", None)
        if combo is None:
            return
        try:
            combo.blockSignals(True)
            try:
                combo.setCurrentLayer(None)
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                combo.setCurrentIndex(-1)
            except Exception:
                log_exception("falha opcional ignorada")
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                log_exception("falha opcional ignorada")
        self._active_numeric_field = None

    def _page_layout(self, page, spacing: int = 0):
        layout = page.layout()
        if layout is None:
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(spacing)
        return layout

    def _clear_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _ensure_model_backend(self):
        if self.model_manager is not None:
            return self.model_manager
        try:
            from .model_view import ModelCanvasScene, ModelCanvasView, ModelManager

            if self._model_backend_host is None:
                self._model_backend_host = QWidget(self)
                self._model_backend_host.hide()
            self._model_scene = ModelCanvasScene(self._model_backend_host)
            self._model_view = ModelCanvasView(self._model_scene, self._model_backend_host)
            self.model_manager = ModelManager(self._model_scene, self._model_view, self)
            self.model_manager.refresh_model()
        except Exception:
            self.model_manager = None
            log_exception("falha opcional ignorada")
        return self.model_manager

    def _ensure_model_page(self):
        if self.model_tab is not None:
            return self.model_tab
        try:
            from .model_tab import ModelTab

            self._ensure_model_backend()
            layout = self._page_layout(self.ui.pageModel, spacing=0)
            self._clear_layout_widgets(layout)
            widget = ModelTab(parent=self.ui.pageModel)
            layout.addWidget(widget)
            self.model_tab = widget
        except Exception:
            self.model_tab = None
            log_exception("falha opcional ignorada")
        return self.model_tab

    def _ensure_integration_page(self):
        if self.integration_panel is not None:
            return self.integration_panel
        try:
            from .integration_panel import IntegrationPanel

            layout = self._page_layout(self.ui.pageIntegracao, spacing=0)
            self._clear_layout_widgets(layout)
            self.ui.integration_placeholder = None

            scroll = QScrollArea(self.ui.pageIntegracao)
            scroll.setObjectName("integrationScrollArea")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            layout.addWidget(scroll, 1)
            self.integration_scroll = scroll

            panel = IntegrationPanel(self, self.iface)
            scroll.setWidget(panel)
            self.integration_panel = panel
        except Exception:
            self.integration_panel = None
            log_exception("falha opcional ignorada")
        return self.integration_panel

    def _current_database_connection_meta(self) -> Dict:
        try:
            from .database_explorer import provider_key_for_driver

            connections = connection_registry.all_connections()
            for connection in connections:
                if provider_key_for_driver(str(connection.get("driver") or "")):
                    return dict(connection)
        except Exception:
            log_exception("falha opcional ignorada")
        return {}

    def _ensure_database_explorer_page(self):
        if self.database_explorer_panel is not None:
            return self.database_explorer_panel
        try:
            from .database_explorer.database_explorer_panel import DatabaseExplorerPanel

            layout = self._page_layout(self.ui.pageDatabaseExplorer, spacing=0)
            self._clear_layout_widgets(layout)
            panel = DatabaseExplorerPanel(parent=self.ui.pageDatabaseExplorer)
            panel.tableActivated.connect(self._handle_database_object_activated)
            panel.connectionEditRequested.connect(self._open_database_connection_dialog)
            panel.statusChanged.connect(self._update_database_sidebar_status)
            layout.addWidget(panel)
            self.database_explorer_panel = panel
        except Exception:
            self.database_explorer_panel = None
            log_exception("falha opcional ignorada")
        return self.database_explorer_panel

    def _update_database_sidebar_status(self, status: str):
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None:
            return
        try:
            set_status = getattr(sidebar, "set_database_status", None)
            if callable(set_status):
                set_status(status)
        except Exception:
            log_exception("falha opcional ignorada")

    def _open_database_connection_dialog(self, connection_meta: Optional[Dict] = None):
        try:
            from .integration_panel import DatabaseImportDialog

            active_connection = self._database_dialog_connection_meta(connection_meta or {})
            saved = connection_registry.saved_connections()
            if active_connection:
                fingerprint = str(active_connection.get("fingerprint") or "")
                saved = [
                    conn
                    for conn in saved
                    if str(conn.get("fingerprint") or "") != fingerprint
                ]
                saved.insert(0, active_connection)
            preferred_driver = str(
                active_connection.get("source_driver")
                or active_connection.get("driver")
                or "PostgreSQL"
            )
            dialog = DatabaseImportDialog(self.dlg, saved, preferred_driver=preferred_driver)
            result = dialog.exec_()
            if result != QDialog.Accepted:
                self._refresh_database_sidebar_state()
                return
            df, metadata, updated_connection, session_connection = dialog.result()
            if df is not None and not df.empty:
                self.register_integration_dataframe(df, metadata or {"connector": preferred_driver})
            if session_connection:
                connection_registry.register_runtime_connection(session_connection)
            if updated_connection:
                fingerprint = updated_connection.get("fingerprint")
                saved = [
                    conn
                    for conn in connection_registry.saved_connections()
                    if conn.get("fingerprint") != fingerprint
                ]
                saved.insert(0, updated_connection)
                connection_registry.replace_saved_connections(saved, persist=True)
            self._refresh_database_sidebar_state()
        except Exception:
            log_exception("falha opcional ignorada")

    def _database_dialog_connection_meta(self, connection_meta: Dict) -> Dict:
        meta = dict(connection_meta or {})
        if not meta:
            return {}
        driver = str(meta.get("source_driver") or meta.get("driver") or "").strip()
        normalized_driver = driver.lower()
        if normalized_driver in {"postgres", "postgresql", "postgis"}:
            dialog_driver = "PostGIS" if normalized_driver == "postgis" else "PostgreSQL"
            meta["driver"] = dialog_driver
            meta["source_driver"] = dialog_driver
            meta.setdefault("port", 5432)
        if not meta.get("fingerprint"):
            meta["fingerprint"] = "::".join(
                [
                    str(meta.get("driver") or "").lower(),
                    str(meta.get("host") or meta.get("service") or ""),
                    str(meta.get("port") or ""),
                    str(meta.get("database") or ""),
                    str(meta.get("user") or meta.get("username") or ""),
                ]
            )
        return meta

    def _handle_database_object_activated(self, database_object):
        connection_meta = dict(getattr(self, "_database_explorer_connection_meta", {}) or {})
        if not connection_meta:
            self._finish_database_object_activation(database_object, loaded=False)
            return
        name = str(getattr(database_object, "name", "") or "").strip()
        schema = str(getattr(database_object, "schema", "") or "").strip()
        geometry_column = str(getattr(database_object, "geometry_column", "") or "").strip()
        provider_key = str(getattr(database_object, "provider_key", "") or "").strip()
        loaded_successfully = False
        self._database_explorer_activation_error = ""
        try:
            if geometry_column and provider_key == "postgres":
                descriptor = {
                    "connector": connection_meta.get("driver") or "PostgreSQL",
                    "display_name": name,
                    "db_connection": connection_meta,
                    "schema": schema,
                    "table_name": name,
                    "geometry_column": geometry_column,
                    "import_target": "project",
                }
                try:
                    layer = self._load_integration_database_layer(descriptor)
                except Exception:
                    layer = None
                    log_exception("falha opcional ignorada")
                if layer is not None and layer.isValid():
                    loaded_successfully = True
                    self._database_explorer_activation_error = ""
                    try:
                        self._database_explorer_layer_objects[layer.id()] = database_object
                    except Exception:
                        log_exception("falha opcional ignorada")
                    try:
                        if self.model_manager is not None:
                            self.model_manager.refresh_model()
                    except Exception:
                        log_exception("falha opcional ignorada")
                    return
                if layer is not None:
                    self._database_explorer_activation_error = self._layer_error_text(layer)
            try:
                detail = str(getattr(self, "_database_explorer_activation_error", "") or "").strip()
                if detail:
                    message = _rt_runtime(
                        "Nao foi possivel abrir esta camada diretamente.\n\nDetalhe: {detail}",
                        detail=detail,
                    )
                else:
                    message = _rt_runtime("Abra o importador de banco para carregar esta tabela.")
                QMessageBox.information(
                    self,
                    _rt_runtime("Banco"),
                    message,
                )
            except Exception:
                log_exception("falha opcional ignorada")
        finally:
            self._finish_database_object_activation(database_object, loaded=loaded_successfully)

    def _finish_database_object_activation(self, database_object, loaded: bool = False):
        panel = getattr(self, "database_explorer_panel", None)
        marker = getattr(panel, "mark_object_loaded", None)
        if callable(marker):
            try:
                marker(database_object, loaded=loaded)
            except Exception:
                log_exception("falha opcional ignorada")

    def _handle_database_layers_removed(self, layer_ids):
        removed_ids = list(layer_ids or [])
        if not removed_ids:
            return
        panel = getattr(self, "database_explorer_panel", None)
        marker = getattr(panel, "mark_object_unloaded", None)
        for layer_id in removed_ids:
            database_object = self._database_explorer_layer_objects.pop(layer_id, None)
            if database_object is None or not callable(marker):
                continue
            try:
                marker(database_object)
            except Exception:
                log_exception("falha opcional ignorada")

    def _refresh_database_sidebar_state(self):
        connection_meta = self._current_database_connection_meta()
        self._database_explorer_connection_meta = dict(connection_meta)
        visible = bool(connection_meta)
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None:
            try:
                sidebar.set_database_tab_visible(visible)
                sidebar.set_database_connected(visible)
            except Exception:
                log_exception("falha opcional ignorada")
        panel = getattr(self, "database_explorer_panel", None)
        if panel is not None:
            if connection_meta:
                try:
                    panel.set_connection(connection_meta)
                except Exception:
                    log_exception("falha opcional ignorada")
            else:
                try:
                    panel.clear()
                except Exception:
                    log_exception("falha opcional ignorada")

    def show_database_explorer_page(self):
        self._set_ribbon_visible(False)
        connection_meta = self._current_database_connection_meta()
        self._database_explorer_connection_meta = dict(connection_meta)
        try:
            self.ui.stackedWidget.setCurrentWidget(self.ui.pageDatabaseExplorer)
        except Exception:
            log_exception("falha opcional ignorada")
        panel = self._ensure_database_explorer_page()
        if panel is not None:
            try:
                if connection_meta:
                    panel.set_connection(connection_meta)
                else:
                    panel.clear()
            except Exception:
                log_exception("falha opcional ignorada")
        self._refresh_database_sidebar_state()

    def _ensure_dashboard_widget(self):
        if self.dashboard_widget is not None:
            return self.dashboard_widget
        try:
            from .dashboard_widget import DashboardWidget

            self.dashboard_widget = DashboardWidget()
        except Exception:
            self.dashboard_widget = None
            log_exception("falha opcional ignorada")
        return self.dashboard_widget

    def show_integration_page(self):
        self._set_ribbon_visible(False)
        try:
            self.ui.stackedWidget.setCurrentWidget(self.ui.pageIntegracao)
        except Exception:
            log_exception("falha opcional ignorada")
        panel = None if self._defer_page_build else self._ensure_integration_page()
        try:
            self._apply_runtime_translations()
        except Exception:
            log_exception("falha opcional ignorada")
        scroll = getattr(self, "integration_scroll", None)
        if scroll is not None:
            try:
                scroll.verticalScrollBar().setValue(0)
            except Exception:
                log_exception("falha opcional ignorada")
        if panel is not None:
            try:
                panel.refresh_recents()
            except Exception:
                log_exception("falha opcional ignorada")

    def show_model_page(self):
        self._set_ribbon_visible(False)
        try:
            self.ui.stackedWidget.setCurrentWidget(self.ui.pageModel)
        except Exception:
            log_exception("falha opcional ignorada")
        if not self._defer_page_build:
            self._ensure_model_page()
        try:
            self._apply_runtime_translations()
        except Exception:
            log_exception("falha opcional ignorada")

    def handle_add_chart_to_model_request(self, snapshot):
        model_tab = self._ensure_model_page()
        if model_tab is None or not snapshot:
            return
        added = False
        try:
            added = bool(model_tab.request_add_chart(dict(snapshot or {})))
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Model",
                f"Nao foi possivel adicionar o grafico ao Model: {exc}",
            )
            return
        if not added:
            return
        try:
            if getattr(self, "sidebar", None) is not None:
                self.sidebar.show_model_page()
            else:
                self.show_model_page()
        except Exception:
            self.show_model_page()

    def open_get_data_dialog(self):
        dialog = GetDataDialog(self, self)
        _apply_i18n_widgets(dialog)
        if dialog.exec_() != QDialog.Accepted:
            return
        datasets = dialog.results()
        if not datasets:
            return
        for df, metadata in datasets:
            try:
                self.register_integration_dataframe(df, metadata)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    _rt_runtime("Obter Dados"),
                    _rt_runtime("Falha ao registrar dados: {exc}", exc=exc),
                )
        try:
            self.sidebar.show_results_page()
        except Exception:
            self.show_summary_welcome()

    def register_integration_dataframe(self, df: pd.DataFrame, metadata: Dict) -> Dict:
        if df is None or df.empty:
            return {}

        descriptor = dict(metadata or {})
        descriptor.setdefault("display_name", descriptor.get("source_path") or "Dados externos")
        descriptor.setdefault("connector", descriptor.get("connector") or "Fonte externa")
        descriptor.setdefault("record_count", int(len(df)))
        descriptor.setdefault(
            "timestamp",
            descriptor.get("timestamp") or datetime.now().isoformat(),
        )
        import_target = str(descriptor.get("import_target") or "").strip().lower()

        layer = self._create_integration_project_layer(df, descriptor)
        if layer is not None and layer.isValid():
            descriptor["layer_id"] = layer.id()
            descriptor["layer_name"] = layer.name()
            self.integration_datasets[layer.id()] = df.copy()
            try:
                if self.model_manager is not None:
                    self.model_manager.refresh_model()
            except Exception:
                log_exception("falha opcional ignorada")
        if import_target == "project":
            if not descriptor.get("layer_id"):
                return {}
            return descriptor

        summary_data = self._build_dataframe_summary(df, descriptor)
        self.current_summary_data = summary_data
        self.display_advanced_summary(summary_data)
        self.update_charts_preview(summary_data)
        self.prepare_export_tab_defaults(summary_data)

        self.sidebar.show_results_page()
        return descriptor

    def _create_integration_project_layer(
        self,
        df: pd.DataFrame,
        descriptor: Dict,
    ) -> Optional[QgsVectorLayer]:
        connector = str(descriptor.get("connector") or "").strip().lower()
        source_path = str(descriptor.get("source_path") or "").strip()
        geometry_column = str(descriptor.get("geometry_column") or "").strip()
        if connector in ("postgresql", "postgis") and geometry_column:
            try:
                return self._load_integration_database_layer(descriptor)
            except Exception:
                log_exception("falha opcional ignorada")
        if connector == "geopackage" and source_path and os.path.exists(source_path):
            try:
                return self._load_integration_source_layer(source_path, descriptor)
            except Exception:
                log_exception("falha opcional ignorada")
        try:
            layer = self._materialize_integration_text_layer(df, descriptor)
            if layer is not None and layer.isValid():
                return layer
        except Exception:
            log_exception("falha opcional ignorada")
        return self._create_memory_table_from_dataframe(df, descriptor)

    def _load_integration_source_layer(
        self,
        source_path: str,
        descriptor: Dict,
    ) -> Optional[QgsVectorLayer]:
        base_name = (
            descriptor.get("display_name")
            or os.path.basename(source_path)
            or "Camada externa"
        ).strip()
        if not base_name:
            base_name = "Camada externa"

        project = QgsProject.instance()
        existing_names = {layer.name() for layer in project.mapLayers().values()}
        name = base_name
        suffix = 2
        while name in existing_names:
            name = f"{base_name} ({suffix})"
            suffix += 1

        layer = QgsVectorLayer(source_path, name, "ogr")
        if not layer or not layer.isValid():
            return None
        return self._add_layer_to_project(layer)

    def _load_integration_database_layer(self, descriptor: Dict) -> Optional[QgsVectorLayer]:
        connection = descriptor.get("db_connection") or {}
        schema = str(descriptor.get("schema") or "").strip()
        table_name = str(descriptor.get("table_name") or "").strip()
        geometry_column = str(descriptor.get("geometry_column") or "").strip()
        if not table_name or not geometry_column:
            return None

        uri = QgsDataSourceUri()
        authcfg = str(connection.get("authcfg") or "")
        if authcfg:
            uri.setConnection(
                str(connection.get("host") or ""),
                str(connection.get("port") or ""),
                str(connection.get("database") or ""),
                str(connection.get("user") or ""),
                "",
            )
            uri.setAuthConfigId(authcfg)
        else:
            uri.setConnection(
                str(connection.get("host") or ""),
                str(connection.get("port") or ""),
                str(connection.get("database") or ""),
                str(connection.get("user") or ""),
                str(connection.get("password") or ""),
            )
        table_meta = self._postgres_layer_open_metadata(
            connection,
            schema,
            table_name,
            geometry_column,
        )
        key_column = str(table_meta.get("key_column") or "")
        try:
            uri.setDataSource(schema, table_name, geometry_column, "", key_column)
        except TypeError:
            uri.setDataSource(schema, table_name, geometry_column)
            if key_column:
                try:
                    uri.setKeyColumn(key_column)
                except Exception:
                    uri.setParam("key", key_column)

        srid = str(table_meta.get("srid") or "")
        geometry_type = str(table_meta.get("geometry_type") or "")
        if srid:
            try:
                uri.setSrid(srid)
            except Exception:
                uri.setParam("srid", srid)
        if geometry_type:
            uri.setParam("type", geometry_type)

        base_name = (descriptor.get("display_name") or table_name or "Camada externa").strip()
        if not base_name:
            base_name = table_name or "Camada externa"

        layer_name = self._unique_layer_name(base_name)
        source_uri = uri.uri()
        layer = self._add_database_layer_via_iface(source_uri, layer_name)
        if layer is not None and layer.isValid():
            style_uris = [
                layer.source(),
                source_uri,
                self._postgres_table_uri(uri, schema, table_name),
            ]
            self._apply_database_native_style(
                layer,
                style_uris,
                connection,
                schema,
                table_name,
                geometry_column,
            )
            return layer

        layer_options = QgsVectorLayer.LayerOptions()
        try:
            layer_options.loadDefaultStyle = True
            layer_options.loadAllStoredStyles = True
        except Exception:
            log_exception("falha opcional ignorada")
        layer = QgsVectorLayer(source_uri, layer_name, "postgres", layer_options)
        if not layer or not layer.isValid():
            return None
        style_uris = [
            layer.source(),
            source_uri,
            self._postgres_table_uri(uri, schema, table_name),
        ]
        self._apply_database_native_style(
            layer,
            style_uris,
            connection,
            schema,
            table_name,
            geometry_column,
        )
        return self._add_layer_to_project(layer)

    def _add_database_layer_via_iface(self, source_uri: str, layer_name: str) -> Optional[QgsVectorLayer]:
        add_vector_layer = getattr(self.iface, "addVectorLayer", None)
        if not callable(add_vector_layer):
            return None
        try:
            layer = add_vector_layer(source_uri, layer_name, "postgres")
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Falha ao adicionar camada PostGIS via iface.addVectorLayer: {exc}",
                "Summarizer",
                Qgis.Warning,
            )
            return None
        if layer is None or not layer.isValid():
            return None
        return layer

    def _postgres_layer_open_metadata(
        self,
        connection_meta: Dict,
        schema: str,
        table_name: str,
        geometry_column: str,
    ) -> Dict[str, str]:
        result = {"key_column": "", "srid": "", "geometry_type": ""}
        if QSqlDatabase is None or QSqlQuery is None:
            return result
        if str(connection_meta.get("authcfg") or "").strip():
            return result

        conn_name = f"summarizer_layer_meta_{uuid.uuid4().hex}"
        db = None
        try:
            db = QSqlDatabase.addDatabase("QPSQL", conn_name)
            db.setHostName(str(connection_meta.get("host") or ""))
            try:
                db.setPort(int(connection_meta.get("port") or 5432))
            except Exception:
                db.setPort(5432)
            db.setDatabaseName(str(connection_meta.get("database") or ""))
            db.setUserName(str(connection_meta.get("user") or ""))
            db.setPassword(str(connection_meta.get("password") or ""))
            if not db.open():
                return result

            pk_query = QSqlQuery(db)
            if pk_query.prepare(
                "SELECT a.attname "
                "FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) "
                "WHERE i.indisprimary "
                "  AND n.nspname = :schema "
                "  AND c.relname = :table_name "
                "ORDER BY array_position(i.indkey, a.attnum) "
                "LIMIT 1"
            ):
                pk_query.bindValue(":schema", schema)
                pk_query.bindValue(":table_name", table_name)
                if pk_query.exec_() and pk_query.next():
                    result["key_column"] = str(pk_query.value(0) or "")

            geom_query = QSqlQuery(db)
            if geom_query.prepare(
                "SELECT "
                "  NULLIF(Find_SRID(:schema, :table_name, :geometry_column), 0), "
                "  UPPER(GeometryType(("
                "    SELECT {geom} "
                "    FROM {schema_table} "
                "    WHERE {geom} IS NOT NULL "
                "    LIMIT 1"
                "  )))"
                .format(
                    geom=self._pg_quote_identifier(geometry_column),
                    schema_table=(
                        f"{self._pg_quote_identifier(schema)}."
                        f"{self._pg_quote_identifier(table_name)}"
                    ),
                )
            ):
                geom_query.bindValue(":schema", schema)
                geom_query.bindValue(":table_name", table_name)
                geom_query.bindValue(":geometry_column", geometry_column)
                if geom_query.exec_() and geom_query.next():
                    srid = str(geom_query.value(0) or "")
                    geometry_type = self._qgis_uri_geometry_type(str(geom_query.value(1) or ""))
                    if srid:
                        result["srid"] = srid
                    if geometry_type:
                        result["geometry_type"] = geometry_type
        except Exception:
            log_exception("falha opcional ignorada")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    log_exception("falha opcional ignorada")
            try:
                QSqlDatabase.removeDatabase(conn_name)
            except Exception:
                log_exception("falha opcional ignorada")
        return result

    def _pg_quote_identifier(self, identifier: str) -> str:
        return '"' + str(identifier or "").replace('"', '""') + '"'

    def _qgis_uri_geometry_type(self, geometry_type: str) -> str:
        normalized = str(geometry_type or "").upper().replace("ST_", "")
        if "MULTIPOINT" in normalized:
            return "MultiPoint"
        if "MULTILINESTRING" in normalized:
            return "MultiLineString"
        if "MULTIPOLYGON" in normalized:
            return "MultiPolygon"
        if "POINT" in normalized:
            return "Point"
        if "LINESTRING" in normalized:
            return "LineString"
        if "POLYGON" in normalized:
            return "Polygon"
        return ""

    def _postgres_table_uri(self, uri: QgsDataSourceUri, schema: str, table_name: str) -> str:
        if not schema or not table_name:
            return ""
        try:
            metadata = QgsProviderRegistry.instance().providerMetadata("postgres")
        except Exception:
            metadata = None
        if metadata is None:
            return ""
        try:
            connection = metadata.createConnection(uri.connectionInfo(), {})
        except Exception:
            connection = None
        if connection is None:
            return ""
        table_uri_getter = getattr(connection, "tableUri", None)
        if not callable(table_uri_getter):
            return ""
        try:
            return str(table_uri_getter(schema, table_name) or "")
        except Exception:
            return ""

    def _apply_database_native_style(
        self,
        layer: Optional[QgsVectorLayer],
        uris,
        connection_meta: Optional[Dict] = None,
        schema: str = "",
        table_name: str = "",
        geometry_column: str = "",
    ):
        if layer is None:
            return
        style_uris: List[str] = []
        if isinstance(uris, str):
            candidates = [uris]
        else:
            candidates = list(uris or [])
        for candidate in candidates:
            candidate_uri = str(candidate or "").strip()
            if candidate_uri and candidate_uri not in style_uris:
                style_uris.append(candidate_uri)

        if self._try_apply_postgres_layer_style_table(
            layer,
            connection_meta or {},
            schema,
            table_name,
            geometry_column,
        ):
            return
        for candidate_uri in style_uris:
            if self._try_load_provider_style(layer, candidate_uri):
                return
        for candidate_uri in style_uris:
            if self._try_load_layer_named_style(layer, candidate_uri):
                return
        if self._try_load_layer_default_style(layer):
            return

    def _try_load_layer_default_style(self, layer: QgsVectorLayer) -> bool:
        try:
            load_default_style = getattr(layer, "loadDefaultStyle", None)
            if not callable(load_default_style):
                return False
            return self._style_result_is_success(load_default_style())
        except Exception:
            log_exception("falha opcional ignorada")
        return False

    def _try_load_layer_named_style(self, layer: QgsVectorLayer, uri: str) -> bool:
        if not uri:
            return False
        try:
            load_named_style = getattr(layer, "loadNamedStyle", None)
            if not callable(load_named_style):
                return False
            return self._style_result_is_success(load_named_style(uri, False))
        except TypeError:
            try:
                return self._style_result_is_success(load_named_style(uri))
            except Exception:
                log_exception("falha opcional ignorada")
        except Exception:
            log_exception("falha opcional ignorada")
        return False

    def _try_load_provider_style(self, layer: QgsVectorLayer, uri: str) -> bool:
        if not uri:
            return False
        try:
            provider_registry = QgsProviderRegistry.instance()
        except Exception:
            return False
        provider_key = "postgres"

        for style_xml in self._provider_style_xml_candidates(provider_registry, provider_key, uri):
            if self._apply_style_xml(layer, style_xml):
                return True
        return False

    def _try_apply_postgres_layer_style_table(
        self,
        layer: QgsVectorLayer,
        connection_meta: Dict,
        schema: str,
        table_name: str,
        geometry_column: str,
    ) -> bool:
        style_xml = self._postgres_layer_style_qml(
            connection_meta,
            schema,
            table_name,
            geometry_column,
        )
        if not style_xml:
            return False
        return self._apply_style_xml(layer, style_xml)

    def _postgres_layer_style_qml(
        self,
        connection_meta: Dict,
        schema: str,
        table_name: str,
        geometry_column: str,
    ) -> str:
        if QSqlDatabase is None or QSqlQuery is None:
            return ""
        schema = str(schema or "").strip()
        table_name = str(table_name or "").strip()
        geometry_column = str(geometry_column or "").strip()
        if not schema or not table_name:
            return ""
        if str(connection_meta.get("authcfg") or "").strip():
            return ""

        conn_name = f"summarizer_style_{uuid.uuid4().hex}"
        db = None
        try:
            db = QSqlDatabase.addDatabase("QPSQL", conn_name)
            db.setHostName(str(connection_meta.get("host") or ""))
            try:
                db.setPort(int(connection_meta.get("port") or 5432))
            except Exception:
                db.setPort(5432)
            db.setDatabaseName(str(connection_meta.get("database") or ""))
            db.setUserName(str(connection_meta.get("user") or ""))
            db.setPassword(str(connection_meta.get("password") or ""))
            if not db.open():
                return ""

            for styles_schema in self._postgres_layer_style_schemas(db):
                style_xml = self._postgres_layer_style_qml_from_schema(
                    db,
                    styles_schema,
                    schema,
                    table_name,
                    geometry_column,
                )
                if style_xml:
                    return style_xml
            return ""
        except Exception:
            log_exception("falha opcional ignorada")
            return ""
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    log_exception("falha opcional ignorada")
            try:
                QSqlDatabase.removeDatabase(conn_name)
            except Exception:
                log_exception("falha opcional ignorada")

    def _postgres_layer_style_schemas(self, db) -> List[str]:
        schemas: List[str] = []
        query = QSqlQuery(db)
        if query.exec_(
            "SELECT n.nspname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = 'layer_styles' "
            "  AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END, n.nspname"
        ):
            while query.next():
                schema = str(query.value(0) or "").strip()
                if schema and schema not in schemas:
                    schemas.append(schema)
        return schemas or ["public"]

    def _postgres_layer_style_qml_from_schema(
        self,
        db,
        styles_schema: str,
        table_schema: str,
        table_name: str,
        geometry_column: str,
    ) -> str:
        query = QSqlQuery(db)
        table_ref = f"{self._pg_quote_identifier(styles_schema)}.layer_styles"
        if not query.prepare(
            "SELECT styleqml "
            f"FROM {table_ref} "
            "WHERE f_table_schema = :schema "
            "  AND f_table_name = :table_name "
            "  AND COALESCE(styleqml, '') <> '' "
            "  AND ("
            "    COALESCE(f_geometry_column, '') = :geometry_column "
            "    OR COALESCE(f_geometry_column, '') = ''"
            "  ) "
            "ORDER BY "
            "  CASE WHEN useasdefault THEN 0 ELSE 1 END, "
            "  CASE WHEN COALESCE(f_geometry_column, '') = :geometry_column THEN 0 ELSE 1 END, "
            "  update_time DESC NULLS LAST, "
            "  id DESC "
            "LIMIT 1"
        ):
            return ""
        query.bindValue(":schema", table_schema)
        query.bindValue(":table_name", table_name)
        query.bindValue(":geometry_column", geometry_column)
        if not query.exec_() or not query.next():
            return ""
        return str(query.value(0) or "").strip()

    def _provider_style_xml_candidates(self, provider_registry, provider_key: str, uri: str) -> List[str]:
        styles: List[str] = []
        for loader_name in ("loadStoredStyle", "loadStyle"):
            loader = getattr(provider_registry, loader_name, None)
            if not callable(loader):
                continue
            try:
                if loader_name == "loadStoredStyle":
                    style_result = loader(provider_key, uri, "", "")
                else:
                    style_result = loader(provider_key, uri, "")
            except Exception:
                style_result = ""
            self._append_style_xml(styles, style_result)

        list_styles = getattr(provider_registry, "listStyles", None)
        get_style_by_id = getattr(provider_registry, "getStyleById", None)
        if callable(list_styles) and callable(get_style_by_id):
            ids: List[str] = []
            names: List[str] = []
            descriptions: List[str] = []
            try:
                result = list_styles(provider_key, uri, ids, names, descriptions, "")
            except Exception:
                result = -1
            style_ids = ids
            if isinstance(result, tuple):
                for value in result:
                    if isinstance(value, (list, tuple)) and value:
                        style_ids = [str(item) for item in value]
                        break
            if style_ids:
                for style_id in style_ids:
                    try:
                        style_result = get_style_by_id(provider_key, uri, str(style_id), "")
                    except Exception:
                        style_result = ""
                    self._append_style_xml(styles, style_result)
        return styles

    def _append_style_xml(self, styles: List[str], style_result):
        if isinstance(style_result, tuple):
            values = style_result
        else:
            values = (style_result,)
        for value in values:
            if not isinstance(value, str):
                continue
            style_xml = value.strip()
            if "<qgis" in style_xml[:500].lower() and style_xml not in styles:
                styles.append(style_xml)

    def _apply_style_xml(self, layer: QgsVectorLayer, style_xml: str) -> bool:
        if not style_xml:
            return False
        try:
            layer_style = QgsMapLayerStyle(style_xml)
            if not layer_style.isValid() or not layer_style.writeToLayer(layer):
                return False
            try:
                layer.triggerRepaint()
            except Exception:
                pass
            return True
        except Exception:
            log_exception("falha opcional ignorada")
        return False

    def _style_result_is_success(self, result) -> bool:
        if isinstance(result, tuple) and len(result) >= 2:
            ok = bool(result[1])
            if ok:
                return True
        elif isinstance(result, bool):
            return bool(result)
        if isinstance(result, tuple) and result:
            for value in result:
                if isinstance(value, bool):
                    return value
        return False

    def _layer_error_text(self, layer: Optional[QgsVectorLayer]) -> str:
        if layer is None:
            return ""
        for attr_name in ("error", "lastError"):
            getter = getattr(layer, attr_name, None)
            if not callable(getter):
                continue
            try:
                error_obj = getter()
            except Exception:
                continue
            if error_obj is None:
                continue
            for text_attr in ("summary", "message", "text"):
                text_getter = getattr(error_obj, text_attr, None)
                if not callable(text_getter):
                    continue
                try:
                    text = str(text_getter() or "").strip()
                except Exception:
                    text = ""
                if text:
                    return text
        return ""

    def _materialize_integration_text_layer(
        self,
        df: pd.DataFrame,
        descriptor: Dict,
    ) -> Optional[QgsVectorLayer]:
        base_name = (descriptor.get("display_name") or "Tabela externa").strip()
        if not base_name:
            base_name = "Tabela externa"
        base_name = os.path.splitext(base_name)[0].strip() or base_name
        layer_name = self._unique_layer_name(base_name)

        temp_dir = os.path.join(tempfile.gettempdir(), "summarizer_imports")
        os.makedirs(temp_dir, exist_ok=True)
        csv_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{layer_name}.csv")
        try:
            export_df = df.copy()
            export_df.columns = [str(column) for column in export_df.columns]
            export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Falha ao salvar tabela temporária de integração: {exc}",
                "Summarizer",
                Qgis.Warning,
            )
            return None

        uri = (
            f"{QUrl.fromLocalFile(csv_path).toString()}?"
            "type=csv&detectTypes=yes&geomType=none&subsetIndex=no&watchFile=no"
        )
        iface_layer = None
        add_vector_layer = getattr(self.iface, "addVectorLayer", None)
        if callable(add_vector_layer):
            try:
                iface_layer = add_vector_layer(uri, layer_name, "delimitedtext")
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Falha ao adicionar tabela de texto via iface.addVectorLayer: {exc}",
                    "Summarizer",
                    Qgis.Warning,
                )
                iface_layer = None
        if iface_layer is not None and iface_layer.isValid():
            return iface_layer

        project_layer = QgsVectorLayer(uri, layer_name, "delimitedtext")
        if not project_layer or not project_layer.isValid():
            return None
        return self._add_layer_to_project(project_layer)

    def _add_layer_to_project(self, layer: Optional[QgsVectorLayer]) -> Optional[QgsVectorLayer]:
        if layer is None or not layer.isValid():
            return None
        project = QgsProject.instance()
        try:
            project.addMapLayer(layer)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Falha ao adicionar camada ao projeto: {exc}",
                "Summarizer",
                Qgis.Warning,
            )
            return None
        try:
            if layer.id() not in project.mapLayers():
                return None
        except Exception:
            return None
        return layer

    def _build_dataframe_summary(self, df: pd.DataFrame, descriptor: Dict) -> Dict:
        return _summary_build_dataframe_summary(df, descriptor)

    def _create_memory_table_from_dataframe(
        self,
        df: pd.DataFrame,
        descriptor: Dict,
    ) -> Optional[QgsVectorLayer]:
        return _summary_create_memory_table_from_dataframe(
            df,
            descriptor,
            unique_layer_name_fn=self._unique_layer_name,
            create_layer_from_dataframe_fn=self._create_layer_from_dataframe,
            add_layer_to_project_fn=self._add_layer_to_project,
        )

    def _map_series_to_variant(self, series: pd.Series) -> QVariant.Type:
        return _summary_map_series_to_variant(series)

    def load_layers(self):
        """QgsMapLayerComboBox já lida automaticamente com as camadas."""
        pass

    def _build_geometry_lookup(self, layer: QgsVectorLayer, id_series: pd.Series):
        return _summary_build_geometry_lookup(layer, id_series, log_exception)

    def _geometry_from_lookup(self, fid_value, geometry_lookup):
        return _summary_geometry_from_lookup(fid_value, geometry_lookup)

    def _create_layer_from_dataframe(
        self,
        df: pd.DataFrame,
        layer_name: str,
        with_geometry: bool,
        geometry_layer: Optional[QgsVectorLayer] = None,
    ):
        return _summary_create_layer_from_dataframe(
            df,
            layer_name,
            with_geometry,
            geometry_layer=geometry_layer,
            protected_columns=PROTECTED_COLUMNS_DEFAULT,
            log_exception=log_exception,
        )

    def _export_layer_to_gpkg(self, layer: QgsVectorLayer, path: str, layer_name: str):
        return _summary_export_layer_to_gpkg(layer, path, layer_name)

    def _variant_type_for_series(self, series: pd.Series) -> QVariant.Type:
        return _summary_variant_type_for_series(series)

    def _python_value(self, value):
        return _summary_python_value(value)

    def _format_comparison_values(self, values):
        return _summary_format_comparison_values(values, self._is_meaningful_value)

    def _sanitize_field_name(self, raw_name: str) -> str:
        return _summary_sanitize_field_name(raw_name)

    def _make_unique_field_name(self, existing_names, base_name: str) -> str:
        return _summary_make_unique_field_name(existing_names, base_name)

    def _unique_layer_name(self, base_name: str) -> str:
        existing_names = {
            layer.name() for layer in QgsProject.instance().mapLayers().values()
        }
        return _summary_unique_layer_name(base_name, existing_names)

    def _is_meaningful_value(self, value) -> bool:
        return _summary_is_meaningful_value(value)

    def _filter_empty_matches(self, matches):
        return _summary_filter_empty_matches(matches)

    def on_layer_changed(self):
        layer = self.ui.layer_combo.currentLayer()
        if layer and isinstance(layer, QgsVectorLayer):
            self._active_numeric_field = self._select_default_numeric_field(layer)
        else:
            self._active_numeric_field = None

        if self._active_numeric_field is None:
            self.current_summary_data = None
            self.show_summary_welcome()
            return

        if self.ui.auto_update_check.isChecked():
            QTimer.singleShot(300, self.generate_summary)

    def _select_default_numeric_field(self, layer: QgsVectorLayer) -> Optional[str]:
        if not layer:
            return None
        try:
            for field in layer.fields():
                try:
                    if field.isNumeric():
                        return field.name()
                except Exception:
                    log_exception("falha opcional ignorada")
                try:
                    if QVariant.Double == field.type() or QVariant.Int == field.type():
                        return field.name()
                except Exception:
                    log_exception("falha opcional ignorada")
        except Exception:
            log_exception("falha opcional ignorada")
        return None

    def generate_summary(self):
        layer = self.ui.layer_combo.currentLayer()
        if not layer or not isinstance(layer, QgsVectorLayer):
            return
        field_name = self._active_numeric_field or self._select_default_numeric_field(layer)
        if not field_name:
            QMessageBox.warning(
                self,
                "Resumo",
                "Nenhum campo numérico foi encontrado na camada selecionada.",
            )
            self.show_summary_welcome()
            return
        self._active_numeric_field = field_name
        group_field = None
        filter_field = None
        filter_value = None

        # Ensure pivot view becomes visible when gererating summaries
        self._set_results_view("pivot")
        if getattr(self, "summary_message_widget", None) is not None:
            self.summary_message_widget.clear()

        try:
            summary_data = self.calculate_advanced_summary(
            layer, field_name, group_field, filter_field, filter_value
        )
            self.current_summary_data = summary_data
            self.display_advanced_summary(summary_data)
            self.update_charts_preview(summary_data)
            self.prepare_export_tab_defaults(summary_data)
        except Exception as exc:
            QMessageBox.warning(self, "Erro", f"Erro ao gerar resumo: {exc}")

    def calculate_advanced_summary(
        self,
        layer,
        field_name,
        group_field=None,
        filter_field=None,
        filter_value=None,
    ):
        field_index = layer.fields().indexFromName(field_name)
        group_index = layer.fields().indexFromName(group_field) if group_field else -1

        request = QgsFeatureRequest()
        filter_description = "Nenhum"
        filter_expression = ""
        if filter_field and filter_value:
            filter_description = f'{filter_field} contém "{filter_value}"'
            filter_expression = f'"{filter_field}" ILIKE \'%{filter_value}%\''
            request.setFilterExpression(filter_expression)

        if field_index < 0:
            raise ValueError(f"Campo numérico '{field_name}' não encontrado na camada.")

        field_names = [f.name() for f in layer.fields()]
        raw_rows = []
        values = []
        grouped_values = {}

        for feature in layer.getFeatures(request):
            attrs = feature.attributes()
            raw_rows.append(
                {field_names[idx]: attrs[idx] for idx in range(len(field_names))}
            )

            value = attrs[field_index]
            if value in (None, ""):
                continue

            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue

            values.append(numeric_value)

            if group_index != -1:
                group_value = feature[group_index]
                grouped_values.setdefault(group_value, []).append(numeric_value)

        return _summary_calculate_advanced_summary(
            layer_name=layer.name(),
            layer_id=layer.id(),
            field_name=field_name,
            field_names=field_names,
            raw_rows=raw_rows,
            values=values,
            grouped_values=grouped_values,
            filter_description=filter_description,
            filter_expression=filter_expression,
            timestamp=datetime.now().isoformat(),
            total_features=layer.featureCount(),
        )

    def display_advanced_summary(self, summary_data):
        pivot = getattr(self, "pivot_widget", None)
        fallback_html = _summary_build_unavailable_html(
            _rt_runtime("Não foi possível exibir a tabela dinâmica para estes dados.")
        )
        if pivot is not None:
            try:
                if _summary_display_advanced_summary(
                    pivot,
                    summary_data,
                    set_results_view=self._set_results_view,
                ):
                    return
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Tabela dinamica",
                    f"Não foi possível atualizar a tabela dinâmica: {exc}",
                )
                _summary_show_results_message(
                    getattr(self, "summary_message_widget", None),
                    fallback_html,
                    set_results_view=self._set_results_view,
                )
                return

        _summary_show_results_message(
            getattr(self, "summary_message_widget", None),
            fallback_html,
            set_results_view=self._set_results_view,
        )
        return

    def _escape_html(self, text: str) -> str:
        return _summary_escape_html(text)

    def update_charts_preview(self, summary_data):
        if not hasattr(self.ui, "chart_preview_text"):
            return
        _summary_update_charts_preview(
            self.ui.chart_preview_text,
            summary_data,
            pivot_widget=getattr(self, "pivot_widget", None),
        )

    def _chart_preview_style_block(self) -> str:
        return _summary_chart_preview_style_block()

    def open_export_tab(self):
        try:
            self.ui.stackedWidget.setCurrentWidget(self.ui.pageResultados)
        except Exception:
            log_exception("falha opcional ignorada")
        if self.current_summary_data:
            self.prepare_export_tab_defaults(self.current_summary_data)
        else:
            QMessageBox.information(
                self, "Informação", "Gere um resumo antes de exportar."
            )

    def _current_export_format(self):
        return SummaryExportController(self).current_export_format()

    def _strip_existing_timestamp(self, base_path: str) -> str:
        return SummaryExportController(self).strip_existing_timestamp(base_path)

    def _normalize_filename_component(self, value: str) -> str:
        return SummaryExportController(self).normalize_filename_component(value)

    def _build_default_export_basename(self, summary_data):
        return SummaryExportController(self).build_default_export_basename(summary_data)

    def _set_export_path(self, path: str):
        SummaryExportController(self).set_export_path(path)

    def prepare_export_tab_defaults(self, summary_data):
        SummaryExportController(self).prepare_export_tab_defaults(summary_data)

    def on_export_format_changed(self):
        SummaryExportController(self).on_export_format_changed()

    def on_export_path_edited(self):
        SummaryExportController(self).on_export_path_edited()

    def _ask_layer_selection(self, layers):
        names = [layer.name() or "Camada sem nome" for layer in layers]
        dialog = SlimLayerSelectionDialog("Selecionar camadas", names, parent=self)
        dialog.set_focus_on_search()
        if dialog.exec_() != QDialog.Accepted:
            return None
        indices = dialog.selected_indices()
        return [layers[idx] for idx in indices]

    def export_all_vector_layers(self):
        project = QgsProject.instance()
        if project is None:
            QMessageBox.warning(
                self, "Aviso", "Projeto QGIS não encontrado. Tente novamente."
            )
            return

        vector_layers = [
            layer
            for layer in project.mapLayers().values()
            if isinstance(layer, QgsVectorLayer) and layer.isValid()
        ]

        if not vector_layers:
            QMessageBox.information(
                self,
                "Informação",
                "Nenhuma camada vetorial carregada para exportar.",
            )
            return

        selected_layers = self._ask_layer_selection(vector_layers)
        if selected_layers is None:
            return
        if not selected_layers:
            QMessageBox.information(
                self,
                "Informação",
                "Nenhuma camada selecionada para exportar.",
            )
            return

        target_dir = self._ask_layers_export_directory()
        if not target_dir:
            return

        exported_count = 0
        errors = []
        style_warnings = []
        transform_context = project.transformContext()

        for layer in selected_layers:
            layer_name = layer.name() or "camada"
            safe_name = self._normalize_filename_component(layer_name) or "camada"
            destination_path = os.path.join(target_dir, f"{safe_name}.gpkg")
            final_path = destination_path
            suffix = 1
            while os.path.exists(final_path):
                final_path = os.path.join(target_dir, f"{safe_name}_{suffix}.gpkg")
                suffix += 1

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name
            options.fileEncoding = layer.dataProvider().encoding()

            layer_style = QgsMapLayerStyle()
            try:
                style_captured = layer_style.readFromLayer(layer)
            except Exception:
                style_captured = False

            write_output = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                final_path,
                transform_context,
                options,
            )

            error_message = ""
            status = write_output
            if isinstance(write_output, tuple):
                if write_output:
                    status = write_output[0]
                if len(write_output) > 1:
                    if isinstance(write_output[1], str):
                        error_message = write_output[1]
                    elif write_output[1]:
                        error_message = str(write_output[1])
                if not error_message and len(write_output) > 2:
                    if isinstance(write_output[2], str):
                        error_message = write_output[2]
                    elif write_output[2]:
                        error_message = str(write_output[2])
            elif hasattr(write_output, "status"):
                status = write_output.status()
                try:
                    error_message = getattr(write_output, "errorMessage", lambda: "")()
                except Exception:
                    error_message = ""
            elif hasattr(write_output, "errorMessage"):
                try:
                    error_message = write_output.errorMessage()
                except Exception:
                    error_message = ""

            is_success = False
            if status == QgsVectorFileWriter.NoError:
                is_success = True
            elif hasattr(status, "value"):
                try:
                    is_success = status.value == QgsVectorFileWriter.NoError
                except Exception:
                    is_success = False
            else:
                try:
                    is_success = int(status) == int(QgsVectorFileWriter.NoError)
                except Exception:
                    is_success = False

            if is_success:
                exported_count += 1
                if style_captured:
                    try:
                        gpkg_uri = f"{final_path}|layername={layer_name}"
                        exported_layer = QgsVectorLayer(gpkg_uri, layer_name, "ogr")
                        if not exported_layer.isValid():
                            exported_layer = QgsVectorLayer(final_path, layer_name, "ogr")
                        if exported_layer.isValid():
                            if not layer_style.writeToLayer(exported_layer):
                                style_warnings.append(
                                    (layer_name, "Não foi possível aplicar o estilo.")
                                )
                            else:
                                try:
                                    save_result = exported_layer.saveStyleToDatabase(
                                        layer_name,
                                        "Estilo exportado automaticamente",
                                        True,
                                    )
                                    saved_ok = False
                                    save_error = ""
                                    if isinstance(save_result, tuple):
                                        if save_result:
                                            saved_ok = bool(save_result[0])
                                            if len(save_result) > 1:
                                                save_error = str(save_result[1])
                                    else:
                                        saved_ok = bool(save_result)
                                    if not saved_ok:
                                        message = (
                                            "Estilo aplicado, mas não pôde ser salvo no GeoPackage."
                                        )
                                        if save_error:
                                            message += f" Detalhes: {save_error}"
                                        style_warnings.append(
                                            (
                                                layer_name,
                                                message,
                                            )
                                        )
                                except Exception as exc:
                                    style_warnings.append(
                                        (
                                            layer_name,
                                            f"Falha ao salvar estilo no GeoPackage: {exc}",
                                        )
                                    )
                        else:
                            style_warnings.append(
                                (
                                    layer_name,
                                    "Camada exportada não pôde ser reaberta para aplicar o estilo.",
                                )
                            )
                        exported_layer = None
                    except Exception as exc:
                        style_warnings.append(
                            (layer_name, f"Falha ao transferir estilo: {exc}")
                        )
            else:
                errors.append((layer_name, error_message or "Erro desconhecido"))
                try:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                except Exception:
                    log_exception("falha opcional ignorada")

        summary_lines = [
            (
                f"{exported_count} de {len(selected_layers)} camada(s) "
                "exportada(s) para GeoPackage em:"
            ),
            target_dir,
        ]

        detail_lines = []
        if errors:
            detail_lines.append("Falhas de exportação:")
            detail_lines.extend(f"- {name}: {msg}" for name, msg in errors)
        if style_warnings:
            detail_lines.append("Avisos de estilo:")
            detail_lines.extend(f"- {name}: {msg}" for name, msg in style_warnings)

        if not errors and not style_warnings:
            QMessageBox.information(
                self,
                "Exportação concluída",
                "\n".join(summary_lines),
            )
        else:
            QMessageBox.warning(
                self,
                "Exportação concluída com avisos",
                "\n".join(summary_lines + [""] + detail_lines),
            )

    def _ask_layers_export_directory(self):
        settings = QSettings()
        last_dir = settings.value("Summarizer/export/gpkgDir", "")
        fallback_dir = self.export_manager.export_dir
        initial_dir = last_dir if last_dir and os.path.isdir(last_dir) else fallback_dir

        directory = QFileDialog.getExistingDirectory(
            self,
            _rt_runtime("Selecionar pasta de destino"),
            initial_dir,
        )

        if not directory:
            return None

        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Exportar camadas",
                f"Não foi possível criar a pasta selecionada:\n{directory}\nDetalhes: {exc}",
            )
            return None

        settings.setValue("Summarizer/export/gpkgDir", directory)
        return directory

    def choose_export_path(self):
        return SummaryExportController(self).choose_export_path()

    def export_results(self):
        SummaryExportController(self).export_results()

    def _materialize_dataframe_dialog(
        self,
        df: pd.DataFrame,
        base_name: str,
        can_use_geometry: bool,
        geometry_layer: Optional[QgsVectorLayer],
        settings_key: str,
        dialog_title: str,
        table_prefix: str,
        memory_prefix: str,
        export_prefix: str,
    ):
        _summary_materialize_dataframe_dialog(
            self,
            df,
            base_name,
            can_use_geometry,
            geometry_layer,
            settings_key,
            dialog_title,
            table_prefix,
            memory_prefix,
            export_prefix,
        )

    def show_dashboard(self):
        self._set_ribbon_visible(False)
        try:
            self.ui.stackedWidget.setCurrentWidget(self.ui.pageResultados)
        except Exception:
            log_exception("falha opcional ignorada")
        pivot_widget = getattr(self, "pivot_widget", None)
        if pivot_widget is None:
            QMessageBox.warning(
                self,
                "Dashboard",
                "A tabela dinâmica ainda não está disponível para este resumo.",
            )
            return

        try:
            raw_df = getattr(pivot_widget, "raw_df", None)
            metadata = pivot_widget.get_summary_metadata()
            config = pivot_widget.get_current_configuration()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Dashboard",
                f"Não foi possível obter os dados filtrados da tabela dinâmica: {exc}",
            )
            return

        dashboard_widget = self._ensure_dashboard_widget()
        if dashboard_widget is None:
            QMessageBox.warning(
                self,
                "Dashboard",
                "Não foi possível carregar o dashboard agora.",
            )
            return

        dashboard_widget.show()
        dashboard_widget.raise_()

        def _populate_dashboard():
            try:
                if hasattr(pivot_widget, "get_current_pivot_result"):
                    pivot_result = pivot_widget.get_current_pivot_result()
                else:
                    pivot_result = None
                if pivot_result is not None and hasattr(
                    dashboard_widget, "set_pivot_result"
                ):
                    dashboard_widget.set_pivot_result(pivot_result)
                elif raw_df is not None and not getattr(raw_df, "empty", True):
                    dashboard_widget.set_pivot_data(raw_df, metadata, config)
                else:
                    pivot_df = pivot_widget.get_visible_pivot_dataframe()
                    dashboard_widget.set_pivot_data(pivot_df, metadata, config)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Dashboard",
                    f"NÃ£o foi possÃ­vel obter os dados filtrados da tabela dinÃ¢mica: {exc}",
                )

        QTimer.singleShot(0, _populate_dashboard)

    def show_about_dialog(self):
        dialog = SlimDialogBase(self, geometry_key="Summarizer/dialogs/about")
        dialog.setWindowTitle(_rt_runtime("Sobre"))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel(_rt_runtime("Summarizer"), dialog)
        title.setProperty("sublabel", True)
        layout.addWidget(title)

        body = QLabel(
            _rt_runtime(
                "Resumo e exportação de camadas do QGIS com visual focado em "
                "análise e relatórios."
            ),
            dialog,
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setObjectName("SlimPrimaryButton")
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        _apply_i18n_widgets(dialog)
        dialog.exec_()


def _vector_layer_to_dataframe(layer) -> Optional[pd.DataFrame]:
    if layer is None or not layer.isValid():
        return None
    field_names = [field.name() for field in layer.fields()]
    rows = []
    for feature in layer.getFeatures():
        row = {field_names[idx]: feature.attributes()[idx] for idx in range(len(field_names))}
        rows.append(row)
    return pd.DataFrame(rows)


class GetDataDialog(QDialog):
    """Diálogo compacto de 'Obter Dados' focado em relatórios."""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.setProperty("walkerDialog", True)
        self.setWindowTitle(_rt_runtime("Obter Dados"))
        self.resize(680, 420)
        self._datasets: list = []
        self._build_ui()
        install_walker_modal_chrome(self)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title = QLabel(_rt_runtime("Obter Dados"), self)
        title.setObjectName("WalkerDialogTitle")
        header.addWidget(title, 1)
        add_walker_close_button(header, self)
        layout.addLayout(header)

        info = QLabel(
            _rt_runtime("Escolha a fonte de dados disponível para importar.")
            + _rt_runtime(
                "As tabelas selecionadas serão adicionadas ao modelo sem abrir "
                "camadas no mapa."
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.source_combo = QComboBox(self)
        self.source_combo.addItem(_rt_runtime("PostgreSQL / SQL"), "database")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_combo)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        # Página DB
        db_page = QFrame(self)
        db_layout = QVBoxLayout(db_page)
        db_layout.setContentsMargins(0, 0, 0, 0)
        db_layout.setSpacing(8)
        db_layout.addWidget(QLabel(_rt_runtime("Usar conexões salvas ou cadastrar nova.")))
        self.db_import_btn = QPushButton(_rt_runtime("Abrir importador de banco..."))
        self.db_import_btn.setCursor(Qt.PointingHandCursor)
        db_layout.addWidget(self.db_import_btn, 0, Qt.AlignLeft)
        self.db_status = QLabel("")
        self.db_status.setProperty("role", "helper")
        db_layout.addWidget(self.db_status)
        db_layout.addStretch(1)
        self.db_import_btn.clicked.connect(self._open_db_dialog)
        self.stack.addWidget(db_page)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        apply_walker_buttons(
            primary=[buttons.button(QDialogButtonBox.Ok), self.db_import_btn],
            secondary=[buttons.button(QDialogButtonBox.Cancel)],
        )
        layout.addWidget(buttons)
        self.setStyleSheet(WALKER_DIALOG_STYLE)

        self._on_source_changed(0)
        _apply_i18n_widgets(self)

    # ------------------------------------------------------------------ Actions
    def _on_source_changed(self, index: int):
        self.stack.setCurrentIndex(index)

    def _open_db_dialog(self):
        from .integration_panel import DatabaseImportDialog

        try:
            saved = connection_registry.saved_connections()
        except Exception:
            saved = []
        dialog = DatabaseImportDialog(self, saved)
        if dialog.exec_() != QDialog.Accepted:
            return
        df, metadata, connection_meta, session_connection = dialog.result()
        if df is None or df.empty:
            QMessageBox.information(
                self,
                _rt_runtime("Banco"),
                _rt_runtime("Nenhuma tabela carregada."),
            )
            return
        self._datasets.append((df, metadata or {"connector": "PostgreSQL"}))
        self.db_status.setText(
            _rt_runtime(
                "Tabela carregada: {display_name}",
                display_name=metadata.get("display_name"),
            )
        )
        # Replica conexão no Navegador, se houver
        if connection_meta:
            try:
                connection_registry.replace_saved_connections([connection_meta], persist=True)
            except Exception:
                log_exception("falha opcional ignorada")
        if session_connection:
            try:
                connection_registry.register_runtime_connection(session_connection)
            except Exception:
                log_exception("falha opcional ignorada")

    # ------------------------------------------------------------------ API
    def results(self) -> List:
        return list(self._datasets)
