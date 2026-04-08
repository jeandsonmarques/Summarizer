from functools import partial
import json
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pandas.api import types as ptypes
from qgis.PyQt.QtCore import QEvent, QItemSelection, QItemSelectionModel, QMimeData, QRegExp, QSettings, QSize, QTimer, Qt, QSortFilterProxyModel, QVariant
from qgis.PyQt.QtGui import QFont, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from qgis.core import (
    QgsFields,
    QgsField,
    QgsFeature,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis,
)

from .palette import TYPOGRAPHY
from .report_view.pivot import (
    PivotEngine,
    PivotExportService,
    PivotFieldSpec,
    PivotRequest,
    PivotSelectionBridge,
    PivotValidationError,
)


class _PivotFilterProxy(QSortFilterProxyModel):
    """Proxy that supports global search plus per-column filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._global_regexp = QRegExp()
        self._column_filters: Dict[int, QRegExp] = {}
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if model is None:
            return True
        column_count = model.columnCount()

        if not self._global_regexp.isEmpty():
            matched = False
            for col in range(column_count):
                idx = model.index(source_row, col, source_parent)
                value = str(model.data(idx) or "")
                if self._global_regexp.indexIn(value) != -1:
                    matched = True
                    break
            if not matched:
                return False

        for col, rx in self._column_filters.items():
            if rx.isEmpty():
                continue
            if col >= column_count:
                continue
            idx = model.index(source_row, col, source_parent)
            value = str(model.data(idx) or "")
            if rx.indexIn(value) == -1:
                return False
        return True

    def set_global_filter(self, text: str):
        self._global_regexp = QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString)
        self.invalidateFilter()

    def set_column_filter(self, column: int, text: str):
        if not text:
            self._column_filters.pop(column, None)
        else:
            self._column_filters[column] = QRegExp(
                text, Qt.CaseInsensitive, QRegExp.FixedString
            )
        self.invalidateFilter()


_PIVOT_FIELD_MIME = "application/x-powerbisummarizer-pivot-field"
_SIDEBAR_COLLAPSED_KEY = "PowerBISummarizer/pivot/sidebarCollapsed"
_SIDEBAR_WIDTH_KEY = "PowerBISummarizer/pivot/sidebarWidth"


class _PivotFieldSourceListWidget(QListWidget):
    def __init__(self, owner=None, parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def supportedDropActions(self):
        return Qt.CopyAction

    def mimeTypes(self):
        return [_PIVOT_FIELD_MIME]

    def mimeData(self, items):
        mime = QMimeData()
        payload = []
        for item in items or []:
            spec_key = item.data(Qt.UserRole)
            if spec_key:
                payload.append({"spec_key": spec_key, "text": item.text()})
        mime.setData(_PIVOT_FIELD_MIME, json.dumps(payload).encode("utf-8"))
        return mime

    def contextMenuEvent(self, event):
        if self._owner is None:
            super().contextMenuEvent(event)
            return
        item = self.itemAt(event.pos()) or self.currentItem()
        if item is None:
            return
        spec_key = item.data(Qt.UserRole)
        if not spec_key or spec_key == "__placeholder__":
            return
        spec = self._owner._field_spec_from_key(spec_key)
        if spec is None:
            return
        menu = QMenu(self)
        add_last = menu.addAction(f"Adicionar em {self._owner._area_label(self._owner._last_active_area)}")
        add_rows = menu.addAction("Adicionar em Linhas")
        add_columns = menu.addAction("Adicionar em Colunas")
        action = menu.exec_(event.globalPos())
        if action is None:
            return
        if action == add_last:
            self._owner._add_field_to_area(self._owner._last_active_area, spec)
        elif action == add_rows:
            self._owner._add_field_to_area("row", spec)
        elif action == add_columns:
            self._owner._add_field_to_area("column", spec)


class _PivotDropListWidget(QListWidget):
    def __init__(self, owner, area_name: str, allow_multiple: bool = True, parent=None):
        super().__init__(parent)
        self._owner = owner
        self._area_name = area_name
        self._allow_multiple = allow_multiple
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_PIVOT_FIELD_MIME) or event.source() is self:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(_PIVOT_FIELD_MIME) or event.source() is self:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.source() is self:
            super().dropEvent(event)
            if self._owner is not None:
                self._owner._set_last_active_area(self._area_name)
                self._owner._sync_area_placeholder(self._area_name)
                self._owner._maybe_refresh()
            return

        if not event.mimeData().hasFormat(_PIVOT_FIELD_MIME):
            super().dropEvent(event)
            return

        try:
            payload = json.loads(bytes(event.mimeData().data(_PIVOT_FIELD_MIME)).decode("utf-8"))
        except Exception:
            payload = []

        added = False
        for item in payload or []:
            spec = self._owner._field_spec_from_key(item.get("spec_key"))
            if spec is None:
                continue
            added = self._owner._add_field_to_area(self._area_name, spec, auto_refresh=False) or added
            if not self._allow_multiple:
                break

        if added:
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            if self._owner is not None:
                self._owner._set_last_active_area(self._area_name)
                self._owner._sync_area_placeholder(self._area_name)
                self._owner._maybe_refresh()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.currentRow() >= 0 and self._owner is not None:
                self._owner._remove_selected_area_field(self._area_name)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        super().focusInEvent(event)

    def contextMenuEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        menu = QMenu(self)
        remove_action = menu.addAction("Remover")
        up_action = menu.addAction("Mover para cima")
        down_action = menu.addAction("Mover para baixo")
        menu.addSeparator()
        clear_action = menu.addAction("Limpar área")
        action = menu.exec_(event.globalPos())
        if action == remove_action and self._owner is not None:
            self._owner._remove_selected_area_field(self._area_name)
        elif action == up_action and self._owner is not None:
            self._owner._move_selected_area_field(self._area_name, -1)
        elif action == down_action and self._owner is not None:
            self._owner._move_selected_area_field(self._area_name, 1)
        elif action == clear_action and self._owner is not None:
            self._owner._clear_area(self._area_name)
            self._owner._maybe_refresh()


class PivotTableWidget(QWidget):
    """Excel-inspired compact pivot table with column filters and field list."""

    SUPPORTED_AGGREGATORS = [
        ("Soma", "sum"),
        ("Media", "average"),
        ("Contagem", "count"),
        ("Maximo", "max"),
        ("Minimo", "min"),
        ("Mediana", "median"),
        ("Valores unicos", "unique"),
        ("Variancia", "variance"),
        ("Desvio padrao", "stddev"),
    ]

    EXPORT_FILTERS = "CSV (*.csv);;Excel (*.xlsx);;GeoPackage (*.gpkg)"

    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)
        self.iface = iface
        self.raw_df: pd.DataFrame = pd.DataFrame()
        self.filtered_df: pd.DataFrame = pd.DataFrame()
        self.pivot_df: pd.DataFrame = pd.DataFrame()
        self.column_dtypes: Dict[str, str] = {}
        self.numeric_candidates: List[str] = []
        self.column_filter_editors: List[QLineEdit] = []
        self._block_updates = False
        self._current_metadata: Dict[str, str] = {}
        self.toolbar_layout: Optional[QHBoxLayout] = None
        self._external_auto_checkbox: Optional[QCheckBox] = None
        self._external_dashboard_button: Optional[QPushButton] = None
        self.auto_update_check: Optional[QCheckBox] = None
        self._current_summary_data: Dict[str, Any] = {}
        self._current_layer = None
        self._current_pivot_request = None
        self._current_pivot_result = None
        self._display_row_keys: List[tuple] = []
        self._display_column_keys: List[tuple] = []
        self._pivot_data_column_offset = 0
        self._row_header_depth = 1
        self._last_active_area = "row"
        self._sidebar_collapsed = False
        self._sidebar_last_width = 340
        self._field_specs_by_key: Dict[str, PivotFieldSpec] = {}
        self._saved_configurations: Dict[str, Dict[str, Any]] = {}
        self.pivot_engine = PivotEngine(iface=iface, logger=QgsMessageLog)
        self.pivot_selection_bridge = PivotSelectionBridge(iface)
        self.pivot_export_service = PivotExportService()

        self._build_ui()
        self._configure_compact_sizing()
        self._apply_styles()
        self._apply_theming_tokens()
        self._load_sidebar_state()
        self._apply_sidebar_visibility(not self._sidebar_collapsed, persist=False)

    def minimumSizeHint(self):
        return QSize(720, 360)

    def sizeHint(self):
        return QSize(1120, 560)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)
        root.setSizeConstraint(QLayout.SetNoConstraint)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        root.addWidget(self.main_splitter)

        # -- Left (table) -------------------------------------------------
        self.table_container = QWidget()
        self.table_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_container.setMinimumSize(0, 0)
        left_layout = QVBoxLayout(self.table_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.toolbar_layout = toolbar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pesquisar em todas as colunas...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self.search_input, stretch=1)

        self.clear_filters_btn = QPushButton("Limpar filtros")
        self.clear_filters_btn.setFixedHeight(26)
        self.clear_filters_btn.setMinimumWidth(120)
        self.clear_filters_btn.setProperty("variant", "secondary")
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        toolbar.addWidget(self.clear_filters_btn)

        self.export_btn = QPushButton("Exportar")
        self.export_btn.setFixedHeight(26)
        self.export_btn.clicked.connect(self._export_pivot_table)
        toolbar.addWidget(self.export_btn)

        self.sidebar_toggle_btn = QPushButton("Ocultar construtor")
        self.sidebar_toggle_btn.setFixedHeight(26)
        self.sidebar_toggle_btn.setCheckable(True)
        self.sidebar_toggle_btn.setProperty("variant", "secondary")
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        toolbar.addWidget(self.sidebar_toggle_btn)

        left_layout.addLayout(toolbar)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("metaLabel")
        self.meta_label.setProperty("role", "helper")
        self.meta_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout.addWidget(self.meta_label)

        self.table_model = QStandardItemModel(self)
        self.proxy_model = _PivotFilterProxy(self)
        self.proxy_model.setSourceModel(self.table_model)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_view.setMinimumSize(0, 0)
        self.table_view.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_view.clicked.connect(self._handle_table_cell_clicked)
        self.table_view.installEventFilter(self)
        self.table_view.viewport().installEventFilter(self)
        self.table_view.verticalHeader().sectionClicked.connect(self._handle_row_header_clicked)
        self.table_view.horizontalHeader().sectionClicked.connect(self._handle_column_header_clicked)
        left_layout.addWidget(self.table_view, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setProperty("role", "helper")
        left_layout.addWidget(self.status_label)

        self.selection_summary_bar = QFrame()
        self.selection_summary_bar.setObjectName("selectionSummaryBar")
        selection_layout = QHBoxLayout(self.selection_summary_bar)
        selection_layout.setContentsMargins(10, 6, 10, 6)
        selection_layout.setSpacing(8)
        self.selection_summary_label = QLabel("Selecione celulas para ver soma e contagem.")
        self.selection_summary_label.setObjectName("selectionSummaryLabel")
        self.selection_summary_label.setProperty("role", "helper")
        selection_layout.addWidget(self.selection_summary_label)
        selection_layout.addStretch(1)
        left_layout.addWidget(self.selection_summary_bar)

        self.main_splitter.addWidget(self.table_container)

        # -- Right (field list) ------------------------------------------
        self.side_panel = QFrame()
        self.side_panel.setObjectName("fieldPanel")
        self.side_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.side_panel.setMinimumSize(0, 0)
        right_layout = QVBoxLayout(self.side_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        title = QLabel("Tabela Dinamica")
        title.setObjectName("fieldPanelTitle")
        right_layout.addWidget(title)

        self.side_hint = QLabel("Duplo clique ou arraste para montar a tabela.")
        self.side_hint.setProperty("role", "helper")
        self.side_hint.setObjectName("fieldPanelHint")
        right_layout.addWidget(self.side_hint)

        source_card = QFrame()
        source_card.setObjectName("pivotSideCard")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(10, 10, 10, 10)
        source_layout.setSpacing(6)

        source_title = QLabel("Campos da Tabela Dinamica")
        source_title.setObjectName("pivotSideSectionTitle")
        source_layout.addWidget(source_title)

        self.field_search = QLineEdit()
        self.field_search.setPlaceholderText("Pesquisar campos...")
        self.field_search.textChanged.connect(self._filter_field_list)
        source_layout.addWidget(self.field_search)

        self.fields_list = _PivotFieldSourceListWidget(owner=self)
        self.fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.fields_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fields_list.itemDoubleClicked.connect(self._handle_field_double_click)
        self.fields_list.setFixedHeight(176)
        source_layout.addWidget(self.fields_list)
        right_layout.addWidget(source_card)

        self.filter_field_combo = QComboBox()
        self.filter_field_combo.hide()
        self.row_field_combo = QComboBox()
        self.row_field_combo.hide()
        self.column_field_combo = QComboBox()
        self.column_field_combo.hide()
        self.filter_fields_list = _PivotDropListWidget(self, "filter", allow_multiple=False)
        self.filter_fields_list.hide()

        areas_card = QFrame()
        areas_card.setObjectName("pivotSideCard")
        areas_layout = QVBoxLayout(areas_card)
        areas_layout.setContentsMargins(10, 10, 10, 10)
        areas_layout.setSpacing(8)

        areas_title = QLabel("Montagem da Pivot")
        areas_title.setObjectName("pivotSideSectionTitle")
        areas_layout.addWidget(areas_title)

        areas_hint = QLabel("Duplo clique ou arraste para montar a tabela.")
        areas_hint.setObjectName("fieldPanelHint")
        areas_hint.setProperty("role", "helper")
        areas_layout.addWidget(areas_hint)

        self.row_fields_list = _PivotDropListWidget(self, "row", allow_multiple=True)
        self.row_fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.row_fields_list.setFixedHeight(110)

        self.column_fields_list = _PivotDropListWidget(self, "column", allow_multiple=True)
        self.column_fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.column_fields_list.setFixedHeight(110)

        axes_row = QHBoxLayout()
        axes_row.setSpacing(8)

        self.row_area_card = QFrame()
        self.row_area_card.setObjectName("pivotAreaCard")
        row_layout = QVBoxLayout(self.row_area_card)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(6)
        self.row_area_title = QLabel("Linhas")
        self.row_area_title.setObjectName("pivotAreaTitle")
        row_title = self.row_area_title
        row_layout.addWidget(row_title)
        row_layout.addWidget(self.row_fields_list)
        axes_row.addWidget(self.row_area_card, 1)

        self.column_area_card = QFrame()
        self.column_area_card.setObjectName("pivotAreaCard")
        col_layout = QVBoxLayout(self.column_area_card)
        col_layout.setContentsMargins(8, 8, 8, 8)
        col_layout.setSpacing(6)
        self.column_area_title = QLabel("Colunas")
        self.column_area_title.setObjectName("pivotAreaTitle")
        col_title = self.column_area_title
        col_layout.addWidget(col_title)
        col_layout.addWidget(self.column_fields_list)
        axes_row.addWidget(self.column_area_card, 1)

        areas_layout.addLayout(axes_row)

        self.agg_combo = QComboBox()
        self.agg_combo.setObjectName("operationCombo")
        for label, func in self.SUPPORTED_AGGREGATORS:
            self.agg_combo.addItem(label, func)
        self.agg_combo.setCurrentIndex(self.agg_combo.findData("count"))
        self.agg_combo.currentIndexChanged.connect(self._on_operation_changed)
        areas_layout.addWidget(QLabel("Operacao"))
        areas_layout.addWidget(self.agg_combo)

        self.advanced_group = QGroupBox("Avançado")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.advanced_group.toggled.connect(self._on_advanced_toggled)
        self.advanced_group.setFixedHeight(80)
        advanced_layout = QVBoxLayout(self.advanced_group)
        advanced_layout.setContentsMargins(8, 6, 8, 6)
        advanced_layout.setSpacing(6)
        advanced_help = QLabel("Use so se precisar de metricas explicitas.")
        advanced_help.setProperty("role", "helper")
        advanced_layout.addWidget(advanced_help)

        self.advanced_value_label = QLabel("Campo de valor")
        self.value_field_combo = QComboBox()
        self.value_field_combo.currentIndexChanged.connect(self._maybe_refresh)
        advanced_layout.addWidget(self.advanced_value_label)
        advanced_layout.addWidget(self.value_field_combo)
        self.advanced_value_label.setVisible(False)
        self.value_field_combo.setVisible(False)
        areas_layout.addWidget(self.advanced_group)

        self.only_selected_check = QCheckBox("Apenas selecionadas")
        self.only_selected_check.stateChanged.connect(self._maybe_refresh)
        self.include_nulls_check = QCheckBox("Incluir nulos")
        self.include_nulls_check.stateChanged.connect(self._maybe_refresh)
        flags_row = QHBoxLayout()
        flags_row.addWidget(self.only_selected_check)
        flags_row.addWidget(self.include_nulls_check)
        flags_row.addStretch(1)
        areas_layout.addLayout(flags_row)

        self.apply_btn = QPushButton("Atualizar")
        self.apply_btn.setFixedHeight(26)
        self.apply_btn.clicked.connect(self.refresh)
        areas_layout.addWidget(self.apply_btn)

        right_layout.addWidget(areas_card)
        right_layout.addStretch()

        self.main_splitter.addWidget(self.side_panel)
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([840, 340])
        self.side_panel.setMaximumWidth(420)
        areas_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _configure_compact_sizing(self):
        for widget in (
            self,
            self.table_view,
            self.fields_list,
            self.filter_fields_list,
            self.row_fields_list,
            self.column_fields_list,
            self.advanced_group,
        ):
            try:
                widget.setMinimumHeight(0)
            except Exception:
                pass

    def _load_sidebar_state(self):
        settings = QSettings()
        collapsed = settings.value(_SIDEBAR_COLLAPSED_KEY, False, type=bool)
        width = settings.value(_SIDEBAR_WIDTH_KEY, 340, type=int)
        try:
            width = int(width)
        except Exception:
            width = 340
        self._sidebar_collapsed = bool(collapsed)
        self._sidebar_last_width = max(260, width)

    def _persist_sidebar_state(self):
        settings = QSettings()
        settings.setValue(_SIDEBAR_COLLAPSED_KEY, self._sidebar_collapsed)
        if not self._sidebar_collapsed and self.main_splitter is not None:
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 0:
                self._sidebar_last_width = max(260, sizes[1])
        settings.setValue(_SIDEBAR_WIDTH_KEY, int(self._sidebar_last_width))

    def _toggle_sidebar(self, checked: bool):
        self._apply_sidebar_visibility(not checked, persist=True)

    def _apply_sidebar_visibility(self, visible: bool, persist: bool = True):
        self._sidebar_collapsed = not visible
        if hasattr(self, "sidebar_toggle_btn"):
            self.sidebar_toggle_btn.blockSignals(True)
            self.sidebar_toggle_btn.setChecked(not visible)
            self.sidebar_toggle_btn.setText("Mostrar construtor" if not visible else "Ocultar construtor")
            self.sidebar_toggle_btn.blockSignals(False)

        if hasattr(self, "side_panel"):
            self.side_panel.setVisible(visible)
            self.side_panel.setMaximumWidth(420 if visible else 0)

        if hasattr(self, "main_splitter"):
            if visible:
                sidebar_width = max(260, int(self._sidebar_last_width or 340))
                self.main_splitter.setSizes([max(1, self.main_splitter.width() - sidebar_width), sidebar_width])
                self.main_splitter.widget(1).show()
            else:
                sizes = self.main_splitter.sizes()
                if len(sizes) >= 2 and sizes[1] > 0:
                    self._sidebar_last_width = max(260, sizes[1])
                self.main_splitter.setSizes([max(1, self.main_splitter.width()), 0])
                self.main_splitter.widget(1).hide()

        if persist:
            self._persist_sidebar_state()
        self._refresh_active_area_styles()

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
                font-size: 10pt;
            }
            QLabel#metaLabel {
                color: #5a6a85;
            }
            QLabel#statusLabel {
                color: #5a6a85;
            }
            QLineEdit {
                padding: 4px 6px;
                border: 1px solid #c7cfe2;
                border-radius: 0px;
            }
            QPushButton {
                background-color: #153C8A;
                color: white;
                padding: 4px 10px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #1f4ea8;
            }
            QPushButton:disabled {
                background-color: #ccd6ee;
                color: #7c8aad;
            }
            QFrame#fieldPanel {
                border: 1px solid #d7e1f2;
                border-radius: 10px;
                background-color: #f7f9fc;
            }
            QListWidget {
                border: 1px solid #d7e1f2;
                border-radius: 8px;
                background-color: #ffffff;
                min-height: 44px;
            }
            QListWidget::item {
                padding: 4px 6px;
            }
            QListWidget::item:selected {
                background-color: #dce8ff;
                color: #153C8A;
            }
            QGroupBox {
                border: 1px solid #d7e1f2;
                margin-top: 8px;
                padding-top: 10px;
                border-radius: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #1d2a4b;
                font-weight: 600;
            }
            QFrame#pivotSideCard {
                border: 1px solid #d7e1f2;
                border-radius: 10px;
                background-color: #ffffff;
            }
            QFrame#selectionSummaryBar {
                border-top: 1px solid #d7e1f2;
                background-color: #fbfcff;
            }
            QFrame#pivotAreaCard[activeArea="true"] {
                border: 1px solid #153C8A;
                background-color: #f3f7ff;
            }
            QLabel#fieldPanelTitle {
                font-size: 11pt;
                font-weight: 700;
                color: #1d2a4b;
            }
            QLabel#pivotSideSectionTitle {
                font-size: 10pt;
                font-weight: 700;
                color: #1d2a4b;
            }
            QLabel#pivotAreaTitle[activeArea="true"] {
                color: #153C8A;
                font-weight: 700;
            }
            QLabel#fieldPanelHint {
                color: #5f6f8d;
                font-size: 9pt;
            }
            QLabel#selectionSummaryLabel {
                color: #394a67;
                font-size: 9pt;
            }
            """
        )

    # ------------------------------------------------------------------ Data intake
    def set_summary_data(self, summary_data: Dict):
        self._block_updates = True
        try:
            previous_key = self._configuration_key_from_metadata(self._current_metadata)
            if previous_key:
                self._store_current_configuration(previous_key)

            metadata = summary_data.get("metadata", {}) or {}
            raw = summary_data.get("raw_data") or {}
            columns = raw.get("columns") or []
            rows = raw.get("rows") or []

            df = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame(rows)
            self.raw_df = df
            self.filtered_df = df
            self.column_dtypes = {col: str(df[col].dtype) for col in df.columns}
            self.numeric_candidates = self._detect_numeric_candidates(df)
            self._current_metadata = metadata
            self._current_summary_data = dict(summary_data or {})
            self._current_layer = self._resolve_current_layer()
            self._current_pivot_request = None
            self._current_pivot_result = None

            self._update_meta_label(metadata, summary_data.get("filter_description"))
            self._populate_field_panel(df)
            self._restore_saved_configuration_for_metadata(metadata)
        finally:
            self._block_updates = False

        self.refresh()

    def _update_meta_label(self, metadata: Dict, filter_desc: Optional[str]):
        layer = metadata.get("layer_name", "-")
        field = metadata.get("field_name", "-")
        total_feat = metadata.get("total_features")
        filter_text = filter_desc or "Nenhum"
        if total_feat is None:
            message = f"Camada: {layer} | Campo numerico: {field} | Filtro: {filter_text}"
        else:
            message = (
                f"Camada: {layer} | Campo numerico: {field} | "
                f"Feicoes carregadas: {total_feat:,} | Filtro: {filter_text}"
            )
        self.meta_label.setText(message)

    def _populate_field_panel(self, df: pd.DataFrame):
        self.fields_list.clear()
        self._field_specs_by_key = {}
        self.filter_fields_list.clear()
        self.row_fields_list.clear()
        self.column_fields_list.clear()
        self._sync_area_placeholder()

        combos = [
            self.filter_field_combo,
            self.column_field_combo,
            self.row_field_combo,
            self.value_field_combo,
        ]
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(Nenhum)", None)
            combo.blockSignals(False)

        layer = self._current_layer
        for column in df.columns:
            field_spec = self._build_attribute_field_spec(column, layer, df)
            spec_key = self._register_field_spec(field_spec)
            item = QListWidgetItem(column)
            item.setData(Qt.UserRole, spec_key)
            item.setData(Qt.UserRole + 1, bool(field_spec.data_type == "numeric"))
            item.setData(Qt.UserRole + 2, column)
            self.fields_list.addItem(item)
            self.filter_field_combo.addItem(column, spec_key)
            self.column_field_combo.addItem(column, spec_key)
            self.row_field_combo.addItem(column, spec_key)
            self.value_field_combo.addItem(column, spec_key)

        if layer is not None:
            geometry_specs = self._geometry_field_specs_for_layer(layer)
            for field_spec in geometry_specs:
                spec_key = self._register_field_spec(field_spec)
                self.value_field_combo.addItem(field_spec.display_name, spec_key)

        # Default selections
        if df.columns.size:
            # Default row: first non-numeric column, else first column
            row_candidate = next(
                (col for col in df.columns if not self._is_numeric_column(df[col])),
                df.columns[0],
            )
            idx = self.row_field_combo.findText(row_candidate)
            if idx != -1:
                self.row_field_combo.setCurrentIndex(idx)
                self._add_selected_field_to_area("row", auto_refresh=False)
                self._set_last_active_area("row")

        if self.numeric_candidates:
            value_candidate = next(
                (candidate for candidate in self.numeric_candidates if not self._is_identifier_like_field(candidate)),
                None,
            )
            if value_candidate is not None:
                idx = self.value_field_combo.findText(value_candidate)
                if idx != -1:
                    self.value_field_combo.setCurrentIndex(idx)

    def _configuration_key_from_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        metadata = dict(metadata or {})
        layer_id = str(metadata.get("layer_id") or "").strip()
        if layer_id:
            return f"layer:{layer_id}"
        layer_name = str(metadata.get("layer_name") or "").strip()
        if layer_name:
            return f"name:{layer_name}"
        return ""

    def _store_current_configuration(self, key: str):
        if not key or self.raw_df is None or self.raw_df.empty:
            return
        try:
            self._saved_configurations[key] = dict(self.get_current_configuration() or {})
        except Exception:
            return

    def _restore_saved_configuration_for_metadata(self, metadata: Optional[Dict[str, Any]]):
        key = self._configuration_key_from_metadata(metadata)
        if not key:
            return
        config = dict(self._saved_configurations.get(key) or {})
        if not config:
            return
        self._apply_saved_configuration(config)

    def _apply_saved_configuration(self, config: Dict[str, Any]):
        if not config:
            return

        self.filter_fields_list.clear()
        self.row_fields_list.clear()
        self.column_fields_list.clear()
        self._sync_area_placeholder()

        aggregation = str(config.get("aggregation") or "count")
        for index in range(self.agg_combo.count()):
            if str(self.agg_combo.itemData(index) or "") == aggregation:
                self.agg_combo.setCurrentIndex(index)
                break

        row_fields = list(config.get("row_fields") or [])
        column_fields = list(config.get("column_fields") or [])
        filter_fields = list(config.get("filter_fields") or [])

        for field_name in row_fields:
            spec = self._field_spec_from_field_name(field_name)
            if spec is not None:
                self._add_field_to_area("row", spec, auto_refresh=False)

        for field_name in column_fields:
            spec = self._field_spec_from_field_name(field_name)
            if spec is not None:
                self._add_field_to_area("column", spec, auto_refresh=False)

        for field_name in filter_fields:
            spec = self._field_spec_from_field_name(field_name)
            if spec is not None:
                self._add_field_to_area("filter", spec, auto_refresh=False)

        value_field = str(config.get("value_field") or "").strip()
        if value_field:
            spec = self._field_spec_from_field_name(value_field)
            if spec is not None:
                spec_key = self._register_field_spec(spec)
                idx = self.value_field_combo.findData(spec_key)
                if idx != -1:
                    self.value_field_combo.setCurrentIndex(idx)

        self.only_selected_check.setChecked(bool(config.get("only_selected")))
        self.include_nulls_check.setChecked(bool(config.get("include_nulls")))
        self.advanced_group.setChecked(aggregation != "count")
        self._on_advanced_toggled(aggregation != "count")
        self._sync_area_placeholder()

        if row_fields:
            self._set_last_active_area("row")
        elif column_fields:
            self._set_last_active_area("column")

    def _field_spec_from_field_name(self, field_name: Optional[str]) -> Optional[PivotFieldSpec]:
        target = str(field_name or "").strip()
        if not target:
            return None
        for spec in self._field_specs_by_key.values():
            if spec.field_name == target:
                return spec
        return None

    # ------------------------------------------------------------------ Filters & refresh
    def refresh(self):
        self._apply_filters()
        layer = self._resolve_current_layer()
        self._current_layer = layer
        if layer is not None:
            self._compute_layer_backed_pivot(layer)
        else:
            self._compute_dataframe_pivot()
        self._populate_table()

    def _apply_filters(self):
        df = self.raw_df
        if df is None or df.empty:
            self.filtered_df = pd.DataFrame()
            return

        filtered = df.copy()
        self.filtered_df = filtered

    def _compute_dataframe_pivot(self):
        df = self.filtered_df
        self._current_pivot_request = None
        self._current_pivot_result = None
        if df is None or df.empty:
            self.pivot_df = pd.DataFrame()
            return

        metric_key = self.value_field_combo.currentData()
        row_specs = self._selected_area_specs("row")
        col_specs = self._selected_area_specs("column")
        agg_func = self.agg_combo.currentData()
        metric = self._field_name_from_key(metric_key)
        row_fields = [spec.field_name for spec in row_specs if spec.source_type == "attribute"]
        col_fields = [spec.field_name for spec in col_specs if spec.source_type == "attribute"]

        if metric is None and agg_func != "count":
            self.pivot_df = pd.DataFrame()
            return

        if metric is not None and agg_func not in {"count", "min", "max", "unique"} and metric not in self.numeric_candidates:
            try:
                df[metric] = pd.to_numeric(df[metric], errors="coerce")
            except Exception:
                pass

        if not row_fields and not col_fields:
            if metric is None:
                self.pivot_df = pd.DataFrame({"Indicador": ["Contagem"], "Valor": [len(df.index)]})
                return
            series = df[metric]
            if agg_func == "count":
                value = series.count()
            else:
                value = self._aggregate_series(series, agg_func)
            self.pivot_df = pd.DataFrame({"Indicador": [metric], "Valor": [value]})
            return

        working = df.copy()
        synthetic_row = False
        if not row_fields:
            working["__row_total__"] = "Total"
            row_fields = ["__row_total__"]
            synthetic_row = True

        if col_fields:
            if metric is None and agg_func == "count":
                pivot = pd.crosstab(
                    index=[working[field] for field in row_fields] if len(row_fields) > 1 else working[row_fields[0]],
                    columns=[working[field] for field in col_fields] if len(col_fields) > 1 else working[col_fields[0]],
                    dropna=False,
                )
            else:
                values = None if metric is None else metric
                if values is not None and agg_func not in {"count", "min", "max", "unique"} and values not in self.numeric_candidates:
                    try:
                        working[values] = pd.to_numeric(working[values], errors="coerce")
                    except Exception:
                        pass
                pivot = pd.pivot_table(
                    working,
                    index=row_fields,
                    columns=col_fields,
                    values=values,
                    aggfunc="size" if metric is None and agg_func == "count" else self._pandas_aggfunc_name(agg_func),
                    dropna=False,
                )
            pivot = pivot.reset_index()
            pivot = self._flatten_pandas_columns(pivot, synthetic_row=synthetic_row)
            if agg_func != "count":
                pivot = pivot.applymap(lambda v: round(v, 2) if isinstance(v, (float, np.floating)) else v)
            self.pivot_df = pivot
            return

        if metric is None:
            grouped = working.groupby(row_fields, dropna=False).size()
        else:
            grouped = working.groupby(row_fields, dropna=False)[metric].agg(self._pandas_aggfunc_name(agg_func))
        pivot = grouped.reset_index()
        header = f"{agg_func.upper()}({metric})" if agg_func != "count" else f"COUNT({metric})"
        pivot.columns = row_fields + [header]
        if synthetic_row and row_fields:
            pivot = pivot.rename(columns={"__row_total__": "Total"})
            row_fields = ["Total"]
            header = pivot.columns[-1]
        if agg_func != "count":
            pivot[header] = pivot[header].round(2)
        if agg_func in ("sum", "count"):
            total = pivot[header].sum()
            if total:
                pivot["% do total"] = (pivot[header] / total * 100).round(2)
        pivot = pivot.sort_values(by=header, ascending=False).reset_index(drop=True)
        self.pivot_df = pivot

    def _compute_layer_backed_pivot(self, layer):
        try:
            request = self._build_pivot_request(layer)
            self._current_pivot_request = request
            self._current_pivot_result = self.pivot_engine.execute(request)
            self.pivot_df = self._pivot_result_to_dataframe(self._current_pivot_result)
            self.status_label.setText("")
        except PivotValidationError as exc:
            self._current_pivot_result = None
            self.pivot_df = pd.DataFrame()
            self.status_label.setText(str(exc))
        except Exception as exc:
            self._current_pivot_result = None
            self.pivot_df = pd.DataFrame()
            self.status_label.setText(f"Falha ao calcular a pivot: {exc}")

    def _populate_table(self):
        QgsMessageLog.logMessage(
            "PivotTableWidget: rebuilding table model", "PowerBISummarizer", Qgis.Info
        )
        self.proxy_model.setSourceModel(None)
        new_model = QStandardItemModel(self)
        self._display_row_keys = []
        self._display_column_keys = []
        self._pivot_data_column_offset = 0
        self._row_header_depth = 1

        if self.pivot_df is None or self.pivot_df.empty:
            new_model.setHorizontalHeaderLabels(["Nenhum resultado"])
            self.table_model = new_model
            self.proxy_model.setSourceModel(self.table_model)
            self.table_view.setModel(self.proxy_model)
            self._connect_selection_summary()
            self.proxy_model.invalidate()
            self._update_status_label()
            self._update_selection_summary()
            QgsMessageLog.logMessage(
                "PivotTableWidget: model rebuilt (empty)",
                "PowerBISummarizer",
                Qgis.Info,
            )
            return

        headers = list(self.pivot_df.columns)
        new_model.setHorizontalHeaderLabels(headers)
        self._display_row_keys = list(getattr(self._current_pivot_result, "row_headers", []) or [])
        self._display_column_keys = list(getattr(self._current_pivot_result, "column_headers", []) or [])
        self._row_header_depth = max(
            len((self._current_pivot_result.metadata or {}).get("row_fields") or []),
            max((len(key) for key in self._display_row_keys), default=0),
            1,
        )
        self._pivot_data_column_offset = self._row_header_depth

        base_font = QFont(TYPOGRAPHY.get("font_family", "Montserrat"), TYPOGRAPHY.get("font_body_size", 12))
        base_font.setWeight(QFont.Medium)
        total_column_index = headers.index("Total") if "Total" in headers else -1
        for row_index, row in enumerate(self.pivot_df.itertuples(index=False, name=None)):
            items = []
            for column_index, value in enumerate(row):
                if pd.isna(value):
                    text = ""
                elif isinstance(value, (float, np.floating)):
                    text = f"{value:,.2f}"
                else:
                    text = str(value)
                item = QStandardItem(text)
                item.setEditable(False)
                item.setData(None if pd.isna(value) else value, Qt.UserRole + 3)
                font = QFont(base_font)
                if column_index == total_column_index:
                    font.setBold(True)
                item.setFont(font)
                if column_index < self._pivot_data_column_offset:
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                if isinstance(value, (float, np.floating, int, np.integer)):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if (
                    self._current_pivot_result is not None
                    and row_index < len(self._display_row_keys)
                    and column_index >= self._pivot_data_column_offset
                ):
                    pivot_column_index = column_index - self._pivot_data_column_offset
                    if (
                        pivot_column_index < len(self._display_column_keys)
                        and row_index < len(self._current_pivot_result.matrix)
                        and pivot_column_index < len(self._current_pivot_result.matrix[row_index])
                    ):
                        matrix_cell = self._current_pivot_result.matrix[row_index][pivot_column_index]
                        feature_ids = list(getattr(matrix_cell, "feature_ids", []) or [])
                        item.setData(",".join(str(fid) for fid in feature_ids), Qt.UserRole)
                items.append(item)
            new_model.appendRow(items)

        self.table_model = new_model
        self.proxy_model.setSourceModel(self.table_model)
        self.table_view.setModel(self.proxy_model)
        self._connect_selection_summary()
        self.proxy_model.invalidate()
        self.table_view.resizeColumnsToContents()
        self._update_status_label()
        self._update_selection_summary()
        QgsMessageLog.logMessage(
            f"PivotTableWidget: model rebuilt with {self.table_model.rowCount()} rows",
            "PowerBISummarizer",
            Qgis.Info,
        )

    def _rebuild_column_filters(self, headers: List[str]):
        return

    # ------------------------------------------------------------------ Events
    def _on_search_text_changed(self, text: str):
        self.proxy_model.set_global_filter(text)
        self._update_status_label()

    def _on_column_filter_changed(self, column: int, text: str):
        self.proxy_model.set_column_filter(column, text)
        self._update_status_label()

    def _on_operation_changed(self, *args):
        aggregation = str(self.agg_combo.currentData() or "count")
        self.advanced_group.blockSignals(True)
        self.advanced_group.setChecked(aggregation != "count")
        self.advanced_group.blockSignals(False)
        self._on_advanced_toggled(aggregation != "count")
        self._update_status_label()
        if aggregation != "count":
            self._sync_default_value_field()

    def _on_advanced_toggled(self, checked: bool):
        self.advanced_value_label.setVisible(bool(checked))
        self.value_field_combo.setVisible(bool(checked))
        self._maybe_refresh()

    def _sync_default_value_field(self):
        if self.value_field_combo.count() == 0:
            return
        if self.value_field_combo.currentData() is not None:
            return
        for candidate in self.numeric_candidates:
            idx = self.value_field_combo.findText(candidate)
            if idx != -1:
                self.value_field_combo.setCurrentIndex(idx)
                return
        if self.value_field_combo.count():
            self.value_field_combo.setCurrentIndex(0)

    def _maybe_refresh(self):
        if self._block_updates:
            return
        auto_on = True
        if isinstance(self.auto_update_check, QCheckBox):
            auto_on = self.auto_update_check.isChecked()
        if auto_on:
            self.refresh()

    def _clear_filters(self):
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        self.proxy_model.set_global_filter("")
        self._update_status_label()

    def _filter_field_list(self, text: str):
        for index in range(self.fields_list.count()):
            item = self.fields_list.item(index)
            visible = text.lower() in item.text().lower()
            self.fields_list.setRowHidden(index, not visible)

    def _handle_field_double_click(self, item: QListWidgetItem):
        spec_key = item.data(Qt.UserRole)
        field_spec = self._field_spec_from_key(spec_key)
        if field_spec is None:
            return
        is_numeric = item.data(Qt.UserRole + 1)
        target_area = getattr(self, "_last_active_area", "row")
        if is_numeric:
            if self.advanced_group.isChecked():
                idx = self.value_field_combo.findData(spec_key)
                if idx != -1:
                    self.value_field_combo.setCurrentIndex(idx)
                    self._show_inline_message("", level="info")
                else:
                    self._show_inline_message(
                        f"O campo {field_spec.display_name} nao pode ser usado como valor.",
                        level="warning",
                    )
                self._maybe_refresh()
                return
            else:
                self._add_field_to_area(target_area, field_spec)
                return
        else:
            self._add_field_to_area(target_area, field_spec)
            return

    def _handle_table_cell_clicked(self, proxy_index):
        if not proxy_index.isValid():
            return
        self._safe_sync_selection_to_map()
        self._schedule_selection_feedback_refresh()

    def _handle_row_header_clicked(self, proxy_row: int):
        if self._current_pivot_result is None or self._current_layer is None:
            return
        self._select_proxy_row_data_cells(proxy_row)
        proxy_index = self.proxy_model.index(proxy_row, 0)
        if not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        if source_row < 0 or source_row >= len(self._current_pivot_result.matrix):
            return
        self.pivot_selection_bridge.select_row(self._current_layer, self._current_pivot_result.matrix[source_row])
        self._schedule_selection_feedback_refresh()

    def _handle_column_header_clicked(self, proxy_column: int):
        if self._current_pivot_result is None or self._current_layer is None:
            return
        source_column = proxy_column
        if source_column < self._pivot_data_column_offset:
            return
        self._select_proxy_column_data_cells(proxy_column)
        matrix_column = source_column - self._pivot_data_column_offset
        if matrix_column < 0 or matrix_column >= len(self._display_column_keys):
            return
        column_cells = []
        for row_cells in self._current_pivot_result.matrix:
            if matrix_column < len(row_cells):
                column_cells.append(row_cells[matrix_column])
        self.pivot_selection_bridge.select_column(self._current_layer, column_cells)
        self._schedule_selection_feedback_refresh()

    def _select_proxy_row_data_cells(self, proxy_row: int):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return
        last_column = self.proxy_model.columnCount() - 1
        first_data_column = self._pivot_data_column_offset
        if proxy_row < 0 or last_column < first_data_column:
            return
        start = self.proxy_model.index(proxy_row, first_data_column)
        end = self.proxy_model.index(proxy_row, last_column)
        if not start.isValid() or not end.isValid():
            return
        selection = QItemSelection(start, end)
        selection_model.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Select)
        self.table_view.setCurrentIndex(start)

    def _select_proxy_column_data_cells(self, proxy_column: int):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return
        row_count = self.proxy_model.rowCount()
        if row_count <= 0 or proxy_column < self._pivot_data_column_offset:
            return
        start = self.proxy_model.index(0, proxy_column)
        end = self.proxy_model.index(row_count - 1, proxy_column)
        if not start.isValid() or not end.isValid():
            return
        selection = QItemSelection(start, end)
        selection_model.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Select)
        self.table_view.setCurrentIndex(start)

    def _update_status_label(self):
        total = self.table_model.rowCount()
        visible = self.proxy_model.rowCount()
        row_labels = [self._area_list("row").item(i).text() for i in range(self._area_list("row").count())]
        column_labels = [self._area_list("column").item(i).text() for i in range(self._area_list("column").count())]
        parts = [f"Mostrando {visible}/{total} linha(s)"]
        if row_labels:
            parts.append(f"Linhas: {' / '.join(row_labels)}")
        if column_labels:
            parts.append(f"Colunas: {' / '.join(column_labels)}")
        self.status_label.setText(" | ".join(parts))

    def _connect_selection_summary(self):
        try:
            selection_model = self.table_view.selectionModel()
        except Exception:
            selection_model = None
        if selection_model is None:
            return
        try:
            selection_model.selectionChanged.disconnect(self._on_table_selection_changed)
        except Exception:
            pass
        selection_model.selectionChanged.connect(self._on_table_selection_changed)

    def _on_table_selection_changed(self, selected, deselected):
        self._schedule_selection_feedback_refresh()

    def eventFilter(self, watched, event):
        if watched in {getattr(self, "table_view", None), getattr(getattr(self, "table_view", None), "viewport", lambda: None)()}:
            if event is not None and event.type() in {
                QEvent.MouseButtonRelease,
                QEvent.KeyRelease,
                QEvent.FocusIn,
                QEvent.FocusOut,
            }:
                self._schedule_selection_feedback_refresh()
        return super().eventFilter(watched, event)

    def _schedule_selection_feedback_refresh(self):
        QTimer.singleShot(0, self._refresh_selection_feedback)

    def _refresh_selection_feedback(self):
        try:
            self._update_selection_summary()
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"PivotTableWidget: falha ao atualizar resumo de selecao: {exc}",
                "PowerBISummarizer",
                Qgis.Warning,
            )
            if hasattr(self, "selection_summary_label"):
                self.selection_summary_label.setText("Nao foi possivel calcular a selecao atual.")

    def _safe_sync_selection_to_map(self):
        try:
            self._sync_selection_to_map()
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"PivotTableWidget: falha ao sincronizar selecao no mapa: {exc}",
                "PowerBISummarizer",
                Qgis.Warning,
            )

    def _sync_selection_to_map(self):
        if self._current_layer is None:
            return
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return

        feature_ids: List[int] = []
        seen = set()
        for proxy_index in selection_model.selectedIndexes():
            if not proxy_index.isValid():
                continue
            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                continue
            if source_index.column() < self._pivot_data_column_offset:
                continue
            raw_ids = self._feature_ids_for_proxy_index(proxy_index, source_index)
            for fid in raw_ids:
                if fid in seen:
                    continue
                seen.add(fid)
                feature_ids.append(fid)
        self.pivot_selection_bridge.select_feature_ids(self._current_layer, feature_ids)

    def _update_selection_summary(self):
        if not hasattr(self, "selection_summary_label"):
            return
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            self.selection_summary_label.setText("Selecione celulas para ver soma e contagem.")
            return

        indexes = list(selection_model.selectedIndexes() or [])
        if not indexes:
            self.selection_summary_label.setText("Selecione celulas para ver soma e contagem.")
            return

        numeric_values: List[float] = []
        selected_count = 0
        numeric_count = 0
        for proxy_index in indexes:
            try:
                if not proxy_index.isValid():
                    continue
                if proxy_index.column() < self._pivot_data_column_offset:
                    continue
                selected_count += 1
                numeric_value = self._coerce_numeric_summary_value(proxy_index.data(Qt.DisplayRole))
                if numeric_value is not None:
                    numeric_values.append(numeric_value)
                    numeric_count += 1
            except Exception:
                continue

        if selected_count == 0:
            self.selection_summary_label.setText("Selecione celulas para ver soma e contagem.")
            return

        if numeric_values:
            total_sum = float(sum(numeric_values))
            sum_text = f"Soma: {self._format_selection_number(total_sum)}"
        else:
            sum_text = "Soma: -"
        self.selection_summary_label.setText(
            f"Selecionadas: {selected_count} celula(s) | {sum_text} | Numericas: {numeric_count}"
        )

    def _format_selection_number(self, value: float) -> str:
        try:
            numeric = float(value)
        except Exception:
            return "-"
        if abs(numeric - round(numeric)) < 1e-9:
            return f"{int(round(numeric)):,}"
        return f"{numeric:,.2f}"

    def _coerce_numeric_summary_value(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(" ", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            try:
                return float(text)
            except Exception:
                return None
        if re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+)(?:\.\d+)?", text):
            try:
                return float(text.replace(",", ""))
            except Exception:
                return None
        if re.fullmatch(r"-?(?:\d{1,3}(?:\.\d{3})+)(?:,\d+)?", text):
            try:
                return float(text.replace(".", "").replace(",", "."))
            except Exception:
                return None
        if "," in text and "." in text:
            cleaned = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
            try:
                return float(cleaned)
            except Exception:
                return None
        if "," in text:
            cleaned = text.replace(",", ".") if (text.count(",") == 1 and len(text.split(",")[-1]) <= 2) else text.replace(",", "")
            try:
                return float(cleaned)
            except Exception:
                return None
        if "." in text:
            if text.count(".") == 1 and len(text.split(".")[-1]) <= 2:
                try:
                    return float(text)
                except Exception:
                    return None
            try:
                return float(text.replace(".", ""))
            except Exception:
                return None
        try:
            return float(text)
        except Exception:
            return None

    def _feature_ids_for_proxy_index(self, proxy_index, source_index=None) -> List[int]:
        payload = proxy_index.data(Qt.UserRole)
        if isinstance(payload, str) and payload.strip():
            ids = [int(part) for part in payload.split(",") if part.strip().isdigit()]
            if ids:
                return ids
        if isinstance(payload, (list, tuple)):
            ids = [int(part) for part in payload if str(part).strip().isdigit()]
            if ids:
                return ids
        if source_index is not None and self._current_pivot_result is not None:
            row_index = source_index.row()
            column_index = source_index.column() - self._pivot_data_column_offset
            if row_index >= 0 and column_index >= 0 and row_index < len(self._current_pivot_result.matrix):
                row_cells = self._current_pivot_result.matrix[row_index]
                if column_index < len(row_cells):
                    cell = row_cells[column_index]
                    feature_ids = getattr(cell, "feature_ids", []) or []
                    return [int(fid) for fid in feature_ids if str(fid).strip().isdigit() or isinstance(fid, int)]
        return []

    def _apply_theming_tokens(self):
        try:
            font_family = TYPOGRAPHY.get("font_family", "Montserrat")
            base_font = QFont(font_family, TYPOGRAPHY.get("font_body_size", 12))
            base_font.setWeight(QFont.Medium)
            self.table_view.setFont(base_font)
            header_font = QFont(font_family, TYPOGRAPHY.get("font_body_size", 12))
            header_font.setWeight(QFont.DemiBold)
            self.table_view.horizontalHeader().setFont(header_font)
            self.table_view.setAlternatingRowColors(True)
        except Exception:
            pass

    def _set_last_active_area(self, area: str):
        if area in {"filter", "row", "column"}:
            self._last_active_area = area
            self._refresh_active_area_styles()

    def _refresh_active_area_styles(self):
        active = self._last_active_area
        for card, title, area in (
            (getattr(self, "row_area_card", None), getattr(self, "row_area_title", None), "row"),
            (getattr(self, "column_area_card", None), getattr(self, "column_area_title", None), "column"),
        ):
            if card is None or title is None:
                continue
            card.setProperty("activeArea", active == area)
            title.setProperty("activeArea", active == area)
            card.style().unpolish(card)
            card.style().polish(card)
            title.style().unpolish(title)
            title.style().polish(title)

    def _placeholder_item(self) -> QListWidgetItem:
        item = QListWidgetItem("Nenhum campo")
        item.setData(Qt.UserRole, "__placeholder__")
        item.setFlags(Qt.NoItemFlags)
        return item

    def _refresh_area_placeholder(self, area: str):
        list_widget = self._area_list(area)
        real_items_present = False
        for index in reversed(range(list_widget.count())):
            if list_widget.item(index).data(Qt.UserRole) == "__placeholder__":
                list_widget.takeItem(index)
            else:
                real_items_present = True
        if not real_items_present:
            list_widget.addItem(self._placeholder_item())
            list_widget.setCurrentRow(0)

    def _sync_area_placeholder(self, area: Optional[str] = None):
        names = (area,) if area else ("filter", "row", "column")
        for name in names:
            self._refresh_area_placeholder(name)

    def _resolve_current_layer(self):
        metadata = dict(self._current_metadata or {})
        layer_id = metadata.get("layer_id") or ""
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is not None:
                return layer
        layer_name = metadata.get("layer_name") or ""
        if layer_name:
            matches = QgsProject.instance().mapLayersByName(layer_name)
            if matches:
                return matches[0]
        return None

    def _build_attribute_field_spec(self, field_name: str, layer, df: pd.DataFrame) -> PivotFieldSpec:
        data_type = "text"
        display_name = field_name
        if layer is not None:
            field_index = layer.fields().indexFromName(field_name)
            field = layer.fields()[field_index] if field_index >= 0 else None
            if field is not None:
                data_type = self._map_variant_to_data_type(field.type())
                display_name = field.alias() or field.name()
        elif field_name in df.columns:
            if self._is_numeric_column(df[field_name]):
                data_type = "numeric"
        return PivotFieldSpec(
            field_name=field_name,
            display_name=display_name,
            source_type="attribute",
            data_type=data_type,
        )

    def _geometry_field_specs_for_layer(self, layer) -> List[PivotFieldSpec]:
        specs = []
        try:
            geometry_type = layer.geometryType()
        except Exception:
            geometry_type = None
        if geometry_type in (1, 2):
            specs.append(
                PivotFieldSpec(
                    field_name="__geometry_length__",
                    display_name="Comprimento geometrico",
                    source_type="geometry",
                    geometry_op="length",
                    data_type="numeric",
                )
            )
        if geometry_type == 2:
            specs.append(
                PivotFieldSpec(
                    field_name="__geometry_area__",
                    display_name="Area geometrica",
                    source_type="geometry",
                    geometry_op="area",
                    data_type="numeric",
                )
            )
        return specs

    def _register_field_spec(self, field_spec: PivotFieldSpec) -> str:
        key = f"{field_spec.source_type}:{field_spec.field_name}:{field_spec.geometry_op or ''}"
        self._field_specs_by_key[key] = field_spec
        return key

    def _field_spec_from_key(self, spec_key: Optional[str]) -> Optional[PivotFieldSpec]:
        if not spec_key:
            return None
        return self._field_specs_by_key.get(spec_key)

    def _field_name_from_key(self, spec_key: Optional[str]) -> Optional[str]:
        field_spec = self._field_spec_from_key(spec_key)
        if field_spec is None or field_spec.source_type != "attribute":
            return None
        return field_spec.field_name

    def _area_combo(self, area: str) -> QComboBox:
        if area == "row":
            return self.row_field_combo
        if area == "column":
            return self.column_field_combo
        return self.filter_field_combo

    def _area_list(self, area: str) -> QListWidget:
        if area == "row":
            return self.row_fields_list
        if area == "column":
            return self.column_fields_list
        return self.filter_fields_list

    def _area_label(self, area: str) -> str:
        if area == "row":
            return "Linhas"
        if area == "column":
            return "Colunas"
        return "Filtros"

    def _selected_area_specs(self, area: str) -> List[PivotFieldSpec]:
        specs: List[PivotFieldSpec] = []
        list_widget = self._area_list(area)
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            if item.data(Qt.UserRole) == "__placeholder__":
                continue
            spec = self._field_spec_from_key(item.data(Qt.UserRole))
            if spec is not None:
                specs.append(spec)
        return specs

    def _add_selected_field_to_area(self, area: str, auto_refresh: bool = True):
        self._set_last_active_area(area)
        combo = self._area_combo(area)
        return self._add_field_to_area(
            area,
            self._field_spec_from_key(combo.currentData()),
            auto_refresh=auto_refresh,
        )

    def _add_field_to_area(self, area: str, field_spec: Optional[PivotFieldSpec], auto_refresh: bool = True):
        if field_spec is None:
            return False
        list_widget = self._area_list(area)
        spec_key = self._register_field_spec(field_spec)
        self._set_last_active_area(area)
        if area == "filter":
            list_widget.clear()
        elif any(list_widget.item(index).data(Qt.UserRole) == spec_key for index in range(list_widget.count())):
            self._show_inline_message(
                f"O campo {field_spec.display_name} ja existe em {self._area_label(area)}.",
                level="warning",
            )
            return False

        for index in reversed(range(list_widget.count())):
            if list_widget.item(index).data(Qt.UserRole) == "__placeholder__":
                list_widget.takeItem(index)

        item = QListWidgetItem(field_spec.display_name)
        item.setData(Qt.UserRole, spec_key)
        list_widget.addItem(item)
        list_widget.setCurrentItem(item)
        self._show_inline_message("", level="info")
        self._sync_area_placeholder(area)
        if auto_refresh:
            self._maybe_refresh()
        return True

    def _remove_selected_area_field(self, area: str):
        list_widget = self._area_list(area)
        row = list_widget.currentRow()
        if row < 0:
            return
        if list_widget.item(row).data(Qt.UserRole) == "__placeholder__":
            return
        list_widget.takeItem(row)
        self._sync_area_placeholder(area)
        self._maybe_refresh()

    def _move_selected_area_field(self, area: str, offset: int):
        list_widget = self._area_list(area)
        row = list_widget.currentRow()
        if row < 0:
            return
        if list_widget.item(row).data(Qt.UserRole) == "__placeholder__":
            return
        new_row = row + offset
        if new_row < 0 or new_row >= list_widget.count():
            return
        if list_widget.item(new_row).data(Qt.UserRole) == "__placeholder__":
            return
        item = list_widget.takeItem(row)
        list_widget.insertItem(new_row, item)
        list_widget.setCurrentRow(new_row)
        self._maybe_refresh()

    def _clear_area(self, area: str):
        self._area_list(area).clear()
        self._sync_area_placeholder(area)

    def _ensure_default_row_area(self):
        if self.row_fields_list.count() > 0:
            return
        if self.raw_df is None or self.raw_df.empty:
            return
        candidate = next(
            (column for column in self.raw_df.columns if not self._is_numeric_column(self.raw_df[column])),
            self.raw_df.columns[0],
        )
        spec_key = None
        for index in range(self.row_field_combo.count()):
            if self.row_field_combo.itemText(index) == candidate:
                spec_key = self.row_field_combo.itemData(index)
                break
        self._add_field_to_area("row", self._field_spec_from_key(spec_key), auto_refresh=False)

    def _show_inline_message(self, message: str, level: str = "info"):
        self.status_label.setText(message)

    def _build_pivot_request(self, layer) -> PivotRequest:
        row_fields = self._selected_area_specs("row")
        column_fields = self._selected_area_specs("column")
        value_field = self._value_field_for_current_aggregation()
        aggregation = str(self.agg_combo.currentData() or "count")
        request = PivotRequest(
            layer_id=layer.id(),
            filter_expression=str((self._current_metadata or {}).get("filter_expression") or ""),
            row_fields=row_fields,
            column_fields=column_fields,
            value_field=value_field,
            aggregation=aggregation,
            only_selected=self.only_selected_check.isChecked(),
            include_nulls=self.include_nulls_check.isChecked(),
            include_percentages=True,
            include_totals=True,
        )
        return request

    def _value_field_for_current_aggregation(self) -> Optional[PivotFieldSpec]:
        aggregation = str(self.agg_combo.currentData() or "count")
        if aggregation == "count":
            return None
        if self.advanced_group.isChecked() and self.value_field_combo.currentData():
            spec = self._field_spec_from_key(self.value_field_combo.currentData())
            if spec is not None:
                return spec
        for candidate in self.numeric_candidates:
            if self._is_identifier_like_field(candidate):
                continue
            for index in range(self.value_field_combo.count()):
                if self.value_field_combo.itemText(index) == candidate:
                    spec = self._field_spec_from_key(self.value_field_combo.itemData(index))
                    if spec is not None:
                        return spec
        for index in range(self.value_field_combo.count()):
            spec = self._field_spec_from_key(self.value_field_combo.itemData(index))
            if spec is not None and spec.source_type in {"attribute", "geometry"}:
                return spec
        return None

    def _pivot_result_to_dataframe(self, result) -> pd.DataFrame:
        if result is None:
            return pd.DataFrame()
        metadata = dict(result.metadata or {})
        row_fields = list(metadata.get("row_fields") or [])
        row_depth = max(len(row_fields), max((len(key) for key in result.row_headers), default=0), 1)
        headers = []
        for index in range(row_depth):
            if index < len(row_fields):
                headers.append(str(row_fields[index]))
            elif row_depth == 1:
                headers.append("Linha")
            else:
                headers.append(f"Linha {index + 1}")

        records = []
        for row_index, row_key in enumerate(result.row_headers or [()]):
            record = {}
            row_values = list(row_key)
            while len(row_values) < row_depth:
                row_values.append("")
            for header, value in zip(headers, row_values[:row_depth]):
                record[header] = value
            for column_index, column_key in enumerate(result.column_headers or [()]):
                column_label = self._format_header_tuple(column_key)
                cell = (
                    result.matrix[row_index][column_index]
                    if row_index < len(result.matrix) and column_index < len(result.matrix[row_index])
                    else None
                )
                record[column_label] = getattr(cell, "raw_value", None)
            if result.row_totals:
                record["Total"] = result.row_totals.get(row_key)
            records.append(record)
        return pd.DataFrame(records)

    def _aggregate_series(self, series: pd.Series, agg_func: str):
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if agg_func == "median":
            return float(numeric.median()) if not numeric.empty else None
        if agg_func == "unique":
            return int(series.nunique(dropna=not self.include_nulls_check.isChecked()))
        if agg_func == "variance":
            return float(numeric.var(ddof=0)) if not numeric.empty else None
        if agg_func == "stddev":
            return float(numeric.std(ddof=0)) if not numeric.empty else None
        if agg_func == "average":
            return float(numeric.mean()) if not numeric.empty else None
        return series.astype(float).agg(agg_func)

    def _pandas_aggfunc_name(self, agg_func: str) -> str:
        mapping = {
            "average": "mean",
            "stddev": "std",
            "unique": "nunique",
        }
        return mapping.get(agg_func, agg_func)

    def _map_variant_to_data_type(self, variant_type: int) -> str:
        if variant_type in {
            QVariant.Int,
            QVariant.UInt,
            QVariant.LongLong,
            QVariant.ULongLong,
            QVariant.Double,
        }:
            return "numeric"
        if variant_type in {QVariant.Date, QVariant.DateTime, QVariant.Time}:
            return "date"
        if variant_type == QVariant.Bool:
            return "bool"
        return "text"

    def _format_header_tuple(self, values: tuple) -> str:
        if not values:
            return "Total"
        return " / ".join("Sem valor" if value in (None, "") else str(value) for value in values)

    def _flatten_pandas_columns(self, df: pd.DataFrame, synthetic_row: bool = False) -> pd.DataFrame:
        flattened = []
        for column in df.columns:
            if isinstance(column, tuple):
                parts = [str(part) for part in column if part not in (None, "")]
                if synthetic_row and parts and parts[0] == "__row_total__":
                    flattened.append("Total")
                else:
                    flattened.append(" / ".join(parts) if parts else "Total")
            else:
                flattened.append("Total" if synthetic_row and column == "__row_total__" else column)
        result = df.copy()
        result.columns = flattened
        return result

    # ------------------------------------------------------------------ Public API
    def get_visible_pivot_dataframe(self) -> pd.DataFrame:
        """
        Return a DataFrame representing the pivot table with any UI filters applied.

        The returned frame is detached from the internal reference to avoid callers
        mutating state unintentionally.
        """
        if self.pivot_df is None or self.pivot_df.empty:
            return pd.DataFrame()

        if self.table_model.columnCount() == 0:
            return pd.DataFrame(columns=self.pivot_df.columns)

        visible_rows: List[int] = []
        for row in range(self.proxy_model.rowCount()):
            proxy_index = self.proxy_model.index(row, 0)
            if not proxy_index.isValid():
                continue
            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                continue
            visible_rows.append(source_index.row())

        if not visible_rows:
            return pd.DataFrame(columns=self.pivot_df.columns)

        return self.pivot_df.iloc[visible_rows].reset_index(drop=True)

    def get_current_configuration(self) -> Dict[str, Any]:
        """Expose the active pivot configuration (fields and aggregation)."""
        value_spec = self._field_spec_from_key(self.value_field_combo.currentData())
        row_specs = self._selected_area_specs("row")
        column_specs = self._selected_area_specs("column")
        filter_specs = self._selected_area_specs("filter")
        row_fields = [spec.field_name for spec in row_specs]
        column_fields = [spec.field_name for spec in column_specs]
        filter_fields = [spec.field_name for spec in filter_specs]
        return {
            "aggregation": self.agg_combo.currentData(),
            "aggregation_label": self.agg_combo.currentText(),
            "value_field": value_spec.field_name if value_spec is not None else None,
            "value_label": value_spec.display_name if value_spec is not None else self.value_field_combo.currentText(),
            "row_field": row_fields[0] if row_fields else None,
            "row_label": " / ".join(spec.display_name for spec in row_specs) if row_specs else self.row_field_combo.currentText(),
            "row_fields": row_fields,
            "row_labels": [spec.display_name for spec in row_specs],
            "column_field": column_fields[0] if column_fields else None,
            "column_label": " / ".join(spec.display_name for spec in column_specs) if column_specs else self.column_field_combo.currentText(),
            "column_fields": column_fields,
            "column_labels": [spec.display_name for spec in column_specs],
            "filter_field": filter_fields[0] if filter_fields else None,
            "filter_label": " / ".join(spec.display_name for spec in filter_specs) if filter_specs else self.filter_field_combo.currentText(),
            "filter_fields": filter_fields,
            "filter_labels": [spec.display_name for spec in filter_specs],
            "only_selected": self.only_selected_check.isChecked(),
            "include_nulls": self.include_nulls_check.isChecked(),
        }

    def get_summary_metadata(self) -> Dict[str, str]:
        """Return a shallow copy of the last summary metadata provided."""
        metadata = dict(self._current_metadata)
        if self._current_pivot_result is not None:
            metadata.update(dict(self._current_pivot_result.metadata or {}))
        return metadata

    def get_current_pivot_result(self):
        return self._current_pivot_result

    def set_auto_update_checkbox(self, checkbox: QCheckBox):
        """
        Place an external auto-update checkbox inside the toolbar,
        wiring it to reuse the widget for refresh gating.
        """
        if checkbox is None:
            return

        if checkbox.parent() is not self:
            checkbox.setParent(self)

        if self.toolbar_layout is not None:
            # Remove any previously injected checkbox
            if self._external_auto_checkbox is not None:
                self.toolbar_layout.removeWidget(self._external_auto_checkbox)
                self._external_auto_checkbox.setVisible(False)
            checkbox.setMinimumHeight(26)
            self.toolbar_layout.addWidget(checkbox)
            checkbox.setVisible(True)
        self.auto_update_check = checkbox
        self._external_auto_checkbox = checkbox

    def add_dashboard_button(self, button: QPushButton):
        """Insert the dashboard trigger beside the export controls."""
        if button is None or self.toolbar_layout is None:
            return

        if button.parent() is not self:
            button.setParent(self)
        button.setMinimumHeight(26)

        # Position immediately before the export button if possible
        target_index = self.toolbar_layout.indexOf(self.export_btn)
        insert_index = target_index if target_index != -1 else self.toolbar_layout.count()
        self.toolbar_layout.insertWidget(insert_index, button)
        button.setVisible(True)
        self._external_dashboard_button = button

    def clear_all_filters(self):
        """Expose filter reset so external buttons can reuse it."""
        self._clear_filters()

    # ------------------------------------------------------------------ Helpers
    def _detect_numeric_candidates(self, df: pd.DataFrame) -> List[str]:
        result = []
        for column in df.columns:
            if self._is_numeric_column(df[column]):
                result.append(column)
        return result

    def _is_identifier_like_field(self, field_name: str) -> bool:
        normalized = (field_name or "").strip().lower()
        return normalized in {"fid", "id", "gid", "objectid", "object_id", "ogc_fid"}

    def _is_numeric_column(self, series: pd.Series) -> bool:
        if ptypes.is_numeric_dtype(series):
            return True
        converted = pd.to_numeric(series, errors="coerce")
        return converted.notna().any()

    # ------------------------------------------------------------------ Export
    def _export_pivot_table(self):
        if self.pivot_df is None or self.pivot_df.empty:
            QMessageBox.information(
                self, "Exportar tabela dinamica", "Nao ha dados para exportar."
            )
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar tabela dinamica",
            "",
            self.EXPORT_FILTERS,
        )
        if not path:
            return

        try:
            if "csv" in selected_filter.lower():
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                if self._current_pivot_result is not None:
                    self.pivot_export_service.export_to_csv(self._current_pivot_result, path)
                else:
                    self.pivot_df.to_csv(path, index=False)
            elif "xlsx" in selected_filter.lower():
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                if self._current_pivot_result is not None:
                    self.pivot_export_service.export_to_excel(self._current_pivot_result, path)
                else:
                    self.pivot_df.to_excel(path, index=False)
            else:
                if not path.lower().endswith(".gpkg"):
                    path += ".gpkg"
                self._export_to_gpkg(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Exportar tabela dinamica",
                f"Falha ao exportar a tabela dinamica: {exc}",
            )
            return

        QMessageBox.information(
            self,
            "Exportar tabela dinamica",
            f"Tabela dinamica exportada para:\n{path}",
        )

    def _export_to_gpkg(self, path: str):
        df = self.pivot_df
        layer_name = self._current_metadata.get("layer_name") or "tabela_dinamica"
        safe_name = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in layer_name
        )

        memory_layer = QgsVectorLayer("None", safe_name, "memory")
        provider = memory_layer.dataProvider()

        fields = QgsFields()
        for column in df.columns:
            variant_type = self._map_dtype_to_qvariant(df[column])
            fields.append(QgsField(column, variant_type))
        provider.addAttributes(fields)
        memory_layer.updateFields()

        features = []
        for row in df.itertuples(index=False, name=None):
            feature = QgsFeature()
            feature.setFields(fields)
            attrs = []
            for value in row:
                if isinstance(value, (float, np.floating)):
                    attrs.append(float(value) if not pd.isna(value) else None)
                elif isinstance(value, (int, np.integer)):
                    attrs.append(int(value))
                elif pd.isna(value):
                    attrs.append(None)
                else:
                    attrs.append(value)
            feature.setAttributes(attrs)
            features.append(feature)
        provider.addFeatures(features)
        memory_layer.updateExtents()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = safe_name

        transform_context = QgsProject.instance().transformContext()
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            memory_layer,
            path,
            transform_context,
            options,
        )

        if isinstance(result, tuple):
            status = result[0]
            message = result[1] if len(result) > 1 else ""
        else:
            status = result
            message = ""

        if status != QgsVectorFileWriter.NoError:
            raise RuntimeError(message or "Falha ao escrever GeoPackage.")

    def _map_dtype_to_qvariant(self, series: pd.Series) -> QVariant.Type:
        if self._is_numeric_column(series):
            if ptypes.is_integer_dtype(series):
                return QVariant.LongLong
            return QVariant.Double
        if ptypes.is_datetime64_any_dtype(series):
            return QVariant.DateTime
        if ptypes.is_bool_dtype(series):
            return QVariant.Bool
        return QVariant.String

