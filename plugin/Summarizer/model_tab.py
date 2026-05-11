from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QByteArray, QPoint, QSize, Qt, QMimeData, pyqtSignal
from qgis.PyQt.QtGui import QColor, QDrag, QIcon, QKeySequence, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,
    QScrollArea,
    QSlider,
    QSplitter,
    QSpinBox,
    QToolButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox

from .dashboard_add_dialog import DashboardAddDialog
from .dashboard_canvas import DashboardCanvas
from .dashboard_models import (
    DashboardChartBinding,
    DashboardChartItem,
    DashboardPage,
    DashboardProject,
    FieldBindingItem,
    ROLE_FILTERS,
    ROLE_LEGEND,
    ROLE_SIZE,
    ROLE_TOOLTIP,
    ROLE_VALUES,
    ROLE_X_AXIS,
    ROLE_Y_AXIS,
    binding_slot_definitions,
    empty_binding_message,
    is_binding_slot_compatible,
    normalize_aggregation,
    normalize_binding_role,
    normalize_chart_type,
    suggest_binding_slot,
)
from .dashboard_page_widget import DashboardPageWidget
from .dashboard_project_store import DashboardProjectStore, PROJECT_EXTENSION
from .field_list_helpers import configure_field_item, field_kind_badge, field_kind_from_field_def, normalize_field_kind
from .report_view.charts import ChartVisualState
from .report_view.result_models import ChartPayload
from .model_view.model_cards import _DialogDragHandle, _ModelCardAction, _ModelModeToggle, _ModelRecentCard
from .slim_dialogs import slim_message, slim_question
from .utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
from .utils.i18n_runtime import tr_text as _rt
from .utils.resources import svg_icon
from .utils.logging_utils import log_exception
from .visual_format_panel import VisualFormatPanel

_MODEL_FIELD_MIME = "application/x-summarizer-model-field"
_MODEL_FIELD_ROLE = Qt.UserRole + 41
_MODEL_TRASH_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14.7404 9L14.3942 18M9.60577 18L9.25962 9M19.2276 5.79057C19.5696 5.84221 19.9104 5.89747 20.25 5.95629M19.2276 5.79057L18.1598 19.6726C18.0696 20.8448 17.0921 21.75 15.9164 21.75H8.08357C6.90786 21.75 5.93037 20.8448 5.8402 19.6726L4.77235 5.79057M19.2276 5.79057C18.0812 5.61744 16.9215 5.48485 15.75 5.39432M3.75 5.95629C4.08957 5.89747 4.43037 5.84221 4.77235 5.79057M4.77235 5.79057C5.91878 5.61744 7.07849 5.48485 8.25 5.39432M15.75 5.39432V4.47819C15.75 3.29882 14.8393 2.31423 13.6606 2.27652C13.1092 2.25889 12.5556 2.25 12 2.25C11.4444 2.25 10.8908 2.25889 10.3394 2.27652C9.16065 2.31423 8.25 3.29882 8.25 4.47819V5.39432M15.75 5.39432C14.5126 5.2987 13.262 5.25 12 5.25C10.738 5.25 9.48744 5.2987 8.25 5.39432" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


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
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


class _ModelFieldList(QListWidget):
    fieldActivated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.itemDoubleClicked.connect(self._emit_activated)

    def _emit_activated(self, item):
        payload = item.data(_MODEL_FIELD_ROLE) if item is not None else None
        if isinstance(payload, dict):
            self.fieldActivated.emit(dict(payload))

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        payload = item.data(_MODEL_FIELD_ROLE)
        if not isinstance(payload, dict):
            return
        mime = QMimeData()
        mime.setData(_MODEL_FIELD_MIME, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)


class _ModelFieldBindingChip(QFrame):
    removeRequested = pyqtSignal(str)
    aggregationChanged = pyqtSignal(str, str)
    moveRequested = pyqtSignal(str, int)

    def __init__(self, binding_item: FieldBindingItem, parent=None, *, source_item_id: str = ""):
        super().__init__(parent)
        self.binding_item = binding_item.normalized()
        self.source_item_id = str(source_item_id or "").strip()
        self._drag_start_pos = QPoint()
        self.setObjectName("ModelBindingFieldChip")
        self.setCursor(Qt.OpenHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 4, 2)
        layout.setSpacing(4)

        badge = QLabel(field_kind_badge(self.binding_item.type), self)
        badge.setObjectName("ModelBindingFieldBadge")
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge, 0)

        name = QLabel(self.binding_item.display_name or self.binding_item.field, self)
        name.setObjectName("ModelBindingFieldName")
        name.setToolTip(self.binding_item.field)
        name.setMinimumWidth(42)
        layout.addWidget(name, 1)

        self.aggregation_combo = QComboBox(self)
        self.aggregation_combo.setObjectName("ModelBindingAggregationCombo")
        for label, value in (
            (_rt("Sem agreg."), "none"),
            (_rt("Soma"), "sum"),
            (_rt("Contagem"), "count"),
            (_rt("Media"), "avg"),
            (_rt("Min"), "min"),
            (_rt("Max"), "max"),
            (_rt("Unicos"), "unique_count"),
        ):
            self.aggregation_combo.addItem(label, value)
        index = self.aggregation_combo.findData(self.binding_item.aggregation)
        self.aggregation_combo.setCurrentIndex(index if index >= 0 else 0)
        self.aggregation_combo.currentIndexChanged.connect(self._emit_aggregation_changed)
        self.aggregation_combo.setVisible(self.binding_item.aggregation != "none" or self.binding_item.role in {ROLE_VALUES, ROLE_Y_AXIS, ROLE_SIZE})
        layout.addWidget(self.aggregation_combo, 0)

        for text, delta, tooltip in (("↑", -1, _rt("Mover para cima")), ("↓", 1, _rt("Mover para baixo"))):
            button = QToolButton(self)
            button.setObjectName("ModelBindingSlotMove")
            button.setText(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFixedSize(16, 16)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, value=delta: self.moveRequested.emit(self.binding_item.field, value))
            layout.addWidget(button, 0)

        remove = QToolButton(self)
        remove.setObjectName("ModelBindingSlotRemove")
        remove.setCursor(Qt.PointingHandCursor)
        remove.setAutoRaise(True)
        remove.setFixedSize(18, 18)
        remove.setIcon(_model_builder_trash_icon())
        remove.setIconSize(QSize(14, 14))
        remove.setToolTip(_rt("Remover campo"))
        remove.clicked.connect(lambda checked=False: self.removeRequested.emit(self.binding_item.field))
        layout.addWidget(remove, 0)

    def _emit_aggregation_changed(self):
        aggregation = str(self.aggregation_combo.currentData() or "none")
        self.aggregationChanged.emit(self.binding_item.field, aggregation)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 6:
            super().mouseMoveEvent(event)
            return
        payload = {
            "field_name": self.binding_item.field,
            "display_name": self.binding_item.display_name or self.binding_item.field,
            "field_group": self.binding_item.type,
            "field_kind": self.binding_item.type,
            "aggregation": self.binding_item.aggregation,
            "source_slot": self.binding_item.role,
            "source_item_id": self.source_item_id,
        }
        mime = QMimeData()
        mime.setData(_MODEL_FIELD_MIME, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        self.setCursor(Qt.ClosedHandCursor)
        try:
            drag.exec_(Qt.MoveAction)
        finally:
            self.setCursor(Qt.OpenHandCursor)
        super().mouseMoveEvent(event)


class _ModelBindingSlot(QFrame):
    fieldDropped = pyqtSignal(str, object)
    removeRequested = pyqtSignal(str, str)
    aggregationChanged = pyqtSignal(str, str, str)
    moveRequested = pyqtSignal(str, str, int)

    def __init__(self, slot_name: str, label: str, parent=None):
        super().__init__(parent)
        self.slot_name = str(slot_name or "").strip()
        self._source_item_id = ""
        self.setObjectName("ModelBindingSlot")
        self.setAcceptDrops(True)
        self._active = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 5, 6, 6)
        self._layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        self.label_widget = QLabel(label, self)
        self.label_widget.setObjectName("ModelBindingSlotLabel")
        header.addWidget(self.label_widget, 1)
        self._layout.addLayout(header, 0)

        self.value_widget = QLabel(_rt("Arraste campos aqui"), self)
        self.value_widget.setObjectName("ModelBindingSlotValue")
        self.value_widget.setWordWrap(True)
        self._layout.addWidget(self.value_widget, 0)

        self.chips_host = QWidget(self)
        self.chips_host.setObjectName("ModelBindingSlotChips")
        self.chips_layout = QVBoxLayout(self.chips_host)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(3)
        self._layout.addWidget(self.chips_host, 0)
        self._chip_widgets = []

    def set_value(self, text: str, *, placeholder: str = ""):
        self.set_values([text] if str(text or "").strip() else [], placeholder=placeholder)

    def set_label(self, text: str):
        self.label_widget.setText(str(text or ""))

    def set_values(self, values, *, placeholder: str = "", source_item_id: str = ""):
        self._source_item_id = str(source_item_id or "").strip()
        clean_values = []
        for index, value in enumerate(list(values or [])):
            if isinstance(value, FieldBindingItem):
                item = value.normalized(self.slot_name, index)
            elif isinstance(value, dict):
                item = FieldBindingItem.from_payload(value, self.slot_name, index)
            else:
                item = FieldBindingItem.from_payload(str(value or "").strip(), self.slot_name, index)
            if item is not None and item.field:
                clean_values.append(item)
        for widget in list(getattr(self, "_chip_widgets", []) or []):
            self.chips_layout.removeWidget(widget)
            widget.deleteLater()
        self._chip_widgets = []
        if clean_values:
            self.value_widget.hide()
            self.chips_host.show()
            for item in clean_values:
                chip = _ModelFieldBindingChip(item, self.chips_host, source_item_id=self._source_item_id)
                chip.removeRequested.connect(lambda field_name, slot=self.slot_name: self.removeRequested.emit(slot, field_name))
                chip.aggregationChanged.connect(lambda field_name, aggregation, slot=self.slot_name: self.aggregationChanged.emit(slot, field_name, aggregation))
                chip.moveRequested.connect(lambda field_name, delta, slot=self.slot_name: self.moveRequested.emit(slot, field_name, delta))
                self.chips_layout.addWidget(chip, 0)
                self._chip_widgets.append(chip)
            self.setProperty("filled", True)
        else:
            self.chips_host.hide()
            self.value_widget.show()
            self.value_widget.setText(str(placeholder or _rt("Adicionar campo\nArraste campos aqui")))
            self.setProperty("filled", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_active(self, active: bool):
        self._active = bool(active)
        self.setProperty("dropActive", self._active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event):
        try:
            if event.mimeData().hasFormat(_MODEL_FIELD_MIME):
                self.set_active(True)
                event.acceptProposedAction()
                return
        except Exception:
            log_exception("falha opcional ignorada")
        event.ignore()

    def dragMoveEvent(self, event):
        try:
            if event.mimeData().hasFormat(_MODEL_FIELD_MIME):
                self.set_active(True)
                event.acceptProposedAction()
                return
        except Exception:
            log_exception("falha opcional ignorada")
        event.ignore()

    def dragLeaveEvent(self, event):
        self.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.set_active(False)
        try:
            if not event.mimeData().hasFormat(_MODEL_FIELD_MIME):
                event.ignore()
                return
            payload = json.loads(bytes(event.mimeData().data(_MODEL_FIELD_MIME)).decode("utf-8"))
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            event.ignore()
            return
        self.fieldDropped.emit(self.slot_name, payload)
        event.acceptProposedAction()


class ModelTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelTabRoot")
        self.store = DashboardProjectStore()
        self.current_project: Optional[DashboardProject] = None
        self.current_path: str = ""
        self._dirty = False
        self._syncing_zoom_controls = False
        self._suspend_canvas_events = False
        self._is_adding_page = False
        self._builder_layers: Dict[str, QgsVectorLayer] = {}
        self._page_widgets: Dict[str, DashboardPageWidget] = {}
        self._selected_page_id: str = ""
        self._single_page_mode = True
        self.canvas: Optional[DashboardCanvas] = None
        self._history_undo: List[Dict[str, object]] = []
        self._history_redo: List[Dict[str, object]] = []
        self._history_current: Optional[Dict[str, object]] = None
        self._history_restoring = False
        self._history_limit = 80
        self._builder_panel_open = False
        self._visual_panel_open = False
        self._builder_selected_item_id: str = ""
        self._builder_field_catalog: Dict[str, List[Dict[str, str]]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 3)
        root.setSpacing(4)

        header = QFrame(self)
        header.setObjectName("ModelHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        self.new_btn = QPushButton(_rt("Novo"))
        self.open_btn = QPushButton(_rt("Abrir"))
        self.save_btn = QPushButton(_rt("Salvar"))
        self.save_as_btn = QPushButton(_rt("Salvar como"))
        self.export_btn = QPushButton(_rt("Exportar"))
        self.undo_btn = QPushButton(_rt("Desfazer"))
        self.redo_btn = QPushButton(_rt("Refazer"))
        self.create_chart_btn = QPushButton(_rt("Criar grafico"))
        self.format_visual_btn = QPushButton(_rt("Formatar visual"))
        self.edit_mode_btn = QPushButton(_rt("Edicao"))
        self.settings_btn = QPushButton(_rt("Configuracoes"))
        self.create_chart_btn.setCheckable(True)
        self.create_chart_btn.setChecked(False)
        self.format_visual_btn.setCheckable(True)
        self.format_visual_btn.setChecked(False)
        self.edit_mode_btn.setCheckable(True)
        self.edit_mode_btn.setChecked(True)
        self.close_project_btn = QToolButton()
        self.close_project_btn.setObjectName("ModelCloseProjectButton")
        self._configure_toolbar_icon_button(self.undo_btn, "Walker-Undo.svg", _rt("Desfazer (Ctrl+Z)"))
        self._configure_toolbar_icon_button(self.redo_btn, "Walker-Redo.svg", _rt("Refazer (Ctrl+Shift+Z)"))
        self._configure_toolbar_icon_button(self.new_btn, "Walker-New.svg", _rt("Novo"))
        self._configure_toolbar_icon_button(self.open_btn, "Walker-Open.svg", _rt("Abrir"))
        self._configure_toolbar_icon_button(self.save_btn, "Walker-Save.svg", _rt("Salvar"))
        self._configure_toolbar_icon_button(self.save_as_btn, "Walker-SaveAs.svg", _rt("Salvar como"))
        self._configure_toolbar_icon_button(self.export_btn, "Walker-Image.svg", _rt("Exportar imagem"))
        self._configure_toolbar_icon_button(self.create_chart_btn, "ModelVisual-Pie.svg", _rt("Criar grafico"))
        self._configure_toolbar_icon_button(self.format_visual_btn, "Walker-Format.svg", _rt("Formatar visual"))
        self._configure_toolbar_icon_button(self.edit_mode_btn, "Walker-Edit.svg", _rt("Edicao"))
        self._configure_toolbar_icon_button(
            self.settings_btn,
            "Walker-Settings.svg",
            _rt("Configurar fundo e grade do canvas"),
        )
        self._configure_toolbar_icon_button(
            self.close_project_btn,
            "Close.svg",
            _rt("Fechar projeto e voltar para a tela inicial"),
            icon_size=16,
        )
        self.close_project_btn.setVisible(False)
        for button in (
            self.undo_btn,
            self.redo_btn,
            self.new_btn,
            self.open_btn,
            self.save_btn,
            self.save_as_btn,
            self.export_btn,
            self.create_chart_btn,
            self.format_visual_btn,
            self.edit_mode_btn,
            self.settings_btn,
            self.close_project_btn,
        ):
            button.setObjectName("ModelToolbarButton")

        self.toolbar_strip = QFrame(header)
        self.toolbar_strip.setObjectName("ModelToolbarStrip")
        self.toolbar_strip.setAttribute(Qt.WA_StyledBackground, True)
        toolbar_layout = QHBoxLayout(self.toolbar_strip)
        toolbar_layout.setContentsMargins(8, 5, 8, 5)
        toolbar_layout.setSpacing(2)
        for button in (self.undo_btn, self.redo_btn):
            toolbar_layout.addWidget(button, 0)
        toolbar_layout.addWidget(self._create_toolbar_separator(self.toolbar_strip), 0)
        for button in (self.new_btn, self.open_btn, self.save_btn, self.save_as_btn, self.export_btn):
            toolbar_layout.addWidget(button, 0)
        toolbar_layout.addWidget(self._create_toolbar_separator(self.toolbar_strip), 0)
        for button in (self.create_chart_btn, self.format_visual_btn, self.edit_mode_btn, self.settings_btn):
            toolbar_layout.addWidget(button, 0)
        toolbar_layout.addStretch(1)
        self.mode_switch_wrap = QWidget(self.toolbar_strip)
        self.mode_switch_wrap.setObjectName("ModelModeSwitchWrap")
        mode_layout = QHBoxLayout(self.mode_switch_wrap)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(6)
        self.mode_state_label = QLabel(_rt("Edição"), self.mode_switch_wrap)
        self.mode_state_label.setObjectName("ModelModeStateLabel")
        self.mode_toggle = _ModelModeToggle(self.mode_switch_wrap)
        self.mode_toggle.setObjectName("ModelModeToggle")
        self.mode_toggle.setChecked(True, animated=False)
        self.mode_toggle.setToolTip(_rt("Alternar entre modo de edição e pré-visualização"))
        mode_layout.addWidget(self.mode_state_label, 0)
        mode_layout.addWidget(self.mode_toggle, 0)
        self.clear_filters_btn = QPushButton(_rt("Limpar filtros"))
        self.clear_filters_btn.setObjectName("ModelActionButton")
        self.clear_filters_btn.setVisible(False)
        self.clear_filters_btn.clicked.connect(self._clear_model_filters)
        toolbar_layout.addWidget(self.clear_filters_btn, 0)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.mode_switch_wrap, 0)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.close_project_btn, 0)

        top_row.addWidget(self.toolbar_strip, 1)
        header_layout.addLayout(top_row)

        self.project_hint_label = QLabel(
            _rt("Monte painéis com os graficos da aba Resumo e da aba Relatorios. O painel salvo continua editavel.")
        )
        self.project_hint_label.setObjectName("ModelHint")
        self.project_hint_label.setWordWrap(True)
        self.project_hint_label.setVisible(False)
        header_layout.addWidget(self.project_hint_label)

        root.addWidget(header, 0)

        self.filters_bar = QFrame(self)
        self.filters_bar.setObjectName("ModelFiltersBar")
        self.filters_bar.setAttribute(Qt.WA_StyledBackground, True)
        filters_layout = QHBoxLayout(self.filters_bar)
        filters_layout.setContentsMargins(14, 10, 14, 10)
        filters_layout.setSpacing(10)
        self.filters_label = QLabel(_rt("Filtros ativos: nenhum"))
        self.filters_label.setObjectName("ModelFiltersLabel")
        self.filters_label.setWordWrap(True)
        filters_layout.addWidget(self.filters_label, 1)
        self.filters_bar.setVisible(False)
        root.addWidget(self.filters_bar, 0)

        self.body_stack = QStackedWidget(self)
        root.addWidget(self.body_stack, 1)

        self.empty_page = QWidget(self.body_stack)
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(14)

        welcome = QFrame(self.empty_page)
        welcome.setObjectName("ModelWelcomeCard")
        welcome.setAttribute(Qt.WA_StyledBackground, True)
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setContentsMargins(18, 18, 18, 18)
        welcome_layout.setSpacing(14)

        welcome_title = QLabel(_rt("Comece um painel no Model"))
        welcome_title.setObjectName("ModelWelcomeTitle")
        welcome_layout.addWidget(welcome_title)

        welcome_text = QLabel(
            _rt("Use os graficos do plugin como blocos editaveis. Adicione pelo menu contextual e reorganize no canvas branco.")
        )
        welcome_text.setObjectName("ModelWelcomeText")
        welcome_text.setWordWrap(True)
        welcome_layout.addWidget(welcome_text)

        welcome_layout.addStretch(1)

        empty_layout.addWidget(welcome, 0)

        self.recents_card = QFrame(self.empty_page)
        self.recents_card.setObjectName("ModelRecentsCard")
        self.recents_card.setAttribute(Qt.WA_StyledBackground, True)
        recents_layout = QVBoxLayout(self.recents_card)
        recents_layout.setContentsMargins(18, 18, 18, 18)
        recents_layout.setSpacing(10)

        recents_title = QLabel(_rt("Paineis recentes"))
        recents_title.setObjectName("ModelRecentsTitle")
        recents_layout.addWidget(recents_title)

        self.recents_placeholder = QLabel(_rt("Nenhum painel recente encontrado."))
        self.recents_placeholder.setObjectName("ModelRecentsPlaceholder")
        self.recents_placeholder.setWordWrap(True)
        recents_layout.addWidget(self.recents_placeholder)

        self.recents_container = QWidget(self.recents_card)
        self.recents_layout = QVBoxLayout(self.recents_container)
        self.recents_layout.setContentsMargins(0, 0, 0, 0)
        self.recents_layout.setSpacing(8)
        recents_layout.addWidget(self.recents_container)

        empty_layout.addWidget(self.recents_card, 1)

        self.canvas_page = QWidget(self.body_stack)
        canvas_page_layout = QHBoxLayout(self.canvas_page)
        canvas_page_layout.setContentsMargins(0, 0, 0, 0)
        canvas_page_layout.setSpacing(0)

        self.canvas_splitter = QSplitter(Qt.Horizontal, self.canvas_page)
        self.canvas_splitter.setObjectName("ModelCanvasSplitter")
        self.canvas_splitter.setChildrenCollapsible(False)
        canvas_page_layout.addWidget(self.canvas_splitter, 1)

        self.page_stack = QStackedWidget(self.canvas_splitter)
        self.page_stack.setObjectName("ModelPageStack")
        self.page_stack.currentChanged.connect(self._handle_page_stack_current_changed)
        self.canvas_splitter.addWidget(self.page_stack)

        self.visual_side_panel = QFrame(self.canvas_splitter)
        self.visual_side_panel.setObjectName("ModelVisualSidePanel")
        self.visual_side_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.visual_side_panel.setMinimumWidth(260)
        self.visual_side_panel.setMaximumWidth(520)
        visual_side_layout = QVBoxLayout(self.visual_side_panel)
        visual_side_layout.setContentsMargins(8, 8, 8, 8)
        visual_side_layout.setSpacing(6)

        visual_tab_bar = QFrame(self.visual_side_panel)
        visual_tab_bar.setObjectName("ModelVisualPanelTabBar")
        visual_tab_layout = QHBoxLayout(visual_tab_bar)
        visual_tab_layout.setContentsMargins(4, 4, 4, 4)
        visual_tab_layout.setSpacing(4)
        self.visual_data_tab_btn = QPushButton(_rt("Adicionar dados"), visual_tab_bar)
        self.visual_data_tab_btn.setObjectName("ModelVisualPanelTabButton")
        self.visual_data_tab_btn.setCheckable(True)
        self.visual_data_tab_btn.setCursor(Qt.PointingHandCursor)
        self.visual_data_tab_btn.setToolTip("")
        self.visual_data_tab_btn.setStatusTip("")
        self.visual_data_tab_btn.setWhatsThis("")
        self.visual_data_tab_btn.clicked.connect(lambda checked=False: self._set_visual_side_tab("build"))
        visual_tab_layout.addWidget(self.visual_data_tab_btn, 1)
        self.visual_format_tab_btn = QPushButton(_rt("Formatar visual"), visual_tab_bar)
        self.visual_format_tab_btn.setObjectName("ModelVisualPanelTabButton")
        self.visual_format_tab_btn.setCheckable(True)
        self.visual_format_tab_btn.setCursor(Qt.PointingHandCursor)
        self.visual_format_tab_btn.setToolTip("")
        self.visual_format_tab_btn.setStatusTip("")
        self.visual_format_tab_btn.setWhatsThis("")
        self.visual_format_tab_btn.clicked.connect(lambda checked=False: self._set_visual_side_tab("format"))
        visual_tab_layout.addWidget(self.visual_format_tab_btn, 1)
        visual_side_layout.addWidget(visual_tab_bar, 0)

        self.visual_side_stack = QStackedWidget(self.visual_side_panel)
        self.visual_side_stack.setObjectName("ModelVisualSideStack")
        self.builder_panel = self._build_chart_builder_panel(self.visual_side_stack)
        self.visual_side_stack.addWidget(self.builder_panel)
        self.visual_panel = VisualFormatPanel(self.visual_side_stack)
        self.visual_panel.setMinimumWidth(240)
        self.visual_panel.setMaximumWidth(16777215)
        self.visual_panel.closeRequested.connect(lambda: self._set_visual_panel_open(False))
        self.visual_side_stack.addWidget(self.visual_panel)
        visual_side_layout.addWidget(self.visual_side_stack, 1)
        self._active_visual_side_tab = "build"
        self._sync_visual_side_tab_buttons()
        self._apply_visual_side_panel_styles()
        self.visual_side_panel.setVisible(False)
        self.canvas_splitter.addWidget(self.visual_side_panel)

        self.data_panel = self._build_data_panel(self.canvas_splitter)
        self.data_panel.setMinimumWidth(260)
        self.data_panel.setMaximumWidth(520)
        self.data_panel.setVisible(False)
        self.canvas_splitter.addWidget(self.data_panel)
        self.canvas_splitter.setStretchFactor(0, 1)
        self.canvas_splitter.setStretchFactor(1, 0)
        self.canvas_splitter.setStretchFactor(2, 0)
        self.canvas_splitter.setSizes([900, 292, 292])

        self.body_stack.addWidget(self.empty_page)
        self.body_stack.addWidget(self.canvas_page)

        self.footer_bar = QFrame(self)
        self.footer_bar.setObjectName("ModelFooterBar")
        self.footer_bar.setAttribute(Qt.WA_StyledBackground, True)
        self.footer_bar.setFixedHeight(42)
        self.footer_bar.setVisible(False)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(4, 3, 4, 3)
        footer_layout.setSpacing(6)

        self.page_strip = None
        footer_layout.addStretch(1)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ModelZoomLabel")
        footer_layout.addWidget(self.zoom_label, 0)
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setObjectName("ModelZoomButton")
        self.zoom_out_btn.setFixedSize(20, 16)
        footer_layout.addWidget(self.zoom_out_btn, 0)
        self.zoom_reset_btn = QPushButton("100%")
        self.zoom_reset_btn.setObjectName("ModelZoomButton")
        self.zoom_reset_btn.setFixedSize(40, 16)
        footer_layout.addWidget(self.zoom_reset_btn, 0)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setObjectName("ModelZoomSlider")
        self.zoom_slider.setRange(60, 200)
        self.zoom_slider.setSingleStep(5)
        self.zoom_slider.setPageStep(15)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFocusPolicy(Qt.NoFocus)
        footer_layout.addWidget(self.zoom_slider, 0)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("ModelZoomButton")
        self.zoom_in_btn.setFixedSize(20, 16)
        footer_layout.addWidget(self.zoom_in_btn, 0)
        root.addWidget(self.footer_bar, 0)

        self.new_btn.clicked.connect(self.new_project)
        self.open_btn.clicked.connect(self.open_project)
        self.save_btn.clicked.connect(self.save_project)
        self.save_as_btn.clicked.connect(lambda: self.save_project(save_as=True))
        self.export_btn.clicked.connect(self.export_project)
        self.undo_btn.clicked.connect(self._undo_last_action)
        self.redo_btn.clicked.connect(self._redo_last_action)
        self.create_chart_btn.toggled.connect(self._handle_create_chart_toggle)
        self.format_visual_btn.toggled.connect(self._handle_format_visual_toggle)
        self.settings_btn.clicked.connect(self._open_canvas_style_settings)
        self.zoom_out_btn.clicked.connect(self._zoom_canvas_out)
        self.zoom_reset_btn.clicked.connect(self._zoom_canvas_reset)
        self.zoom_in_btn.clicked.connect(self._zoom_canvas_in)
        self.zoom_slider.valueChanged.connect(self._zoom_slider_changed)
        self.edit_mode_btn.toggled.connect(self.set_edit_mode)
        self.mode_toggle.toggled.connect(self._handle_mode_toggle)
        self.close_project_btn.clicked.connect(self.close_project)
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.activated.connect(self._undo_last_action)
        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._shortcut_redo.activated.connect(self._redo_last_action)
        self._shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_redo_alt.activated.connect(self._redo_last_action)

        self.setStyleSheet(
            """
            QWidget#ModelTabRoot {
                background: #FFFFFF;
            }
            QFrame#ModelHeader {
                background: transparent;
                border: none;
            }
            QFrame#ModelToolbarStrip {
                background: #FFFFFF;
                border: 1px solid #D6D9E0;
                border-radius: 8px;
            }
            QFrame#ModelToolbarSeparator {
                min-width: 1px;
                max-width: 1px;
                margin: 4px 6px;
                background: #E5E7EB;
            }
            QWidget#ModelModeSwitchWrap {
                background: transparent;
            }
            QLabel#ModelModeStateLabel {
                color: #374151;
                font-size: 11px;
                font-weight: 400;
            }
            QLabel#ModelModeStateLabel[modeState="preview"] {
                color: #6B7280;
            }
            QWidget#ModelModeToggle {
                background: transparent;
            }
            QLabel#ModelHint,
            QLabel#ModelWelcomeText,
            QLabel#ModelRecentsPlaceholder {
                color: #6B7280;
                font-size: 12px;
            }
            QFrame#ModelFiltersBar {
                background: #F8FAFC;
                border: 1px solid #D6D9E0;
                border-radius: 12px;
            }
            QLabel#ModelFiltersLabel {
                color: #374151;
                font-size: 12px;
            }
            QFrame#ModelWelcomeCard,
            QFrame#ModelRecentsCard {
                background: #FFFFFF;
                border: 1px solid #D6D9E0;
                border-radius: 16px;
            }
            QFrame#ModelFooterBar {
                background: #FFFFFF;
                border-top: 1px solid #E5E7EB;
            }
            QWidget#ModelPageStrip {
                background: transparent;
            }
            QScrollArea#ModelPageStripScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#ModelPageStripContent {
                background: transparent;
            }
            QWidget#ModelPageStripTab {
                background: transparent;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                margin-right: 2px;
                color: #6B7280;
                font-size: 12px;
                font-weight: 500;
            }
            QWidget#ModelPageStripTab:hover {
                background: #F8FAFC;
                color: #111827;
            }
            QWidget#ModelPageStripTab[selected="true"] {
                color: #111827;
                font-weight: 600;
                border-bottom-color: #5B4CF0;
                background: transparent;
            }
            QLabel#ModelPageStripTabTitle {
                color: #6B7280;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#ModelPageStripTabTitle[selected="true"] {
                color: #111827;
                font-weight: 600;
            }
            QLineEdit#ModelPageStripTabEdit {
                min-height: 22px;
                border: 1px solid #818CF8;
                border-radius: 6px;
                padding: 0 6px;
                background: #FFFFFF;
                color: #111827;
                font-size: 12px;
            }
            QToolButton#ModelPageStripTabMenu,
            QToolButton#ModelPageStripTabClose,
            QToolButton#ModelPageStripNavButton {
                min-width: 16px;
                min-height: 16px;
                border: none;
                background: transparent;
                color: #6B7280;
                font-size: 12px;
                padding: 0px;
            }
            QToolButton#ModelPageStripTabMenu:hover,
            QToolButton#ModelPageStripTabClose:hover,
            QToolButton#ModelPageStripNavButton:hover {
                color: #111827;
                background: #F3F4F6;
                border-radius: 6px;
            }
            QToolButton#ModelPageStripAddButton {
                min-height: 24px;
                min-width: 66px;
                padding: 0 10px;
                color: #4B5563;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 500;
            }
            QToolButton#ModelPageStripAddButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
                color: #111827;
            }
            QToolButton#ModelPageStripAddButton:pressed {
                background: #E5E7EB;
            }
            QFrame#ModelBuilderPanel {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
            QFrame#ModelVisualSidePanel {
                background: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 6px;
            }
            QSplitter#ModelCanvasSplitter {
                background: transparent;
            }
            QSplitter#ModelCanvasSplitter::handle {
                background: transparent;
                width: 8px;
                margin: 0px 2px;
            }
            QSplitter#ModelCanvasSplitter::handle:hover {
                background: #E2E8F0;
            }
            QFrame#ModelVisualPanelTabBar {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }
            QStackedWidget#ModelVisualSideStack {
                background: transparent;
                border: none;
            }
            QPushButton#ModelVisualPanelTabButton {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
                color: #334155;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton#ModelVisualPanelTabButton:hover {
                background: #F8FAFC;
                border-color: #D7DEE8;
            }
            QPushButton#ModelVisualPanelTabButton:checked {
                background: #EAF4FF;
                border-color: #93C5FD;
            }
            QScrollArea#ModelBuilderScroll {
                border: none;
                background: transparent;
            }
            QWidget#ModelBuilderHost {
                background: transparent;
            }
            QLabel#ModelBuilderTitle {
                color: #0F172A;
                font-size: 14px;
                font-weight: 500;
            }
            QLabel#ModelBuilderHint {
                color: #64748B;
                font-size: 11px;
                font-weight: 400;
            }
            QFrame#ModelBuilderSection {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 6px;
            }
            QFrame#ModelBuilderPlainSection {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
            QFrame#ModelBuilderVisualsSection {
                background: #FFFFFF;
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 6px;
            }
            QFrame#ModelBuilderVisualsSection:hover {
                border-color: rgba(17, 24, 39, 0.14);
            }
            QFrame#ModelBuilderSoftDividerSection {
                background: #FFFFFF;
                border: 1px solid #E5EAF1;
                border-radius: 5px;
            }
            QFrame#ModelBuilderFieldsPanel {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 6px;
            }
            QFrame#ModelBuilderDataPanel {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 6px;
            }
            QFrame#ModelBuilderDataSection {
                background: transparent;
                border: none;
            }
            QFrame#ModelBuilderFieldsHeader {
                background: #FFFFFF;
                border: none;
                border-bottom: 1px solid rgba(15, 23, 42, 0.06);
            }
            QLabel#ModelBuilderSectionTitle {
                color: #0F172A;
                font-size: 12px;
                font-weight: 500;
            }
            QToolButton#ModelVisualTypeButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                color: #475569;
                padding: 0px;
                font-size: 10px;
                font-weight: 500;
            }
            QToolButton#ModelVisualTypeButton:hover {
                background: #F3F4F6;
                border-color: rgba(17, 24, 39, 0.10);
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #E8EEF6;
                color: #0F172A;
                border-color: rgba(17, 24, 39, 0.12);
            }
            QToolButton#ModelVisualTypeButton:checked:hover {
                background: #E8EEF6;
            }
            QFrame#ModelBuilderEmptyState {
                background: rgba(255, 255, 255, 0.88);
                border: 1px dashed rgba(17, 24, 39, 0.12);
                border-radius: 6px;
            }
            QLabel#ModelBuilderEmptyStateLabel {
                color: #64748B;
                font-size: 12px;
                font-weight: 400;
            }
            QListWidget#ModelBuilderFieldList {
                border: 1px solid rgba(17, 24, 39, 0.06);
                border-radius: 6px;
                background: #FFFFFF;
                color: #0F172A;
                padding: 4px;
                outline: 0;
                font-size: 12px;
            }
            QListWidget#ModelBuilderFieldList::item {
                padding: 2px 6px;
                margin: 0;
                border-radius: 2px;
            }
            QListWidget#ModelBuilderFieldList::item:hover {
                background: rgba(17, 24, 39, 0.035);
            }
            QListWidget#ModelBuilderFieldList::item:selected {
                background: rgba(81, 96, 116, 0.12);
                color: #111827;
            }
            QLabel#ModelBuilderFieldLabel {
                color: #6B7280;
                font-size: 11px;
                font-weight: 400;
            }
            QFrame#ModelBindingSlot {
                background: #F8FAFC;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 4px;
                min-height: 42px;
            }
            QFrame#ModelBindingSlot[filled="true"] {
                border-color: rgba(148, 163, 184, 0.36);
                background: #FFFFFF;
            }
            QFrame#ModelBindingSlot[dropActive="true"] {
                border-color: rgba(96, 165, 250, 0.45);
                background: rgba(239, 246, 255, 0.55);
            }
            QLabel#ModelBindingSlotLabel {
                color: #475569;
                font-size: 10px;
                font-weight: 500;
            }
            QFrame#ModelBindingSlotChips {
                background: transparent;
            }
            QFrame#ModelBindingFieldChip {
                background: #FFFFFF;
                border: 1px solid rgba(148, 163, 184, 0.42);
                border-radius: 3px;
            }
            QLabel#ModelBindingFieldBadge {
                background: #EEF2FF;
                color: #334155;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 2px;
                min-width: 26px;
                max-width: 34px;
                min-height: 16px;
                font-size: 8px;
                font-weight: 600;
            }
            QLabel#ModelBindingFieldName {
                color: #111827;
                font-size: 10px;
                font-weight: 400;
            }
            QLabel#ModelBindingSlotValue {
                color: #94A3B8;
                font-size: 10px;
                font-weight: 400;
            }
            QComboBox#ModelBindingAggregationCombo {
                min-height: 18px;
                max-height: 18px;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 2px;
                padding: 0 4px;
                background: #F8FAFC;
                color: #334155;
                font-size: 9px;
            }
            QToolButton#ModelBindingSlotRemove {
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                padding: 0;
            }
            QToolButton#ModelBindingSlotRemove:hover {
                background: rgba(239, 68, 68, 0.08);
                border-color: rgba(239, 68, 68, 0.20);
            }
            QToolButton#ModelBindingSlotMove {
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                color: #64748B;
                padding: 0;
                font-size: 9px;
            }
            QToolButton#ModelBindingSlotMove:hover {
                background: #F1F5F9;
                border-color: rgba(148, 163, 184, 0.24);
            }
            QComboBox#ModelBuilderCombo,
            QLineEdit#ModelBuilderLineEdit,
            QSpinBox#ModelBuilderSpin {
                min-height: 23px;
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 2px;
                padding: 2px 6px;
                background: rgba(255, 255, 255, 0.96);
                color: #111827;
                font-size: 11px;
            }
            QComboBox#ModelBuilderCombo:focus,
            QLineEdit#ModelBuilderLineEdit:focus,
            QSpinBox#ModelBuilderSpin:focus {
                border-color: rgba(81, 96, 116, 0.48);
            }
            QSpinBox#ModelBuilderSpin::up-button,
            QSpinBox#ModelBuilderSpin::down-button {
                width: 14px;
                background: #F8FAFC;
                border-left: 1px solid #E2E8F0;
            }
            QSpinBox#ModelBuilderSpin::up-button {
                border-top-right-radius: 6px;
                border-bottom: 1px solid #E2E8F0;
            }
            QSpinBox#ModelBuilderSpin::down-button {
                border-bottom-right-radius: 6px;
            }
            QSpinBox#ModelBuilderSpin::up-button:hover,
            QSpinBox#ModelBuilderSpin::down-button:hover {
                background: #EEF2F7;
            }
            QPushButton#ModelBuilderPrimaryButton {
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 2px;
                background: #FFFFFF;
                color: #111827;
                padding: 4px 8px;
                min-height: 24px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton#ModelBuilderPrimaryButton:hover {
                background: #FFFFFF;
                border-color: rgba(17, 24, 39, 0.12);
            }
            QLabel#ModelWelcomeTitle,
            QLabel#ModelRecentsTitle {
                color: #111827;
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#ModelZoomLabel {
                color: #6B7280;
                font-size: 9px;
                font-weight: 500;
            }
            QSlider#ModelZoomSlider {
                background: transparent;
                min-height: 10px;
            }
            QSlider#ModelZoomSlider::groove:horizontal {
                height: 2px;
                background: #E5E7EB;
                border-radius: 1px;
            }
            QSlider#ModelZoomSlider::sub-page:horizontal {
                background: #C7D2FE;
                border-radius: 1px;
            }
            QSlider#ModelZoomSlider::handle:horizontal {
                width: 8px;
                margin: -4px 0;
                border-radius: 3px;
                background: #6366F1;
                border: 1px solid #4F46E5;
            }
            QSlider#ModelZoomSlider::handle:horizontal:hover {
                background: #4F46E5;
            }
            QPushButton#ModelActionButton {
                min-height: 30px;
                padding: 0 12px;
                color: #374151;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                font-weight: 400;
            }
            QPushButton#ModelActionButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton#ModelActionButton:pressed {
                background: #E5E7EB;
            }
            QPushButton#ModelToolbarButton,
            QToolButton#ModelToolbarButton {
                min-height: 30px;
                padding: 0 4px;
                color: #111827;
                background: transparent;
                border: none;
                border-radius: 6px;
                font-weight: 400;
            }
            QPushButton#ModelToolbarButton:hover,
            QToolButton#ModelToolbarButton:hover {
                background: #F3F4F6;
            }
            QPushButton#ModelToolbarButton:checked,
            QToolButton#ModelToolbarButton:checked {
                background: #E8EEF6;
                color: #111827;
            }
            QPushButton#ModelToolbarButton:pressed,
            QToolButton#ModelToolbarButton:pressed {
                background: #E5E7EB;
            }
            QPushButton#ModelToolbarButton[toolbarMode="icon"],
            QToolButton#ModelToolbarButton[toolbarMode="icon"] {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
            }
            QPushButton#ModelToolbarButton[toolbarMode="label"] {
                min-width: 78px;
                max-width: 78px;
                min-height: 30px;
                max-height: 30px;
                padding: 0 10px;
                text-align: left;
            }
            QPushButton#ModelZoomButton {
                min-height: 16px;
                color: #374151;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 5px;
                font-size: 9px;
                font-weight: 500;
                padding: 0;
            }
            QPushButton#ModelZoomButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton#ModelZoomButton:pressed {
                background: #E5E7EB;
            }
            QFrame#ModelActionCard,
            QFrame#ModelRecentCard {
                background: #FFFFFF;
                border: 1px solid #C9D2E3;
                border-radius: 14px;
            }
            QFrame#ModelActionCard:hover,
            QFrame#ModelRecentCard:hover {
                background: #F8FAFC;
                border-color: #94A3B8;
            }
            QLabel#ModelActionCardIcon {
                background: #EEF2FF;
                border: 1px solid #C7D2FE;
                border-radius: 10px;
            }
            QLabel#ModelActionCardTitle,
            QLabel#ModelRecentCardTitle {
                color: #111827;
                font-size: 13px;
                font-weight: 400;
            }
            QLabel#ModelActionCardText,
            QLabel#ModelRecentCardText {
                color: #6B7280;
                font-size: 12px;
                font-weight: 400;
            }
            """
        )

        self._refresh_recents()
        self._refresh_builder_layers()
        self._sync_mode_switch_state(bool(self.edit_mode_btn.isChecked()))
        self._refresh_ui_state()
        self._reset_history()
        project = QgsProject.instance()
        try:
            project.layersAdded.connect(lambda *_: self._refresh_builder_layers())
            project.layersRemoved.connect(lambda *_: self._refresh_builder_layers())
            project.layerWillBeRemoved.connect(lambda *_: self._refresh_builder_layers())
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_visual_side_panel_styles(self):
        self.visual_side_panel.setStyleSheet(
            """
            QFrame#ModelVisualSidePanel {
                background: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 6px;
            }
            QFrame#ModelVisualPanelTabBar {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }
            QPushButton#ModelVisualPanelTabButton {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
                color: #334155;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton#ModelVisualPanelTabButton:hover {
                background: #F8FAFC;
                border-color: #D7DEE8;
            }
            QPushButton#ModelVisualPanelTabButton:checked {
                background: #EAF4FF;
                border-color: #93C5FD;
            }
            QFrame#ModelBuilderPanel {
                background: transparent;
                border: none;
            }
            QScrollArea#ModelBuilderScroll,
            QWidget#ModelBuilderHost {
                background: transparent;
                border: none;
            }
            QFrame#ModelBuilderPlainSection {
                background: transparent;
                border: none;
            }
            QFrame#ModelBuilderVisualsSection {
                background: #FFFFFF;
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 6px;
            }
            QFrame#ModelBuilderVisualsSection:hover {
                border-color: rgba(17, 24, 39, 0.14);
            }
            QFrame#ModelBuilderSoftDividerSection {
                background: #FFFFFF;
                border: 1px solid #E5EAF1;
                border-radius: 5px;
            }
            QToolButton#ModelVisualTypeButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: #475569;
                padding: 0px;
            }
            QToolButton#ModelVisualTypeButton:hover {
                background: #F3F4F6;
                border-color: rgba(17, 24, 39, 0.10);
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #E8EEF6;
                color: #0F172A;
                border-color: rgba(17, 24, 39, 0.12);
            }
            QFrame#ModelBindingSlot {
                background: #F8FAFC;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 4px;
                min-height: 42px;
            }
            QFrame#ModelBindingSlot[filled="true"] {
                border-color: rgba(148, 163, 184, 0.36);
                background: #FFFFFF;
            }
            QFrame#ModelBindingFieldChip {
                background: #FFFFFF;
                border: 1px solid rgba(148, 163, 184, 0.42);
                border-radius: 3px;
            }
            QLabel#ModelBindingFieldBadge {
                background: #EEF2FF;
                color: #334155;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 2px;
                min-width: 26px;
                max-width: 34px;
                min-height: 16px;
                font-size: 8px;
                font-weight: 600;
            }
            QLabel#ModelBindingFieldName,
            QLabel#ModelBindingSlotValue,
            QLabel#ModelBindingSlotLabel {
                font-size: 10px;
            }
            """
        )

    def _build_chart_builder_panel(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("ModelBuilderPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        scroll = QScrollArea(panel)
        scroll.setObjectName("ModelBuilderScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(scroll, 1)

        host = QWidget(scroll)
        host.setObjectName("ModelBuilderHost")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)
        scroll.setWidget(host)

        visuals_card = QFrame(panel)
        visuals_card.setObjectName("ModelBuilderVisualsSection")
        visuals_card.setAttribute(Qt.WA_StyledBackground, True)
        visuals_card.setStyleSheet(
            """
            QFrame#ModelBuilderVisualsSection {
                background: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 6px;
            }
            QFrame#ModelBuilderVisualsSection:hover {
                border-color: #CBD5E1;
            }
            QToolButton#ModelVisualTypeButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                color: #475569;
                padding: 0px;
            }
            QToolButton#ModelVisualTypeButton:hover {
                background: #F3F4F6;
                border-color: #D7DEE8;
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #E8EEF6;
                border-color: #CBD5E1;
                color: #0F172A;
            }
            """
        )
        visuals_layout = QVBoxLayout(visuals_card)
        visuals_layout.setContentsMargins(8, 8, 8, 8)
        visuals_layout.setSpacing(6)
        visuals_title = QLabel(_rt("Visualizações"), visuals_card)
        visuals_title.setObjectName("ModelBuilderSectionTitle")
        visuals_layout.addWidget(visuals_title, 0)
        visuals_grid = QGridLayout()
        visuals_grid.setContentsMargins(0, 0, 0, 0)
        visuals_grid.setHorizontalSpacing(4)
        visuals_grid.setVerticalSpacing(4)
        self._builder_visual_specs = [
            (_rt("Colunas"), "bar", "ModelVisual-Column.svg", _rt("Colunas - compara valores por categoria.")),
            (_rt("Barras"), "barh", "ModelVisual-Bar.svg", _rt("Barras - compara categorias em eixo horizontal.")),
            (_rt("Linha"), "line", "ModelVisual-Line.svg", _rt("Linha - mostra tendência ao longo do tempo.")),
            (_rt("Area"), "area", "ModelVisual-Area.svg", _rt("Area - destaca a evolução acumulada dos valores.")),
            (_rt("Pizza"), "pie", "ModelVisual-Pie.svg", _rt("Pizza - mostra composição entre partes.")),
            (_rt("Rosca"), "donut", "ModelVisual-Donut.svg", _rt("Rosca - composição com foco no total.")),
            (_rt("Card"), "card", "ModelVisual-Card.svg", _rt("Card - destaca um único indicador.")),
            (_rt("KPI"), "kpi", "ModelVisual-KPI.svg", _rt("KPI - acompanha um indicador principal.")),
            (_rt("Medidor"), "gauge", "ModelVisual-Gauge.svg", _rt("Medidor - mostra progresso em relação a uma meta.")),
            (_rt("Matriz"), "matrix", "ModelVisual-Matrix.svg", _rt("Matriz - cruza linhas, colunas e valores.")),
            (_rt("Segmentador"), "slicer", "ModelVisual-Slicer.svg", _rt("Segmentador - lista categorias para filtragem visual.")),
            (_rt("Coluna agrupada"), "column_clustered", "ModelVisual-ColumnClustered.svg", _rt("Coluna agrupada - compara séries lado a lado.")),
            (_rt("Coluna empilhada"), "column_stacked", "ModelVisual-ColumnStacked.svg", _rt("Coluna empilhada - mostra partes dentro de cada coluna.")),
            (_rt("Barra 100%"), "bar100_stacked", "ModelVisual-Bar100Stacked.svg", _rt("Barra 100% - compara proporções entre categorias.")),
            (_rt("Combo"), "combo", "ModelVisual-Combo.svg", _rt("Combo - combina barras e linha no mesmo visual.")),
            (_rt("Dispersao"), "scatter", "ModelVisual-Scatter.svg", _rt("Dispersão - compara X, Y e tamanho.")),
            (_rt("Treemap"), "treemap", "ModelVisual-Treemap.svg", _rt("Treemap - mostra participação por áreas.")),
            (_rt("Cascata"), "waterfall", "ModelVisual-Waterfall.svg", _rt("Cascata - destaca variações positivas e negativas.")),
            (_rt("Funil"), "funnel", "ModelVisual-Funnel.svg", _rt("Funil - mostra etapas em sequência.")),
        ]
        self.builder_visual_buttons = {}
        for index, (label_text, chart_type, icon_name, tooltip_text) in enumerate(self._builder_visual_specs):
            button = QToolButton(visuals_card)
            button.setObjectName("ModelVisualTypeButton")
            button.setCheckable(True)
            button.setText("")
            button.setIcon(svg_icon(icon_name))
            button.setToolTip(label_text)
            button.setStatusTip("")
            button.setWhatsThis("")
            button.setAccessibleName(label_text)
            button.setAccessibleDescription(tooltip_text)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setAutoRaise(True)
            button.setFixedSize(30, 28)
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, value=chart_type: self._select_visual_type_from_builder(value))
            button.setProperty("visualType", chart_type)
            self.builder_visual_buttons[chart_type] = button
            visuals_grid.addWidget(button, index // 6, index % 6)
        visuals_layout.addLayout(visuals_grid)
        host_layout.addWidget(visuals_card, 0)

        self.builder_empty_label = QFrame(panel)
        self.builder_empty_label.setObjectName("ModelBuilderEmptyState")
        empty_layout = QVBoxLayout(self.builder_empty_label)
        empty_layout.setContentsMargins(8, 6, 8, 6)
        empty_layout.setSpacing(0)
        empty_text = QLabel(_rt("Selecione um visual para configurar os campos e as opções."), self.builder_empty_label)
        empty_text.setObjectName("ModelBuilderEmptyStateLabel")
        empty_text.setWordWrap(True)
        empty_layout.addWidget(empty_text)
        host_layout.addWidget(self.builder_empty_label, 0)

        self.builder_construct_card = QFrame(panel)
        self.builder_construct_card.setObjectName("ModelBuilderSoftDividerSection")
        construct_layout = QVBoxLayout(self.builder_construct_card)
        construct_layout.setContentsMargins(8, 8, 8, 8)
        construct_layout.setSpacing(6)
        construct_title = QLabel(_rt("Construir visual"), self.builder_construct_card)
        construct_title.setObjectName("ModelBuilderSectionTitle")
        construct_layout.addWidget(construct_title, 0)
        self.builder_selected_visual_label = QLabel(_rt("Nenhum visual selecionado"), self.builder_construct_card)
        self.builder_selected_visual_label.setObjectName("ModelBuilderHint")
        self.builder_selected_visual_label.setWordWrap(True)
        construct_layout.addWidget(self.builder_selected_visual_label, 0)
        self._builder_selection_widgets = []

        self.builder_binding_slots = {}
        for slot_name, slot_label in (
            (ROLE_X_AXIS, _rt("Eixo X")),
            (ROLE_Y_AXIS, _rt("Eixo Y")),
            (ROLE_VALUES, _rt("Valores")),
            (ROLE_LEGEND, _rt("Legenda")),
            (ROLE_TOOLTIP, _rt("Tooltip")),
            (ROLE_FILTERS, _rt("Filtros")),
            (ROLE_SIZE, _rt("Tamanho")),
        ):
            slot = _ModelBindingSlot(slot_name, slot_label, self.builder_construct_card)
            slot.fieldDropped.connect(self._apply_dropped_field_to_selected_visual)
            slot.removeRequested.connect(self._remove_selected_visual_slot_field)
            slot.aggregationChanged.connect(self._change_selected_visual_slot_aggregation)
            slot.moveRequested.connect(self._move_selected_visual_slot_field)
            self.builder_binding_slots[slot_name] = slot
            construct_layout.addWidget(slot, 0)
            self._builder_selection_widgets.append(slot)

        host_layout.addWidget(self.builder_construct_card, 0)

        self.builder_format_card = QFrame(panel)
        self.builder_format_card.setObjectName("ModelBuilderSoftDividerSection")
        format_layout = QVBoxLayout(self.builder_format_card)
        format_layout.setContentsMargins(8, 8, 8, 8)
        format_layout.setSpacing(6)
        format_title = QLabel(_rt("Opções de dados"), self.builder_format_card)
        format_title.setObjectName("ModelBuilderSectionTitle")
        format_layout.addWidget(format_title, 0)

        options_form = QFormLayout()
        options_form.setContentsMargins(0, 2, 0, 0)
        options_form.setSpacing(5)
        options_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        options_form.setFormAlignment(Qt.AlignTop)
        options_form.setHorizontalSpacing(6)

        self.builder_option_labels = {}

        def add_selected_row(text: str, widget: QWidget, key: str = ""):
            label = QLabel(text, self.builder_format_card)
            label.setObjectName("ModelBuilderFieldLabel")
            options_form.addRow(label, widget)
            if key:
                self.builder_option_labels[key] = label
            self._builder_selection_widgets.extend([label, widget])

        self.builder_agg_combo = QComboBox(panel)
        self.builder_agg_combo.setObjectName("ModelBuilderCombo")
        self.builder_agg_combo.addItem(_rt("Contagem"), "count")
        self.builder_agg_combo.addItem(_rt("Soma"), "sum")
        self.builder_agg_combo.addItem(_rt("Media"), "avg")
        self.builder_agg_combo.addItem(_rt("Minimo"), "min")
        self.builder_agg_combo.addItem(_rt("Maximo"), "max")
        self.builder_agg_combo.addItem(_rt("Contagem distinta"), "count_distinct")
        add_selected_row(_rt("Agregacao"), self.builder_agg_combo, "aggregation")

        self.builder_topn_spin = QSpinBox(panel)
        self.builder_topn_spin.setObjectName("ModelBuilderSpin")
        self.builder_topn_spin.setRange(1, 50)
        self.builder_topn_spin.setValue(12)
        add_selected_row(_rt("Top N"), self.builder_topn_spin, "top_n")

        self.builder_title_edit = QLineEdit(panel)
        self.builder_title_edit.setObjectName("ModelBuilderLineEdit")
        self.builder_title_edit.setPlaceholderText(_rt("Titulo do grafico (opcional)"))
        add_selected_row(_rt("Titulo"), self.builder_title_edit, "title")
        format_layout.addLayout(options_form)
        self._builder_selection_widgets.extend([self.builder_agg_combo, self.builder_topn_spin, self.builder_title_edit])

        host_layout.addWidget(self.builder_format_card, 0)

        self.builder_dimension_combo = QComboBox(panel)
        self.builder_dimension_combo.setObjectName("ModelBuilderCombo")
        self.builder_value_combo = QComboBox(panel)
        self.builder_value_combo.setObjectName("ModelBuilderCombo")
        self.builder_dimension_combo.hide()
        self.builder_value_combo.hide()
        self.builder_empty_label.setVisible(True)
        self.builder_construct_card.setVisible(False)
        self.builder_format_card.setVisible(False)
        host_layout.addStretch(1)

        self.builder_value_combo.currentIndexChanged.connect(self._on_builder_value_changed)
        self.builder_agg_combo.currentIndexChanged.connect(self._update_selected_visual_binding_controls)
        self.builder_topn_spin.valueChanged.connect(self._update_selected_visual_binding_controls)
        self.builder_title_edit.editingFinished.connect(self._update_selected_visual_binding_controls)
        for slot in self.builder_binding_slots.values():
            slot.set_value("")
        return panel

    def _build_data_panel(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("ModelBuilderDataPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setStyleSheet(
            """
            QFrame#ModelBuilderDataPanel {
                background: #FFFFFF;
                border: 1px solid rgba(17, 24, 39, 0.09);
                border-radius: 2px;
            }
            QFrame#ModelBuilderDataSection {
                background: transparent;
                border: none;
            }
            QComboBox#ModelBuilderCombo {
                min-height: 28px;
                border: 1px solid rgba(17, 24, 39, 0.09);
                border-radius: 6px;
                background: #FFFFFF;
                padding: 3px 8px;
                color: #111827;
                font-size: 12px;
            }
            QListWidget#ModelBuilderFieldList {
                border: 1px solid rgba(17, 24, 39, 0.09);
                border-radius: 2px;
                background: rgba(255, 255, 255, 0.96);
                padding: 2px;
                color: #111827;
                font-size: 12px;
                outline: 0px;
            }
            QListWidget#ModelBuilderFieldList::item {
                padding: 4px 6px;
                margin: 0px;
                border-radius: 2px;
            }
            QListWidget#ModelBuilderFieldList::item:hover {
                background: rgba(17, 24, 39, 0.035);
            }
            QListWidget#ModelBuilderFieldList::item:selected {
                background: rgba(81, 96, 116, 0.12);
                color: #111827;
            }
            QListWidget#ModelBuilderFieldList QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px 0px;
            }
            QListWidget#ModelBuilderFieldList QScrollBar::handle:vertical {
                background: rgba(107, 114, 128, 0.28);
                border-radius: 5px;
                min-height: 24px;
            }
            QListWidget#ModelBuilderFieldList QScrollBar::handle:vertical:hover {
                background: rgba(107, 114, 128, 0.40);
            }
            QListWidget#ModelBuilderFieldList QScrollBar::add-line:vertical,
            QListWidget#ModelBuilderFieldList QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QListWidget#ModelBuilderFieldList QScrollBar::add-page:vertical,
            QListWidget#ModelBuilderFieldList QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QLabel#ModelBuilderTitle {
                color: #4B5563;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#ModelBuilderFieldLabel {
                color: #6B7280;
                font-size: 11px;
                font-weight: 500;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        title = QLabel(_rt("Painel dados"), panel)
        title.setObjectName("ModelBuilderTitle")
        header.addWidget(title, 1, Qt.AlignVCenter)
        layout.addLayout(header, 0)

        layer_card = QFrame(panel)
        layer_card.setObjectName("ModelBuilderDataSection")
        layer_layout = QHBoxLayout(layer_card)
        layer_layout.setContentsMargins(0, 0, 0, 0)
        layer_layout.setSpacing(8)
        layer_title = QLabel(_rt("Camada"), layer_card)
        layer_title.setObjectName("ModelBuilderFieldLabel")
        layer_layout.addWidget(layer_title, 0, Qt.AlignVCenter)
        self.builder_layer_combo = QgsMapLayerComboBox(panel)
        self.builder_layer_combo.setObjectName("ModelBuilderCombo")
        self.builder_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.builder_layer_combo.layerChanged.connect(self._on_builder_layer_changed)
        layer_layout.addWidget(self.builder_layer_combo, 1)
        layout.addWidget(layer_card, 0)

        fields_card = QFrame(panel)
        fields_card.setObjectName("ModelBuilderDataSection")
        fields_layout = QVBoxLayout(fields_card)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(0)
        fields_body = QWidget(fields_card)
        fields_body_layout = QVBoxLayout(fields_body)
        fields_body_layout.setContentsMargins(0, 4, 0, 0)
        fields_body_layout.setSpacing(0)
        self.builder_fields_list = _ModelFieldList(fields_body)
        self.builder_fields_list.setObjectName("ModelBuilderFieldList")
        self.builder_fields_list.setMinimumHeight(220)
        self.builder_fields_list.setUniformItemSizes(True)
        self.builder_fields_list.setSpacing(1)
        self.builder_fields_list.setIconSize(QSize(16, 16))
        self.builder_fields_list.fieldActivated.connect(self._handle_field_list_activation)
        fields_body_layout.addWidget(self.builder_fields_list, 1)
        fields_layout.addWidget(fields_body, 1)
        layout.addWidget(fields_card, 1)

        return panel

    def _field_is_numeric(self, field_def) -> bool:
        if field_def is None:
            return False
        try:
            return bool(field_def.isNumeric())
        except Exception:
            log_exception("falha opcional ignorada")
        type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
        return any(token in type_name for token in ("int", "double", "float", "real", "numeric", "decimal"))

    def _field_is_date_like(self, field_def) -> bool:
        if field_def is None:
            return False
        type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
        return any(token in type_name for token in ("date", "time"))

    def _field_group_for_def(self, field_def) -> str:
        if self._field_is_numeric(field_def):
            return "measure"
        if self._field_is_date_like(field_def):
            return "date"
        type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
        if any(token in type_name for token in ("string", "text", "char")):
            return "dimension"
        return "other"

    def _suggested_role_for_group(self, group: str) -> str:
        mapping = {
            "dimension": ROLE_X_AXIS,
            "measure": ROLE_VALUES,
            "date": ROLE_X_AXIS,
            "other": ROLE_TOOLTIP,
        }
        return mapping.get(str(group or "").strip().lower(), ROLE_X_AXIS)

    def _slot_values_for_binding(self, binding: DashboardChartBinding, slot_name: str) -> List[FieldBindingItem]:
        role = normalize_binding_role(slot_name)
        return list(binding.normalized().bindings.get(role) or [])

    def _chart_type_label(self, chart_type: str) -> str:
        labels = {
            "card": _rt("Card"),
            "kpi": _rt("KPI"),
            "gauge": _rt("Medidor"),
            "bar": _rt("Colunas"),
            "barh": _rt("Barras"),
            "line": _rt("Linha"),
            "area": _rt("Area"),
            "pie": _rt("Pizza"),
            "donut": _rt("Rosca"),
            "scatter": _rt("Dispersao"),
            "matrix": _rt("Matriz"),
            "slicer": _rt("Segmentador"),
            "column_clustered": _rt("Coluna agrupada"),
            "column_stacked": _rt("Coluna empilhada"),
            "bar100_stacked": _rt("Barra 100%"),
            "combo": _rt("Combo"),
            "treemap": _rt("Treemap"),
            "waterfall": _rt("Cascata"),
            "funnel": _rt("Funil"),
        }
        return labels.get(str(chart_type or "").strip().lower(), _rt("Grafico"))

    def _empty_chart_payload(self, chart_type: str, title: str = "") -> ChartPayload:
        return ChartPayload.build(
            chart_type=str(chart_type or "bar"),
            title=str(title or ""),
            categories=[],
            values=[],
            value_label=_rt("Valor"),
        )

    def _selected_canvas_item(self) -> Optional[DashboardChartItem]:
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return None
        return active_canvas.selected_item()

    def _selected_canvas_item_widget(self):
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return None
        return active_canvas.selected_item_widget()

    def _replace_canvas_item(self, updated_item: DashboardChartItem, *, page_id: Optional[str] = None, select: bool = True):
        active_widget = self._active_page_widget()
        if active_widget is None:
            return
        if page_id and str(active_widget.page_id or "").strip() != str(page_id or "").strip():
            active_widget = self._page_widget_for_id(page_id)
        if active_widget is None:
            return
        canvas = active_widget.canvas
        items = canvas.items()
        replaced = False
        for index, item in enumerate(items):
            if str(item.item_id or "") == str(updated_item.item_id or ""):
                items[index] = updated_item.clone()
                replaced = True
                break
        if not replaced:
            return
        canvas.update_items(items, canvas.visual_links(), canvas.chart_relations())
        if select:
            canvas.select_item(updated_item.item_id, emit_signal=True)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _create_blank_visual_from_type(self, chart_type: str):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        item_id = uuid.uuid4().hex
        binding = DashboardChartBinding(
            chart_id=item_id,
            chart_type=str(chart_type or "bar").strip().lower(),
            aggregation="count",
            top_n=max(1, int(self.builder_topn_spin.value() or 12)),
        ).normalized()
        title = self._chart_type_label(chart_type)
        item = DashboardChartItem(
            item_id=item_id,
            origin="model_builder_v2",
            payload=self._empty_chart_payload(chart_type, title=""),
            visual_state=ChartVisualState(chart_type=str(chart_type or "bar").strip().lower()),
            binding=binding,
            title="",
            subtitle=_rt("Arraste campos para configurar este visual"),
            source_meta={"builder_version": "v2", "empty_visual": True},
        )
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()
        self._set_builder_panel_open(True, focus=False)
        self._sync_builder_selection_state()

    def _select_visual_type_from_builder(self, chart_type: str):
        normalized_type = normalize_chart_type(chart_type)
        item = self._selected_canvas_item()
        if item is None:
            self._create_blank_visual_from_type(normalized_type)
            return
        binding = item.binding.normalized()
        binding.chart_type = normalized_type
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is None:
            return
        updated_item.visual_state.chart_type = normalized_type
        self._replace_canvas_item(updated_item, select=True)
        self._set_builder_panel_open(True, focus=False)
        self._sync_builder_selection_state()

    def _field_catalog_for_layer(self, layer: Optional[QgsVectorLayer]) -> Dict[str, List[Dict[str, str]]]:
        catalog = {"all": []}
        if layer is None:
            return catalog
        try:
            field_defs = list(layer.fields())
        except Exception:
            field_defs = []
        for field_def in field_defs:
            field_name = str(field_def.name() or "").strip()
            if not field_name:
                continue
            group = self._field_group_for_def(field_def)
            type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip()
            field_kind = field_kind_from_field_def(field_def)
            catalog["all"].append(
                {
                    "layer_name": layer.name(),
                    "layer_id": layer.id(),
                    "field_name": field_name,
                    "field_type": type_name,
                    "field_kind": field_kind,
                    "field_group": group,
                    "suggested_role": self._suggested_role_for_group(group),
                }
            )
        return catalog

    def _refresh_builder_field_lists(self, layer: Optional[QgsVectorLayer]):
        self._builder_field_catalog = self._field_catalog_for_layer(layer)
        self.builder_fields_list.clear()
        for payload in list(self._builder_field_catalog.get("all") or []):
            label = str(payload.get("field_name") or "")
            field_kind = str(payload.get("field_kind") or "other")
            tooltip = _rt("{name}\nTipo: {kind}", name=label, kind=str(payload.get("field_type") or field_kind).strip() or field_kind)
            item = QListWidgetItem()
            configure_field_item(
                item,
                display_name=label,
                kind=field_kind,
                tooltip=tooltip,
                payload=dict(payload),
                role=_MODEL_FIELD_ROLE,
                include_badge=True,
            )
            self.builder_fields_list.addItem(item)

    def _active_selected_binding(self) -> Optional[DashboardChartBinding]:
        item = self._selected_canvas_item()
        if item is None:
            return None
        return item.binding.normalized()

    def _sync_builder_selection_state(self):
        item = self._selected_canvas_item()
        binding = item.binding.normalized() if item is not None else None
        if item is None or binding is None:
            self._builder_selected_item_id = ""
            if hasattr(self, "builder_empty_label"):
                self.builder_empty_label.setVisible(True)
            if hasattr(self, "builder_construct_card"):
                self.builder_construct_card.setVisible(False)
            if hasattr(self, "builder_format_card"):
                self.builder_format_card.setVisible(False)
            self.builder_selected_visual_label.setText(_rt("Selecione um visual para começar."))
            for button in self.builder_visual_buttons.values():
                button.blockSignals(True)
                button.setChecked(False)
                button.blockSignals(False)
            for widget in list(getattr(self, "_builder_selection_widgets", []) or []):
                widget.setVisible(False)
            for slot in self.builder_binding_slots.values():
                slot.set_value("")
            self.builder_agg_combo.setEnabled(False)
            self.builder_topn_spin.setEnabled(False)
            self.builder_title_edit.setEnabled(False)
            return
        self._builder_selected_item_id = str(item.item_id or "")
        if hasattr(self, "builder_empty_label"):
            self.builder_empty_label.setVisible(False)
        if hasattr(self, "builder_construct_card"):
            self.builder_construct_card.setVisible(True)
        if hasattr(self, "builder_format_card"):
            self.builder_format_card.setVisible(True)
        active_chart_type = normalize_chart_type(binding.chart_type or getattr(item.visual_state, "chart_type", ""))
        layer_name = binding.source_name or _rt("Sem camada")
        visual_label = self._chart_type_label(binding.chart_type or getattr(item.visual_state, "chart_type", "bar"))
        self.builder_selected_visual_label.setText(_rt("{visual} · {layer}", visual=visual_label, layer=layer_name))
        for widget in list(getattr(self, "_builder_selection_widgets", []) or []):
            widget.setVisible(True)
        slot_defs = binding_slot_definitions(binding.chart_type or getattr(item.visual_state, "chart_type", "bar"))
        visible_slots = {str(slot.get("name") or "") for slot in slot_defs}
        labels_by_slot = {str(slot.get("name") or ""): str(slot.get("label") or "") for slot in slot_defs}
        for slot_name, slot in self.builder_binding_slots.items():
            slot.setVisible(slot_name in visible_slots)
            if slot_name in visible_slots:
                label = labels_by_slot.get(slot_name) or slot_name
                slot.set_label(_rt(label))
                slot.set_values(
                    self._slot_values_for_binding(binding, slot_name),
                    placeholder=_rt("Opcional"),
                    source_item_id=item.item_id,
                )
        self.builder_agg_combo.setEnabled(True)
        self.builder_topn_spin.setEnabled(True)
        self.builder_title_edit.setEnabled(True)
        self.builder_agg_combo.setVisible(True)
        label = self.builder_option_labels.get("aggregation")
        if label is not None:
            label.setVisible(True)
        topn_visible = active_chart_type not in {"card", "kpi", "gauge", "scatter"}
        self.builder_topn_spin.setVisible(topn_visible)
        label = self.builder_option_labels.get("top_n")
        if label is not None:
            label.setVisible(topn_visible)
        label = self.builder_option_labels.get("title")
        if label is not None:
            label.setVisible(True)
        agg_index = self.builder_agg_combo.findData(binding.aggregation or "count")
        if agg_index < 0:
            agg_index = self.builder_agg_combo.findData("count")
        self.builder_agg_combo.blockSignals(True)
        self.builder_agg_combo.setCurrentIndex(max(0, agg_index))
        self.builder_agg_combo.blockSignals(False)
        self.builder_topn_spin.blockSignals(True)
        self.builder_topn_spin.setValue(max(1, int(binding.top_n or 12)))
        self.builder_topn_spin.blockSignals(False)
        self.builder_title_edit.blockSignals(True)
        self.builder_title_edit.setText(str(binding.title_override or item.title or ""))
        self.builder_title_edit.blockSignals(False)
        for chart_type, button in self.builder_visual_buttons.items():
            button.blockSignals(True)
            button.setChecked(chart_type == active_chart_type)
            button.blockSignals(False)

    def _selected_layer(self) -> Optional[QgsVectorLayer]:
        return self._current_builder_layer()

    def _current_builder_layer(self) -> Optional[QgsVectorLayer]:
        try:
            layer = self.builder_layer_combo.currentLayer()
        except Exception:
            layer = None
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            return layer
        layer_id = str(getattr(self.builder_layer_combo, "currentData", lambda: "")() or "")
        return self._builder_layers.get(layer_id)

    def _current_builder_layer_id(self) -> str:
        layer = self._current_builder_layer()
        if layer is not None:
            return str(layer.id() or "")
        return ""

    def _current_builder_chart_type(self) -> str:
        item = self._selected_canvas_item()
        if item is not None:
            binding = item.binding.normalized() if item.binding is not None else None
            selected_type = normalize_chart_type(
                (binding.chart_type if binding is not None else "")
                or getattr(item.visual_state, "chart_type", "")
            )
            if selected_type:
                return selected_type
        for chart_type, button in getattr(self, "builder_visual_buttons", {}).items():
            try:
                if button.isChecked():
                    return normalize_chart_type(chart_type)
            except Exception:
                log_exception("falha opcional ignorada")
        return "bar"

    def _field_binding_item_from_payload(self, role: str, payload: Dict[str, object], order: int = 0) -> Optional[FieldBindingItem]:
        field_name = str(payload.get("field_name") or payload.get("field") or "").strip()
        if not field_name:
            return None
        field_kind = normalize_field_kind(str(payload.get("field_kind") or payload.get("field_group") or "unknown"))
        aggregation = normalize_aggregation("", field_kind, role)
        return FieldBindingItem(
            field=field_name,
            display_name=str(payload.get("display_name") or field_name).strip() or field_name,
            type=field_kind,
            aggregation=aggregation,
            role=role,
            order=order,
        ).normalized(role, order)

    def _apply_field_payload_to_binding(self, binding: DashboardChartBinding, slot_name: str, payload: Dict[str, object]) -> DashboardChartBinding:
        slot_name = normalize_binding_role(slot_name)
        field_name = str(payload.get("field_name") or "").strip()
        field_group = str(payload.get("field_group") or "other").strip().lower() or "other"
        layer_id = str(payload.get("layer_id") or "").strip()
        layer_name = str(payload.get("layer_name") or "").strip()
        source_slot = normalize_binding_role(str(payload.get("source_slot") or "").strip())
        source_item_id = str(payload.get("source_item_id") or "").strip()
        if not field_name:
            return binding.normalized()
        updated = binding.normalized()
        updated.source_id = layer_id or updated.source_id
        updated.source_name = layer_name or updated.source_name
        if not updated.chart_type:
            updated.chart_type = "bar"
        if not slot_name or slot_name == "auto":
            slot_name = suggest_binding_slot(updated.chart_type, field_group, updated)
        if not slot_name or not is_binding_slot_compatible(updated.chart_type, slot_name, field_group):
            self.builder_selected_visual_label.setText(_rt("Campo incompativel com este slot"))
            return updated.normalized()
        current_bindings = {
            role: [item.normalized(role, index) for index, item in enumerate(list(items or []))]
            for role, items in dict(updated.bindings or {}).items()
        }
        if source_slot and source_item_id and source_item_id == str(updated.chart_id or "") and source_slot != slot_name:
            current_bindings[source_slot] = [
                item.normalized(source_slot, index)
                for index, item in enumerate(list(current_bindings.get(source_slot) or []))
                if item.field != field_name
            ]
        role_items = list(current_bindings.get(slot_name) or [])
        item = self._field_binding_item_from_payload(slot_name, payload, len(role_items))
        if item is None:
            return updated.normalized()
        if any(existing.field.lower() == item.field.lower() for existing in role_items):
            return updated.normalized()
        slot_def = next((slot for slot in binding_slot_definitions(updated.chart_type) if str(slot.get("name") or "") == slot_name), {})
        if not bool(slot_def.get("multiple", True)):
            role_items = []
        role_items.append(item)
        current_bindings[slot_name] = role_items
        updated.bindings = current_bindings
        return updated.normalized()

    def _remove_binding_slot_value(self, binding: DashboardChartBinding, slot_name: str, field_name: str = "") -> DashboardChartBinding:
        updated = binding.normalized()
        slot_name = normalize_binding_role(slot_name)
        field_name = str(field_name or "").strip()
        role_items = list(updated.bindings.get(slot_name) or [])
        if field_name:
            role_items = [item for item in role_items if item.field != field_name]
        else:
            role_items = []
        updated.bindings[slot_name] = [item.normalized(slot_name, index) for index, item in enumerate(role_items)]
        return updated.normalized()

    def _change_binding_slot_aggregation(self, binding: DashboardChartBinding, slot_name: str, field_name: str, aggregation: str) -> DashboardChartBinding:
        updated = binding.normalized()
        role = normalize_binding_role(slot_name)
        items = []
        for index, item in enumerate(list(updated.bindings.get(role) or [])):
            if item.field == field_name:
                item = FieldBindingItem(item.field, item.display_name, item.type, aggregation, role, index).normalized(role, index)
            items.append(item.normalized(role, index))
        updated.bindings[role] = items
        return updated.normalized()

    def _move_binding_slot_field(self, binding: DashboardChartBinding, slot_name: str, field_name: str, delta: int) -> DashboardChartBinding:
        updated = binding.normalized()
        role = normalize_binding_role(slot_name)
        items = list(updated.bindings.get(role) or [])
        current = next((index for index, item in enumerate(items) if item.field == field_name), -1)
        if current < 0:
            return updated
        target = max(0, min(len(items) - 1, current + int(delta or 0)))
        if target == current:
            return updated
        item = items.pop(current)
        items.insert(target, item)
        updated.bindings[role] = [item.normalized(role, index) for index, item in enumerate(items)]
        return updated.normalized()

    def _update_selected_visual_binding_controls(self):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = item.binding.normalized()
        binding.aggregation = str(self.builder_agg_combo.currentData() or "count").strip().lower() or "count"
        binding.top_n = max(1, int(self.builder_topn_spin.value()))
        binding.title_override = str(self.builder_title_edit.text() or "").strip()
        for role in (ROLE_VALUES, ROLE_Y_AXIS):
            items = list(binding.bindings.get(role) or [])
            if items:
                first = items[0]
                items[0] = FieldBindingItem(first.field, first.display_name, first.type, binding.aggregation, first.role, first.order).normalized(first.role, first.order)
                binding.bindings[role] = items
                break
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _apply_dropped_field_to_selected_visual(self, slot_name: str, payload):
        item = self._selected_canvas_item()
        if item is None or not isinstance(payload, dict):
            return
        binding = self._apply_field_payload_to_binding(item.binding, slot_name, payload)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _remove_selected_visual_slot_field(self, slot_name: str, field_name: str = ""):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._remove_binding_slot_value(item.binding, slot_name, field_name)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _change_selected_visual_slot_aggregation(self, slot_name: str, field_name: str, aggregation: str):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._change_binding_slot_aggregation(item.binding, slot_name, field_name, aggregation)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _move_selected_visual_slot_field(self, slot_name: str, field_name: str, delta: int):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._move_binding_slot_field(item.binding, slot_name, field_name, delta)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _handle_field_list_activation(self, payload):
        if not isinstance(payload, dict):
            return
        binding = self._active_selected_binding() or DashboardChartBinding(chart_type="bar")
        suggested = suggest_binding_slot(binding.chart_type or "bar", str(payload.get("field_group") or "other"), binding)
        self._apply_dropped_field_to_selected_visual(suggested, payload)

    def _refresh_builder_layers(self):
        previous_layer_id = self._current_builder_layer_id()
        selected_binding = self._active_selected_binding()
        if selected_binding is not None and selected_binding.source_id:
            previous_layer_id = str(selected_binding.source_id or previous_layer_id)
        self._builder_layers = {}
        self.builder_layer_combo.blockSignals(True)
        project = QgsProject.instance()
        for layer in list(project.mapLayers().values()):
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                continue
            self._builder_layers[layer.id()] = layer
        if previous_layer_id and previous_layer_id in self._builder_layers:
            try:
                self.builder_layer_combo.setLayer(self._builder_layers[previous_layer_id])
            except Exception:
                log_exception("falha opcional ignorada")
        self.builder_layer_combo.blockSignals(False)
        self._on_builder_layer_changed()
        self._sync_builder_selection_state()

    def _on_builder_layer_changed(self, *_args):
        layer = self._current_builder_layer()
        self.builder_dimension_combo.blockSignals(True)
        self.builder_value_combo.blockSignals(True)
        self.builder_dimension_combo.clear()
        self.builder_value_combo.clear()
        self.builder_value_combo.addItem(_rt("Contagem"), "__count__")
        if layer is not None:
            for field_def in list(layer.fields()):
                field_name = str(field_def.name() or "").strip()
                if not field_name:
                    continue
                self.builder_dimension_combo.addItem(field_name, field_name)
                if self._field_is_numeric(field_def):
                    self.builder_value_combo.addItem(field_name, field_name)
        self.builder_dimension_combo.blockSignals(False)
        self.builder_value_combo.blockSignals(False)
        self._refresh_builder_field_lists(layer)
        self._on_builder_value_changed()
        selected_item = self._selected_canvas_item()
        if selected_item is not None:
            binding = selected_item.binding.normalized()
            if layer is not None and binding.source_id != layer.id():
                binding.source_id = layer.id()
                binding.source_name = layer.name()
                updated_item = self._rebuild_chart_item_from_binding(selected_item, binding)
                if updated_item is not None:
                    self._replace_canvas_item(updated_item)

    def _on_builder_value_changed(self):
        value_key = str(self.builder_value_combo.currentData() or "__count__")
        preferred = "count" if value_key == "__count__" else "sum"
        index = self.builder_agg_combo.findData(preferred)
        if index >= 0:
            self.builder_agg_combo.setCurrentIndex(index)

    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except Exception:
            return None

    def _resolve_layer_field_name(self, layer: QgsVectorLayer, field_name: str) -> str:
        candidate = str(field_name or "").strip()
        if layer is None or not candidate:
            return ""
        try:
            fields = layer.fields()
        except Exception:
            return candidate
        try:
            index = fields.lookupField(candidate)
        except Exception:
            index = -1
        if index is not None and index >= 0:
            try:
                return str(fields.field(index).name() or candidate).strip()
            except Exception:
                return candidate
        lowered = candidate.lower()
        try:
            for field in fields:
                name = str(field.name() or "").strip()
                if name and (name == candidate or name.lower() == lowered):
                    return name
        except Exception:
            log_exception("falha opcional ignorada")
        return ""

    def _field_kind_for_layer_field(self, layer: QgsVectorLayer, field_name: str) -> str:
        try:
            fields = layer.fields()
            index = fields.lookupField(str(field_name or ""))
            if index is not None and index >= 0:
                return normalize_field_kind(field_kind_from_field_def(fields.field(index)))
        except Exception:
            log_exception("falha opcional ignorada")
        return "unknown"

    def _resolve_binding_items_for_layer(self, binding: DashboardChartBinding, role: str, layer: QgsVectorLayer) -> List[FieldBindingItem]:
        normalized = binding.normalized()
        result: List[FieldBindingItem] = []
        for index, item in enumerate(list(normalized.bindings.get(normalize_binding_role(role)) or [])):
            resolved_name = self._resolve_layer_field_name(layer, item.field)
            if not resolved_name:
                continue
            field_type = self._field_kind_for_layer_field(layer, resolved_name)
            result.append(
                FieldBindingItem(
                    field=resolved_name,
                    display_name=item.display_name or resolved_name,
                    type=field_type,
                    aggregation=normalize_aggregation(item.aggregation, field_type, item.role),
                    role=item.role,
                    order=index,
                ).normalized(item.role, index)
            )
        return result

    def _feature_category_from_items(self, feature, items: List[FieldBindingItem]) -> tuple[str, object]:
        if not items:
            return _rt("Total"), _rt("Total")
        raw_parts = []
        display_parts = []
        for item in items:
            raw_value = feature.attribute(item.field)
            raw_parts.append(raw_value)
            text = str(raw_value).strip() if raw_value not in (None, "") else _rt("(vazio)")
            display_parts.append(text)
        return " / ".join(display_parts), tuple(raw_parts)

    def _rebuild_scatter_item_from_binding(self, item: DashboardChartItem, binding: DashboardChartBinding, layer: QgsVectorLayer) -> DashboardChartItem:
        updated_item = item.clone()
        updated_binding = binding.normalized()
        x_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
        y_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
        size_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_SIZE, layer)
        legend_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_LEGEND, layer)
        if x_items:
            updated_binding.x_field = x_items[0].field
        if y_items:
            updated_binding.y_field = y_items[0].field
        if size_items:
            updated_binding.size_field = size_items[0].field
        if legend_items:
            updated_binding.legend_field = legend_items[0].field
        points = []
        for feature in layer.getFeatures():
            x_value = self._safe_float(feature.attribute(updated_binding.x_field))
            y_value = self._safe_float(feature.attribute(updated_binding.y_field))
            if x_value is None or y_value is None:
                continue
            size_value = self._safe_float(feature.attribute(updated_binding.size_field)) if updated_binding.size_field else None
            legend_value = feature.attribute(updated_binding.legend_field) if updated_binding.legend_field else None
            try:
                feature_ids = [int(feature.id())]
            except Exception:
                feature_ids = []
            category = str(legend_value).strip() if legend_value not in (None, "") else str(x_value)
            points.append({"category": category, "x": float(x_value), "y": float(y_value), "size": float(size_value) if size_value is not None else 1.0, "feature_ids": feature_ids})
        if not points:
            updated_item.binding = updated_binding
            updated_item.payload = self._empty_chart_payload("scatter", updated_binding.title_override)
            updated_item.subtitle = _rt("Sem pares numericos validos para X e Y")
            updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
            return updated_item
        top_n = max(1, int(updated_binding.top_n or 50))
        truncated = len(points) > top_n
        points = points[:top_n]
        title_text = str(updated_binding.title_override or "").strip() or _rt("{y_field} por {x_field}", y_field=updated_binding.y_field, x_field=updated_binding.x_field)
        updated_item.binding = updated_binding
        updated_item.title = title_text if updated_binding.title_override else ""
        updated_item.subtitle = f"{layer.name()} - X: {updated_binding.x_field} - Y: {updated_binding.y_field}"
        updated_item.payload = ChartPayload.build(
            chart_type="scatter",
            title=title_text,
            categories=[point["category"] for point in points],
            values=[point["y"] for point in points],
            value_label=updated_binding.y_field,
            truncated=truncated,
            selection_layer_id=layer.id(),
            selection_layer_name=layer.name(),
            category_field=updated_binding.legend_field or updated_binding.x_field,
            raw_categories=[point["category"] for point in points],
            category_feature_ids=[point["feature_ids"] for point in points],
            x_values=[point["x"] for point in points],
            size_values=[point["size"] for point in points],
            series_labels=[point["category"] for point in points],
        )
        updated_item.source_meta = {
            "builder_version": "v2",
            "empty_visual": False,
            "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
            "config": {
                "chart_type": "scatter",
                "x_field": updated_binding.x_field,
                "y_field": updated_binding.y_field,
                "size_field": updated_binding.size_field,
                "legend_field": updated_binding.legend_field,
                "filter_fields": list(updated_binding.filter_fields or []),
                "tooltip_fields": list(updated_binding.tooltip_fields or []),
            },
        }
        return updated_item

    def _rebuild_matrix_item_from_binding(self, item: DashboardChartItem, binding: DashboardChartBinding, layer: QgsVectorLayer) -> DashboardChartItem:
        updated_item = item.clone()
        updated_binding = binding.normalized()
        row_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
        column_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
        value_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_VALUES, layer)
        rows = [item.field for item in row_items]
        columns = [item.field for item in column_items]
        values = [item.field for item in value_items]
        value_item = value_items[0] if value_items else None
        value_field = value_item.field if value_item is not None else ""
        aggregation = normalize_aggregation(value_item.aggregation if value_item is not None else updated_binding.aggregation, value_item.type if value_item is not None else "", ROLE_VALUES)
        grouped: Dict[str, Dict[str, object]] = {}
        has_numeric_values = False
        for feature in layer.getFeatures():
            row_parts = [str(feature.attribute(field) or _rt("(vazio)")).strip() for field in rows]
            column_parts = [str(feature.attribute(field) or _rt("(vazio)")).strip() for field in columns[:1]]
            category = " / ".join([part for part in [*row_parts, *column_parts] if part]) or _rt("(vazio)")
            bucket = grouped.setdefault(category, {"sum": 0.0, "count": 0, "feature_ids": []})
            try:
                bucket["feature_ids"].append(int(feature.id()))
            except Exception:
                log_exception("falha opcional ignorada")
            if aggregation == "count":
                numeric = 1.0
            else:
                numeric = self._safe_float(feature.attribute(value_field)) if value_field else None
                if numeric is None:
                    continue
                has_numeric_values = True
            bucket["sum"] = float(bucket.get("sum") or 0.0) + float(numeric)
            bucket["count"] = int(bucket.get("count") or 0) + 1
        if not grouped or (aggregation != "count" and not has_numeric_values):
            updated_item.binding = updated_binding
            updated_item.payload = self._empty_chart_payload("matrix", updated_binding.title_override)
            updated_item.subtitle = _rt("Sem valores numericos para a matriz")
            updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
            return updated_item
        matrix_rows = []
        for category, bucket in grouped.items():
            count = int(bucket.get("count") or 0)
            value = float(bucket.get("sum") or 0.0)
            if aggregation == "avg":
                value = value / float(max(1, count))
            elif aggregation == "count":
                value = float(count)
            matrix_rows.append({"category": category, "value": value, "feature_ids": list(bucket.get("feature_ids") or [])})
        matrix_rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
        top_n = max(1, int(updated_binding.top_n or 50))
        truncated = len(matrix_rows) > top_n
        matrix_rows = matrix_rows[:top_n]
        title_text = str(updated_binding.title_override or "").strip() or _rt("Matriz - {layer_name}", layer_name=layer.name())
        updated_item.binding = updated_binding
        updated_item.title = title_text if updated_binding.title_override else ""
        updated_item.subtitle = f"{layer.name()} - {', '.join(rows)} - {value_field}"
        updated_item.payload = ChartPayload.build(
            chart_type="matrix",
            title=title_text,
            categories=[str(row.get("category") or "") for row in matrix_rows],
            values=[float(row.get("value") or 0.0) for row in matrix_rows],
            value_label=value_field,
            truncated=truncated,
            selection_layer_id=layer.id(),
            selection_layer_name=layer.name(),
            category_field=rows[0] if rows else "",
            raw_categories=[str(row.get("category") or "") for row in matrix_rows],
            category_feature_ids=[list(row.get("feature_ids") or []) for row in matrix_rows],
        )
        updated_item.source_meta = {
            "builder_version": "v2",
            "empty_visual": False,
            "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
            "config": {
                "chart_type": "matrix",
                "row_fields": list(rows),
                "column_fields": list(columns),
                "value_fields": list(values),
                "aggregation": aggregation,
                "filter_fields": list(updated_binding.filter_fields or []),
                "tooltip_fields": list(updated_binding.tooltip_fields or []),
            },
        }
        return updated_item

    def _rebuild_chart_item_from_binding(self, item: DashboardChartItem, binding: DashboardChartBinding) -> Optional[DashboardChartItem]:
        if item is None:
            return None
        updated_item = item.clone()
        updated_binding = binding.normalized()
        chart_type = str(updated_binding.chart_type or getattr(updated_item.visual_state, "chart_type", "bar") or "bar").strip().lower() or "bar"
        updated_binding.chart_type = chart_type
        updated_item.visual_state.chart_type = chart_type

        layer = self._builder_layers.get(str(updated_binding.source_id or ""))
        if layer is None:
            layer = self._selected_layer()
        if layer is None or not layer.isValid():
            updated_item.binding = updated_binding
            updated_item.payload = self._empty_chart_payload(chart_type, updated_binding.title_override)
            updated_item.subtitle = _rt("Selecione uma camada para continuar")
            updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
            return updated_item

        updated_binding.source_id = layer.id()
        updated_binding.source_name = layer.name()
        x_axis_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
        y_axis_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
        value_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_VALUES, layer)
        legend_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_LEGEND, layer)
        filter_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_FILTERS, layer)
        tooltip_items = self._resolve_binding_items_for_layer(updated_binding, ROLE_TOOLTIP, layer)
        measure_items = list(value_items or []) or list(y_axis_items or [])
        dimension_field = x_axis_items[0].field if x_axis_items else ""
        measure_field = measure_items[0].field if measure_items else ""
        legend_field = legend_items[0].field if legend_items else ""
        aggregation = normalize_aggregation(measure_items[0].aggregation if measure_items else updated_binding.aggregation, measure_items[0].type if measure_items else "", ROLE_VALUES)
        top_n = max(1, int(updated_binding.top_n or 12))

        updated_binding.dimension_field = dimension_field
        updated_binding.measure_field = measure_field
        updated_binding.legend_field = legend_field
        updated_binding.x_field = x_axis_items[0].field if x_axis_items else ""
        updated_binding.y_field = y_axis_items[0].field if y_axis_items else ""
        updated_binding.row_fields = [item.field for item in x_axis_items]
        updated_binding.column_fields = [item.field for item in y_axis_items]
        updated_binding.value_fields = [item.field for item in value_items]
        updated_binding.filter_fields = [item.field for item in filter_items]
        updated_binding.tooltip_fields = [item.field for item in tooltip_items]
        updated_binding.bindings = {
            role: items
            for role, items in {
                ROLE_X_AXIS: x_axis_items,
                ROLE_Y_AXIS: y_axis_items,
                ROLE_VALUES: value_items,
                ROLE_LEGEND: legend_items,
                ROLE_FILTERS: filter_items,
                ROLE_TOOLTIP: tooltip_items,
            }.items()
            if items
        }
        if dimension_field:
            updated_binding.semantic_field_key = dimension_field
            updated_binding.semantic_field_aliases = [item.field for item in x_axis_items]

        if not updated_binding.has_minimum_fields():
            updated_item.binding = updated_binding
            updated_item.payload = self._empty_chart_payload(chart_type, updated_binding.title_override)
            updated_item.subtitle = _rt(empty_binding_message(chart_type, updated_binding))
            updated_item.source_meta = {
                "builder_version": "v2",
                "empty_visual": True,
                "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
            }
            return updated_item

        if chart_type == "scatter":
            return self._rebuild_scatter_item_from_binding(updated_item, updated_binding, layer)

        if chart_type == "matrix":
            return self._rebuild_matrix_item_from_binding(updated_item, updated_binding, layer)

        active_measure_items = measure_items or [
            FieldBindingItem(
                field=dimension_field,
                display_name=_rt("Contagem"),
                type="unknown",
                aggregation="count",
                role=ROLE_VALUES,
                order=0,
            ).normalized(ROLE_VALUES, 0)
        ]
        if chart_type in {"pie", "donut", "card", "kpi", "gauge"} and active_measure_items:
            active_measure_items = active_measure_items[:1]

        grouped: Dict[tuple[str, str], Dict[str, object]] = {}
        has_numeric_values = False
        for feature in layer.getFeatures():
            category, raw_category = self._feature_category_from_items(feature, x_axis_items)
            for measure_index, measure_item in enumerate(active_measure_items):
                measure_label = measure_item.display_name or measure_item.field or _rt("Valor")
                bucket_key = (category, measure_label if len(active_measure_items) > 1 else "")
                bucket = grouped.setdefault(
                    bucket_key,
                    {
                        "category": category,
                        "series": measure_label if len(active_measure_items) > 1 else "",
                        "raw_category": (raw_category, measure_label) if len(active_measure_items) > 1 else raw_category,
                        "feature_ids": [],
                        "sum": 0.0,
                        "count": 0,
                        "distinct": set(),
                        "min": None,
                        "max": None,
                    },
                )
                try:
                    bucket["feature_ids"].append(int(feature.id()))
                except Exception:
                    log_exception("falha opcional ignorada")

                item_aggregation = normalize_aggregation(measure_item.aggregation, measure_item.type, measure_item.role)
                target_field = measure_item.field or dimension_field
                raw_value = feature.attribute(target_field) if target_field else None
                if item_aggregation == "count":
                    value = 1.0
                elif item_aggregation == "unique_count":
                    if raw_value is not None and str(raw_value).strip():
                        bucket["distinct"].add(str(raw_value).strip())
                    bucket["count"] = int(bucket.get("count") or 0) + 1
                    continue
                else:
                    value = self._safe_float(raw_value)
                    if value is None:
                        continue
                    has_numeric_values = True

                bucket["sum"] = float(bucket.get("sum") or 0.0) + float(value)
                bucket["count"] = int(bucket.get("count") or 0) + 1
                current_min = bucket.get("min")
                current_max = bucket.get("max")
                bucket["min"] = float(value) if current_min is None else min(float(current_min), float(value))
                bucket["max"] = float(value) if current_max is None else max(float(current_max), float(value))

        if any(normalize_aggregation(item.aggregation, item.type, item.role) not in {"count", "unique_count"} for item in active_measure_items) and not has_numeric_values:
            updated_item.binding = updated_binding
            updated_item.payload = self._empty_chart_payload(chart_type, updated_binding.title_override)
            updated_item.subtitle = _rt("Sem valores numericos para o campo selecionado")
            updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
            return updated_item

        rows: List[Dict[str, object]] = []
        for (_category, _series), bucket in grouped.items():
            count = int(bucket.get("count") or 0)
            measure_label = str(bucket.get("series") or "")
            measure_item = next((item for item in active_measure_items if (item.display_name or item.field) == measure_label), active_measure_items[0])
            item_aggregation = normalize_aggregation(measure_item.aggregation, measure_item.type, measure_item.role)
            if item_aggregation == "avg":
                metric_value = float(bucket.get("sum") or 0.0) / float(max(1, count))
            elif item_aggregation == "min":
                metric_value = float(bucket.get("min") or 0.0)
            elif item_aggregation == "max":
                metric_value = float(bucket.get("max") or 0.0)
            elif item_aggregation == "sum":
                metric_value = float(bucket.get("sum") or 0.0)
            elif item_aggregation == "unique_count":
                metric_value = float(len(bucket.get("distinct") or set()))
            else:
                metric_value = float(count)
            display_category = str(bucket.get("category") or "")
            if measure_label:
                display_category = f"{display_category} / {measure_label}"
            rows.append(
                {
                    "category": display_category,
                    "value": metric_value,
                    "raw_category": bucket.get("raw_category"),
                    "feature_ids": list(bucket.get("feature_ids") or []),
                }
            )

        rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
        truncated = len(rows) > top_n
        rows = rows[:top_n]
        categories = [str(row.get("category") or "") for row in rows]
        values = [float(row.get("value") or 0.0) for row in rows]
        raw_categories = [row.get("raw_category") for row in rows]
        feature_groups = [list(row.get("feature_ids") or []) for row in rows]

        agg_label = {
            "count": _rt("Contagem"),
            "sum": _rt("Soma"),
            "avg": _rt("Media"),
            "min": _rt("Minimo"),
            "max": _rt("Maximo"),
            "count_distinct": _rt("Contagem distinta"),
            "unique_count": _rt("Contagem distinta"),
        }.get(aggregation, _rt("Contagem"))
        value_target = measure_field or dimension_field
        value_label = _rt("Contagem") if aggregation == "count" else _rt("{agg_label} de {field_name}", agg_label=agg_label, field_name=value_target)

        title_text = str(updated_binding.title_override or "").strip()
        if not title_text:
            if chart_type in {"card", "kpi", "gauge"}:
                title_text = _rt("{agg_label} - {layer_name}", agg_label=agg_label, layer_name=layer.name())
            else:
                title_text = _rt("{agg_label} por {dimension_field}", agg_label=agg_label, dimension_field=" / ".join(item.display_name or item.field for item in x_axis_items) or dimension_field)

        updated_item.binding = updated_binding
        updated_item.title = title_text if updated_binding.title_override else ""
        updated_item.subtitle = f"{layer.name()} - {dimension_field} - {value_label}"
        updated_item.payload = ChartPayload.build(
            chart_type=chart_type,
            title=title_text,
            categories=categories,
            values=values,
            value_label=value_label,
            truncated=truncated,
            selection_layer_id=layer.id(),
            selection_layer_name=layer.name(),
            category_field=dimension_field,
            raw_categories=raw_categories,
            category_feature_ids=feature_groups,
        )
        updated_item.source_meta = {
            "builder_version": "v2",
            "empty_visual": False,
            "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
            "config": {
                "chart_type": chart_type,
                "row_field": dimension_field,
                "row_fields": [item.field for item in x_axis_items],
                "semantic_field_key": dimension_field,
                "value_field": measure_field,
                "value_fields": [item.field for item in active_measure_items],
                "bindings": updated_binding.to_dict().get("bindings", {}),
                "legend_field": legend_field,
                "aggregation": aggregation,
                "top_n": top_n,
                "filter_fields": list(updated_binding.filter_fields or []),
                "tooltip_fields": list(updated_binding.tooltip_fields or []),
            },
        }
        return updated_item

    def _configure_toolbar_icon_button(self, button, icon_name: str, tooltip: str, icon_size: int = 18):
        button.setProperty("toolbarMode", "icon")
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        try:
            button.setAccessibleName(tooltip)
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            button.setText("")
        except Exception:
            log_exception("falha opcional ignorada")
        icon = svg_icon(icon_name)
        if not icon.isNull():
            button.setIcon(icon)
        button.setIconSize(QSize(icon_size, icon_size))
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setAutoRaise(False)

    def _configure_toolbar_text_icon_button(self, button, icon_name: str, text: str, tooltip: str, icon_size: int = 18):
        self._configure_toolbar_icon_button(button, icon_name, tooltip, icon_size=icon_size)
        button.setProperty("toolbarMode", "label")
        try:
            button.setText(text)
        except Exception:
            log_exception("falha opcional ignorada")

    def _create_toolbar_separator(self, parent: QWidget) -> QFrame:
        separator = QFrame(parent)
        separator.setObjectName("ModelToolbarSeparator")
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        return separator

    def _normalize_hex_color(self, value: object, fallback: str) -> str:
        color = QColor(str(value or "").strip())
        if not color.isValid():
            color = QColor(str(fallback or "#FFFFFF"))
        return color.name().upper()

    def _default_canvas_style(self) -> Dict[str, object]:
        return {
            "background": "#FFFFFF",
            "grid_color": "#FFFFFF",
            "show_grid": True,
            "grid_size": 8,
            "grid_opacity": 1.0,
        }

    def _normalized_canvas_style(self, style: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        base = self._default_canvas_style()
        payload = dict(style or {})
        try:
            grid_size = int(round(float(payload.get("grid_size", base["grid_size"]))))
        except Exception:
            grid_size = int(base["grid_size"])
        grid_size = max(4, min(48, grid_size))
        try:
            grid_opacity = float(payload.get("grid_opacity", base["grid_opacity"]))
        except Exception:
            grid_opacity = float(base["grid_opacity"])
        grid_opacity = max(0.1, min(1.0, grid_opacity))
        background = self._normalize_hex_color(payload.get("background"), str(base["background"]))
        grid_color = self._normalize_hex_color(payload.get("grid_color"), str(base["grid_color"]))
        if background == "#FFFFFF" and grid_color == "#E5E7EB":
            grid_color = "#FFFFFF"
            grid_opacity = 1.0
        return {
            "background": background,
            "grid_color": grid_color,
            "show_grid": bool(payload.get("show_grid", base["show_grid"])),
            "grid_size": grid_size,
            "grid_opacity": grid_opacity,
        }

    def _project_canvas_style(self) -> Dict[str, object]:
        if self.current_project is None:
            return self._default_canvas_style()
        source_meta = dict(getattr(self.current_project, "source_meta", {}) or {})
        return self._normalized_canvas_style(source_meta.get("canvas_style"))

    def _apply_canvas_style_to_widget(self, widget: Optional[DashboardPageWidget], style: Dict[str, object]):
        if widget is None or not hasattr(widget, "canvas"):
            return
        canvas_style = self._normalized_canvas_style(style)
        try:
            widget.canvas.set_canvas_style(
                background_color=canvas_style["background"],
                grid_color=canvas_style["grid_color"],
                show_grid=canvas_style["show_grid"],
                grid_size=canvas_style["grid_size"],
                grid_opacity=canvas_style["grid_opacity"],
            )
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_canvas_style_to_pages(
        self,
        style: Optional[Dict[str, object]] = None,
        *,
        persist: bool = False,
        mark_dirty: bool = False,
        record_history: bool = False,
    ):
        canvas_style = self._normalized_canvas_style(style if style is not None else self._project_canvas_style())
        if persist and self.current_project is not None:
            source_meta = dict(getattr(self.current_project, "source_meta", {}) or {})
            source_meta["canvas_style"] = dict(canvas_style)
            self.current_project.source_meta = source_meta
        for widget in self._page_widgets_in_order():
            self._apply_canvas_style_to_widget(widget, canvas_style)
        if self.current_project is not None and mark_dirty:
            self._dirty = True
        if record_history:
            self._commit_history_if_changed()
        self._refresh_ui_state()

    def _set_color_preview_chip(self, label: QLabel, color_value: object, fallback: str):
        color_hex = self._normalize_hex_color(color_value, fallback)
        label.setText(" ")
        label.setStyleSheet(
            f"""
            QLabel {{
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                border-radius: 6px;
                border: 1px solid #D1D5DB;
                background: {color_hex};
            }}
            """
        )

    def _open_canvas_style_settings(self):
        if self.current_project is None:
            return
        style = self._project_canvas_style()
        draft = dict(style)

        dialog = QDialog(self)
        dialog.setObjectName("WalkerCanvasStyleDialog")
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setModal(True)
        dialog.resize(560, 392)
        dialog.setFont(ui_font())
        dialog._font_enforcer = attach_ui_font_enforcer(dialog)
        dialog.setStyleSheet(
            """
            QDialog#WalkerCanvasStyleDialog {
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 10px;
            }
            QFrame#WalkerDialogCard {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            QFrame#WalkerDialogDragHandle {
                background: transparent;
                border: none;
            }
            QLabel#WalkerDialogTitle {
                color: #111827;
                font-size: 14px;
                font-weight: 500;
            }
            QLabel#WalkerDialogSubtitle {
                color: #6B7280;
                font-size: 11px;
            }
            QLabel#WalkerFieldLabel {
                color: #111827;
                font-size: 12px;
                font-weight: 400;
            }
            QLineEdit#WalkerDialogInput,
            QComboBox#WalkerDialogInput,
            QSpinBox#WalkerDialogInput {
                min-height: 30px;
                padding: 0 9px;
                color: #111827;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
            }
            QLineEdit#WalkerDialogInput:focus,
            QComboBox#WalkerDialogInput:focus,
            QSpinBox#WalkerDialogInput:focus {
                border-color: #9CA3AF;
            }
            QSpinBox#WalkerDialogInput::up-button,
            QSpinBox#WalkerDialogInput::down-button {
                width: 0px;
                border: none;
                background: transparent;
                margin: 0;
                padding: 0;
            }
            QSpinBox#WalkerDialogInput::up-arrow,
            QSpinBox#WalkerDialogInput::down-arrow {
                width: 0px;
                height: 0px;
                image: none;
            }
            QCheckBox#WalkerDialogCheck {
                color: #111827;
                font-size: 12px;
                font-weight: 400;
            }
            QPushButton#WalkerDialogPrimaryButton,
            QPushButton#WalkerDialogSecondaryButton {
                min-height: 32px;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 12px;
            }
            QPushButton#WalkerDialogSecondaryButton {
                color: #111827;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                font-weight: 400;
            }
            QPushButton#WalkerDialogSecondaryButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton#WalkerDialogPrimaryButton {
                color: #FFFFFF;
                background: #111827;
                border: 1px solid #111827;
                font-weight: 500;
            }
            QPushButton#WalkerDialogPrimaryButton:hover {
                background: #1F2937;
                border-color: #1F2937;
            }
            QPushButton#WalkerColorChip {
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                border-radius: 5px;
                border: 1px solid #D1D5DB;
                padding: 0;
            }
            QLabel#WalkerAuxText {
                color: #6B7280;
                font-size: 10px;
            }
            QToolButton#ConfigDialogCloseButton {
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                color: #6B7280;
                font-size: 14px;
            }
            QToolButton#ConfigDialogCloseButton:hover {
                color: #111827;
                background: #F3F4F6;
            }
            """
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        title_font = ui_font()
        title_font.setPixelSize(14)
        title_font.setWeight(600)

        body_font = ui_font()
        body_font.setPixelSize(12)

        helper_font = ui_font()
        helper_font.setPixelSize(11)

        drag_handle = _DialogDragHandle(dialog, dialog)
        drag_handle.setObjectName("WalkerDialogDragHandle")
        drag_handle.setFixedHeight(24)
        top_bar = QHBoxLayout(drag_handle)
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)
        top_hint = QLabel(_rt("Configuração visual"), dialog)
        top_hint.setObjectName("WalkerDialogSubtitle")
        top_hint.setFont(helper_font)
        top_bar.addWidget(top_hint, 0)
        top_bar.addStretch(1)
        close_btn = QToolButton(dialog)
        close_btn.setObjectName("ConfigDialogCloseButton")
        close_btn.setText("×")
        close_btn.clicked.connect(dialog.reject)
        top_bar.addWidget(close_btn, 0)
        layout.addWidget(drag_handle, 0)

        title = QLabel(_rt("Configurar canvas"), dialog)
        title.setObjectName("WalkerDialogTitle")
        title.setFont(title_font)
        layout.addWidget(title, 0)

        subtitle = QLabel(_rt("Ajuste fundo, grade e densidade visual com visual minimalista."), dialog)
        subtitle.setObjectName("WalkerDialogSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setFont(helper_font)
        layout.addWidget(subtitle, 0)

        card = QFrame(dialog)
        card.setObjectName("WalkerDialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        def _build_label(text: str) -> QLabel:
            label = QLabel(text, card)
            label.setObjectName("WalkerFieldLabel")
            label.setFont(body_font)
            return label

        theme_label = _build_label(_rt("Tema"))
        theme_combo = QComboBox(card)
        theme_combo.setObjectName("WalkerDialogInput")
        presets = {
            "clean": {
                "background": "#FFFFFF",
                "grid_color": "#FFFFFF",
                "show_grid": True,
                "grid_size": 8,
                "grid_opacity": 1.0,
            },
            "soft": {
                "background": "#F8FAFC",
                "grid_color": "#D1D5DB",
                "show_grid": True,
                "grid_size": 10,
                "grid_opacity": 0.66,
            },
            "dark": {
                "background": "#111827",
                "grid_color": "#374151",
                "show_grid": True,
                "grid_size": 8,
                "grid_opacity": 0.6,
            },
        }
        theme_combo.addItem(_rt("Personalizado"), "custom")
        theme_combo.addItem(_rt("Padrão clean"), "clean")
        theme_combo.addItem(_rt("Padrão suave"), "soft")
        theme_combo.addItem(_rt("Noturno"), "dark")
        grid.addWidget(theme_label, 0, 0)
        grid.addWidget(theme_combo, 0, 1, 1, 3)

        bg_label = _build_label(_rt("Cor do fundo"))
        bg_edit = QLineEdit(str(draft.get("background") or ""), card)
        bg_edit.setObjectName("WalkerDialogInput")
        bg_preview = QLabel(card)
        self._set_color_preview_chip(bg_preview, bg_edit.text(), "#FFFFFF")
        grid.addWidget(bg_label, 1, 0)
        grid.addWidget(bg_edit, 1, 1, 1, 2)
        grid.addWidget(bg_preview, 1, 3)

        grid_label = _build_label(_rt("Cor da grade"))
        grid_edit = QLineEdit(str(draft.get("grid_color") or ""), card)
        grid_edit.setObjectName("WalkerDialogInput")
        grid_preview = QLabel(card)
        self._set_color_preview_chip(grid_preview, grid_edit.text(), "#FFFFFF")
        grid.addWidget(grid_label, 2, 0)
        grid.addWidget(grid_edit, 2, 1, 1, 2)
        grid.addWidget(grid_preview, 2, 3)

        show_grid_check = QCheckBox(_rt("Mostrar grade no modo de edicao"), card)
        show_grid_check.setObjectName("WalkerDialogCheck")
        show_grid_check.setFont(body_font)
        show_grid_check.setChecked(bool(draft.get("show_grid", True)))
        grid.addWidget(show_grid_check, 3, 0, 1, 4)

        grid_size_label = _build_label(_rt("Tamanho da grade"))
        grid_size_spin = QSpinBox(card)
        grid_size_spin.setObjectName("WalkerDialogInput")
        grid_size_spin.setRange(4, 48)
        grid_size_spin.setValue(int(draft.get("grid_size", 8)))
        grid_size_spin.setButtonSymbols(QSpinBox.NoButtons)
        grid_size_spin.setAlignment(Qt.AlignCenter)
        grid.addWidget(grid_size_label, 4, 0)
        grid.addWidget(grid_size_spin, 4, 1)

        grid_opacity_label = _build_label(_rt("Opacidade da grade (%)"))
        grid_opacity_spin = QSpinBox(card)
        grid_opacity_spin.setObjectName("WalkerDialogInput")
        grid_opacity_spin.setRange(10, 100)
        grid_opacity_spin.setValue(int(round(float(draft.get("grid_opacity", 1.0)) * 100.0)))
        grid_opacity_spin.setButtonSymbols(QSpinBox.NoButtons)
        grid_opacity_spin.setAlignment(Qt.AlignCenter)
        grid.addWidget(grid_opacity_label, 4, 2)
        grid.addWidget(grid_opacity_spin, 4, 3)

        card_layout.addLayout(grid)

        palette_bg = QHBoxLayout()
        palette_bg.setContentsMargins(0, 0, 0, 0)
        palette_bg.setSpacing(6)
        palette_bg.addWidget(QLabel(_rt("Paleta fundo"), card))
        bg_quick_colors = ["#FFFFFF", "#F8FAFC", "#F3F4F6", "#F1F5F9", "#111827"]
        for color in bg_quick_colors:
            chip = QPushButton("", card)
            chip.setObjectName("WalkerColorChip")
            chip.setToolTip(color)
            chip.setStyleSheet(
                f"QPushButton#WalkerColorChip{{background:{color};border:1px solid #D1D5DB;border-radius:6px;}}"
            )
            chip.clicked.connect(lambda checked=False, value=color: bg_edit.setText(value))
            palette_bg.addWidget(chip)
        palette_bg.addStretch(1)
        card_layout.addLayout(palette_bg)

        palette_grid = QHBoxLayout()
        palette_grid.setContentsMargins(0, 0, 0, 0)
        palette_grid.setSpacing(6)
        palette_grid.addWidget(QLabel(_rt("Paleta grade"), card))
        grid_quick_colors = ["#FFFFFF", "#E5E7EB", "#D1D5DB", "#9CA3AF", "#6B7280", "#374151"]
        for color in grid_quick_colors:
            chip = QPushButton("", card)
            chip.setObjectName("WalkerColorChip")
            chip.setToolTip(color)
            chip.setStyleSheet(
                f"QPushButton#WalkerColorChip{{background:{color};border:1px solid #D1D5DB;border-radius:6px;}}"
            )
            chip.clicked.connect(lambda checked=False, value=color: grid_edit.setText(value))
            palette_grid.addWidget(chip)
        palette_grid.addStretch(1)
        card_layout.addLayout(palette_grid)

        helper = QLabel(_rt("Dica: use fundo claro com grade suave para um visual limpo."), card)
        helper.setObjectName("WalkerAuxText")
        helper.setWordWrap(True)
        helper.setFont(helper_font)
        card_layout.addWidget(helper, 0)

        layout.addWidget(card, 1)
        harmonize_widget_fonts(dialog)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addStretch(1)

        reset_btn = QPushButton(_rt("Restaurar padrao"), dialog)
        reset_btn.setObjectName("WalkerDialogSecondaryButton")
        reset_btn.setFont(body_font)
        cancel_btn = QPushButton(_rt("Cancelar"), dialog)
        cancel_btn.setObjectName("WalkerDialogSecondaryButton")
        cancel_btn.setFont(body_font)
        apply_btn = QPushButton(_rt("Aplicar"), dialog)
        apply_btn.setObjectName("WalkerDialogPrimaryButton")
        apply_btn.setFont(body_font)

        actions.addWidget(reset_btn, 0)
        actions.addWidget(cancel_btn, 0)
        actions.addWidget(apply_btn, 0)
        layout.addLayout(actions)

        def _refresh_color_previews():
            self._set_color_preview_chip(bg_preview, bg_edit.text(), "#FFFFFF")
            self._set_color_preview_chip(grid_preview, grid_edit.text(), "#FFFFFF")

        bg_edit.textChanged.connect(lambda *_: _refresh_color_previews())
        grid_edit.textChanged.connect(lambda *_: _refresh_color_previews())

        preset_signal_lock = {"active": False}

        def _apply_style_to_controls(style_payload: Dict[str, object]):
            normalized = self._normalized_canvas_style(style_payload)
            bg_edit.setText(str(normalized.get("background") or "#FFFFFF"))
            grid_edit.setText(str(normalized.get("grid_color") or "#FFFFFF"))
            show_grid_check.setChecked(bool(normalized.get("show_grid", True)))
            grid_size_spin.setValue(int(normalized.get("grid_size", 8)))
            grid_opacity_spin.setValue(int(round(float(normalized.get("grid_opacity", 1.0)) * 100.0)))
            _refresh_color_previews()

        def _handle_preset_changed(index: int):
            key = str(theme_combo.itemData(index) or "")
            if key not in presets:
                return
            preset_signal_lock["active"] = True
            try:
                _apply_style_to_controls(dict(presets[key]))
            finally:
                preset_signal_lock["active"] = False

        theme_combo.currentIndexChanged.connect(_handle_preset_changed)

        def _mark_custom():
            if preset_signal_lock["active"]:
                return
            custom_index = theme_combo.findData("custom")
            if custom_index >= 0 and theme_combo.currentIndex() != custom_index:
                theme_combo.setCurrentIndex(custom_index)

        bg_edit.textChanged.connect(lambda *_: _mark_custom())
        grid_edit.textChanged.connect(lambda *_: _mark_custom())
        show_grid_check.toggled.connect(lambda *_: _mark_custom())
        grid_size_spin.valueChanged.connect(lambda *_: _mark_custom())
        grid_opacity_spin.valueChanged.connect(lambda *_: _mark_custom())

        def _reset_defaults():
            preset_signal_lock["active"] = True
            try:
                _apply_style_to_controls(self._default_canvas_style())
                default_index = theme_combo.findData("clean")
                if default_index >= 0:
                    theme_combo.setCurrentIndex(default_index)
            finally:
                preset_signal_lock["active"] = False

        reset_btn.clicked.connect(_reset_defaults)
        cancel_btn.clicked.connect(dialog.reject)
        apply_btn.clicked.connect(dialog.accept)

        if dialog.exec_() != QDialog.Accepted:
            return

        draft["background"] = self._normalize_hex_color(bg_edit.text(), str(style.get("background") or "#FFFFFF"))
        draft["grid_color"] = self._normalize_hex_color(grid_edit.text(), str(style.get("grid_color") or "#FFFFFF"))
        draft["show_grid"] = bool(show_grid_check.isChecked())
        draft["grid_size"] = int(grid_size_spin.value())
        draft["grid_opacity"] = max(0.1, min(1.0, float(grid_opacity_spin.value()) / 100.0))
        self._apply_canvas_style_to_pages(draft, persist=True, mark_dirty=True, record_history=True)

    def _project_snapshot_payload(self) -> Optional[Dict[str, object]]:
        if self.current_project is None:
            return None
        try:
            self._sync_project_from_pages(self._current_page_id())
        except Exception:
            log_exception("falha opcional ignorada")
        project = self.current_project
        pages = [page.normalized() for page in list(project.pages or [])]
        if not pages:
            pages = [DashboardPage(title=self._page_display_title(1)).normalized()]
        active_page_id = str(project.active_page_id or pages[0].page_id or "").strip() or pages[0].page_id
        active_page = pages[0]
        for page in pages:
            if str(page.page_id or "").strip() == active_page_id:
                active_page = page
                break
        payload = {
            "version": int(project.version or 2),
            "project_id": str(project.project_id or ""),
            "name": str(project.name or ""),
            "created_at": str(project.created_at or ""),
            "updated_at": str(project.updated_at or ""),
            "edit_mode": bool(project.edit_mode),
            "source_meta": dict(project.source_meta or {}),
            "active_page_id": active_page_id,
            "pages": [page.to_dict() for page in pages],
            "items": [item.to_dict() for item in list(active_page.items or [])],
            "visual_links": [link.to_dict() for link in list(active_page.visual_links or [])],
            "chart_relations": [relation.to_dict() for relation in list(active_page.chart_relations or [])],
        }
        try:
            return json.loads(json.dumps(payload, ensure_ascii=False))
        except Exception:
            return payload

    def _snapshot_state(self) -> Dict[str, object]:
        return {
            "project": self._project_snapshot_payload(),
            "path": str(self.current_path or ""),
            "dirty": bool(self._dirty),
        }

    def _snapshot_signature(self, snapshot: Optional[Dict[str, object]]) -> str:
        payload = dict(snapshot or {})
        serial = {
            "project": payload.get("project"),
            "path": str(payload.get("path") or ""),
        }
        try:
            return json.dumps(serial, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(serial)

    def _reset_history(self):
        self._history_undo.clear()
        self._history_redo.clear()
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _commit_history_if_changed(self):
        if self._history_restoring:
            return
        current_snapshot = self._snapshot_state()
        if self._history_current is None:
            self._history_current = current_snapshot
            self._update_undo_redo_buttons()
            return
        if self._snapshot_signature(current_snapshot) == self._snapshot_signature(self._history_current):
            self._update_undo_redo_buttons()
            return
        self._history_undo.append(self._history_current)
        if len(self._history_undo) > self._history_limit:
            self._history_undo = self._history_undo[-self._history_limit :]
        self._history_current = current_snapshot
        self._history_redo.clear()
        self._update_undo_redo_buttons()

    def _restore_history_snapshot(self, snapshot: Dict[str, object]):
        payload = dict(snapshot or {})
        project_payload = payload.get("project")
        self._history_restoring = True
        self._suspend_canvas_events = True
        try:
            if project_payload is None:
                self.current_project = None
                self.current_path = ""
                self._dirty = False
                self._selected_page_id = ""
                self._clear_page_widgets()
                self._clear_page_tab_buttons()
                self.canvas = None
            else:
                project = DashboardProject.from_dict(project_payload)
                self.current_project = project
                raw_path = str(payload.get("path") or "")
                self.current_path = self.store.normalize_path(raw_path) if raw_path else ""
                self._dirty = bool(payload.get("dirty"))
                self._selected_page_id = ""
                self._rebuild_page_stack(project.active_page_id or (project.pages[0].page_id if project.pages else ""))
                self.edit_mode_btn.blockSignals(True)
                try:
                    self.edit_mode_btn.setChecked(bool(project.edit_mode))
                finally:
                    self.edit_mode_btn.blockSignals(False)
                self.set_edit_mode(bool(project.edit_mode))
                self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
            self._refresh_builder_layers()
            self._refresh_ui_state()
        finally:
            self._suspend_canvas_events = False
            self._history_restoring = False

    def _undo_last_action(self):
        if not self._history_undo:
            return
        current_snapshot = self._history_current or self._snapshot_state()
        target_snapshot = self._history_undo.pop()
        self._history_redo.append(current_snapshot)
        self._restore_history_snapshot(target_snapshot)
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _redo_last_action(self):
        if not self._history_redo:
            return
        current_snapshot = self._history_current or self._snapshot_state()
        target_snapshot = self._history_redo.pop()
        self._history_undo.append(current_snapshot)
        self._restore_history_snapshot(target_snapshot)
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        has_project = self.current_project is not None
        can_undo = has_project and bool(self._history_undo)
        can_redo = has_project and bool(self._history_redo)
        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)

    def _page_widgets_in_order(self) -> List[DashboardPageWidget]:
        widgets: List[DashboardPageWidget] = []
        if not hasattr(self, "page_stack"):
            return widgets
        for index in range(self.page_stack.count()):
            widget = self.page_stack.widget(index)
            if isinstance(widget, DashboardPageWidget):
                widgets.append(widget)
        return widgets

    def _page_widget_for_id(self, page_id: str) -> Optional[DashboardPageWidget]:
        key = str(page_id or "").strip()
        if not key:
            return None
        widget = self._page_widgets.get(key)
        if widget is not None:
            return widget
        for candidate in self._page_widgets.values():
            if getattr(candidate, "page_id", "") == key:
                return candidate
        for candidate in self._page_widgets.values():
            try:
                if candidate.page_id == key:
                    return candidate
            except Exception:
                continue
        return None

    def _clear_page_tab_buttons(self):
        if self.page_strip is not None:
            self.page_strip.clear_pages()

    def _scroll_page_tabs(self, delta: int):
        if self.page_strip is not None:
            self.page_strip.scroll_by(delta)

    def _ensure_page_button_visible(self, page_id: str):
        if self.page_strip is not None:
            self.page_strip.ensure_page_visible(page_id)

    def _select_page_button(self, page_id: str):
        target_id = str(page_id or "").strip()
        self._selected_page_id = target_id
        if self.page_strip is not None:
            self.page_strip.set_active_page(target_id)

    def _handle_page_tabs_moved(self, from_index: int, to_index: int):
        if self.current_project is None or self.page_strip is None:
            return
        order = list(self.page_strip.page_ids() or [])
        if not order:
            return
        if len(order) != len(self._page_widgets):
            self._rebuild_page_stack(self._current_page_id())
            return
        existing_widgets = dict(self._page_widgets)
        current_id = self._current_page_id() or self.current_project.active_page_id or order[0]
        self._suspend_canvas_events = True
        try:
            if hasattr(self, "page_stack"):
                while self.page_stack.count():
                    widget = self.page_stack.widget(0)
                    self.page_stack.removeWidget(widget)
            ordered_widgets: Dict[str, DashboardPageWidget] = {}
            for page_id in order:
                widget = existing_widgets.pop(page_id, None)
                if widget is None:
                    continue
                self.page_stack.addWidget(widget)
                ordered_widgets[page_id] = widget
            for widget in list(existing_widgets.values()):
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except Exception:
                    log_exception("falha opcional ignorada")
            self._page_widgets = ordered_widgets
            self._selected_page_id = str(current_id or "").strip()
            self._set_active_page(str(current_id or ""), sync_project=False, update_tabs=True)
            self._sync_project_from_pages(str(current_id or ""))
        finally:
            self._suspend_canvas_events = False
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_page_stack_current_changed(self, index: int):
        if self._suspend_canvas_events or index < 0:
            return
        widget = self.page_stack.widget(index) if hasattr(self, "page_stack") else None
        if not isinstance(widget, DashboardPageWidget):
            return
        self.canvas = widget.canvas
        self._selected_page_id = str(widget.page_id or "").strip()
        if self.page_strip is not None:
            self.page_strip.set_active_page(widget.page_id)
        if self.current_project is not None:
            self.current_project.active_page_id = str(widget.page_id or "").strip()
            try:
                self.current_project.set_active_page(widget.page_id)
            except Exception:
                log_exception("falha opcional ignorada")
        try:
            self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
        except Exception:
            log_exception("falha opcional ignorada")
        self._update_filters_bar()

    def _page_index_from_id(self, page_id: str) -> int:
        if self.current_project is None:
            return -1
        target_id = str(page_id or "").strip()
        for index, page in enumerate(list(self.current_project.pages or [])):
            if str(page.page_id or "").strip() == target_id:
                return index
        return -1

    def _current_page_id(self) -> str:
        if hasattr(self, "page_stack") and self.page_stack.count() > 0:
            candidate = self.page_stack.currentWidget()
            if isinstance(candidate, DashboardPageWidget):
                return str(candidate.page_id or "").strip()
        if self.current_project is not None:
            current_id = str(self.current_project.active_page_id or "").strip()
            if current_id:
                return current_id
        if self._selected_page_id:
            return str(self._selected_page_id).strip()
        return ""

    def _active_page_widget(self) -> Optional[DashboardPageWidget]:
        current_id = self._current_page_id()
        if current_id:
            widget = self._page_widget_for_id(current_id)
            if widget is not None:
                return widget
        if hasattr(self, "page_stack") and self.page_stack.count() > 0:
            candidate = self.page_stack.currentWidget()
            if isinstance(candidate, DashboardPageWidget):
                return candidate
        return None

    def _active_canvas(self) -> Optional[DashboardCanvas]:
        widget = self._active_page_widget()
        if widget is None:
            return None
        return widget.canvas

    def _sync_active_canvas_alias(self):
        self.canvas = self._active_canvas()
        widget = self._active_page_widget()
        if widget is not None:
            try:
                self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
            except Exception:
                log_exception("falha opcional ignorada")

    def _page_display_title(self, index: int) -> str:
        return _rt("Pagina {index}", index=max(1, int(index or 1)))

    def _create_page_widget(self, page: DashboardPage) -> DashboardPageWidget:
        widget = DashboardPageWidget(page, self.page_stack)
        self._apply_canvas_style_to_widget(widget, self._project_canvas_style())
        widget.itemsChanged.connect(lambda page_id, self=self: self._handle_canvas_changed(page_id))
        widget.filtersChanged.connect(
            lambda page_id, summary, self=self: self._handle_canvas_filters_changed(summary, page_id)
        )
        widget.zoomChanged.connect(lambda page_id, zoom, self=self: self._handle_canvas_zoom_changed(zoom, page_id))
        widget.itemSelectionChanged.connect(
            lambda page_id, item_id, item_widget, self=self: self._handle_canvas_item_selection(page_id, item_id, item_widget)
        )
        widget.fieldBindingDropRequested.connect(
            lambda page_id, item_id, slot_name, payload, self=self: self._handle_canvas_field_binding_drop(page_id, item_id, slot_name, payload)
        )
        widget.visualPanelRequested.connect(
            lambda page_id, item_id, self=self: self._handle_canvas_visual_panel_requested(page_id, item_id)
        )
        widget.canvas.emptyCanvasContextMenuRequested.connect(
            lambda pos, page_id=widget.page_id, self=self: self._open_canvas_context_menu(pos, page_id)
        )
        return widget

    def _clear_page_widgets(self):
        if not hasattr(self, "page_stack"):
            self._page_widgets.clear()
            return
        blocked = self.page_stack.blockSignals(True)
        try:
            while self.page_stack.count():
                widget = self.page_stack.widget(0)
                self.page_stack.removeWidget(widget)
        finally:
            self.page_stack.blockSignals(blocked)
        for widget in list(self._page_widgets.values()):
            try:
                widget.setParent(None)
                widget.deleteLater()
            except Exception:
                log_exception("falha opcional ignorada")
        self._page_widgets.clear()

    def _rebuild_page_stack(self, active_page_id: Optional[str] = None):
        if self.current_project is None:
            self._clear_page_widgets()
            return
        pages = [page.normalized() for page in list(self.current_project.pages or [])]
        if not pages:
            pages = [DashboardPage(title=self._page_display_title(1)).normalized()]
        if self._single_page_mode and len(pages) > 1:
            target_id = str(active_page_id or self.current_project.active_page_id or "").strip()
            selected = None
            for page in pages:
                if str(page.page_id or "").strip() == target_id:
                    selected = page.normalized()
                    break
            if selected is None:
                selected = pages[0].normalized()
            pages = [selected]
        self.current_project.pages = pages
        self.current_project.active_page_id = pages[0].page_id
        existing_widgets = dict(self._page_widgets)
        stack_blocked = False
        if hasattr(self, "page_stack"):
            stack_blocked = self.page_stack.blockSignals(True)
            while self.page_stack.count():
                widget = self.page_stack.widget(0)
                self.page_stack.removeWidget(widget)
        self._page_widgets = {}
        try:
            for page in pages:
                widget = existing_widgets.pop(page.page_id, None)
                if widget is None:
                    widget = self._create_page_widget(page)
                else:
                    widget.apply_page(page)
                    widget.set_page_identity(page.page_id, page.title)
                self._page_widgets[widget.page_id] = widget
                self.page_stack.addWidget(widget)
            for widget in list(existing_widgets.values()):
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except Exception:
                    log_exception("falha opcional ignorada")
        finally:
            if hasattr(self, "page_stack"):
                self.page_stack.blockSignals(stack_blocked)
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or pages[0].page_id or "").strip()
        self._refresh_page_tabs(resolved_active_id)
        self._set_active_page(resolved_active_id, sync_project=False, update_tabs=False)

    def _refresh_page_tabs(self, active_page_id: Optional[str] = None):
        if self.page_strip is None:
            return
        pages = list(self.current_project.pages or []) if self.current_project is not None else []
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or "").strip()
        if not resolved_active_id and pages:
            resolved_active_id = str(pages[0].page_id or "").strip()
        page_defs = []
        for index, page in enumerate(pages, start=1):
            title = str(page.title or "").strip() or self._page_display_title(index)
            page_defs.append((str(page.page_id or "").strip(), title))
        self.page_strip.set_pages(page_defs, resolved_active_id)

    def _sync_project_from_pages(self, active_page_id: Optional[str] = None):
        if self.current_project is None:
            return
        pages: List[DashboardPage] = []
        for widget in self._page_widgets_in_order():
            try:
                pages.append(widget.page_state())
            except Exception:
                continue
        if not pages:
            pages = [DashboardPage(title=self._page_display_title(1)).normalized()]
        if self._single_page_mode and len(pages) > 1:
            target_id = str(active_page_id or self.current_project.active_page_id or "").strip()
            selected = None
            for page in pages:
                if str(page.page_id or "").strip() == target_id:
                    selected = page.normalized()
                    break
            if selected is None:
                selected = pages[0].normalized()
            pages = [selected]
        self.current_project.pages = pages
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or pages[0].page_id or "").strip()
        if not resolved_active_id:
            resolved_active_id = pages[0].page_id
        self.current_project.active_page_id = resolved_active_id
        self.current_project.set_active_page(resolved_active_id)
        self.current_project.edit_mode = bool(self.edit_mode_btn.isChecked())

    def _set_active_page(self, page_id: str, sync_project: bool = True, update_tabs: bool = True):
        if self.current_project is None:
            self.canvas = None
            return
        target_id = str(page_id or "").strip()
        widget = self._page_widget_for_id(target_id)
        if widget is None:
            widget = self._active_page_widget()
        if widget is None:
            return
        if hasattr(self, "page_stack"):
            current_index = self.page_stack.indexOf(widget)
            if current_index >= 0:
                if self.page_stack.currentIndex() != current_index:
                    self.page_stack.setCurrentIndex(current_index)
        self.canvas = widget.canvas
        self._selected_page_id = str(widget.page_id or "").strip()
        self.current_project.active_page_id = str(widget.page_id or "").strip()
        if update_tabs:
            self._select_page_button(widget.page_id)
        try:
            self.current_project.set_active_page(widget.page_id)
        except Exception:
            log_exception("falha opcional ignorada")
        if sync_project:
            self._sync_project_from_pages(widget.page_id)
        try:
            self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
        except Exception:
            log_exception("falha opcional ignorada")

    def _page_state_by_id(self, page_id: str) -> Optional[DashboardPage]:
        key = str(page_id or "").strip()
        if not key or self.current_project is None:
            return None
        for page in list(self.current_project.pages or []):
            if str(page.page_id or "").strip() == key:
                return page
        return None

    def _add_page(self, checked: bool = False, title: Optional[str] = None, activate: bool = True):
        if self._single_page_mode:
            return
        if self._is_adding_page:
            return
        self._is_adding_page = True
        try:
            if self.current_project is None:
                # Creating the first page must stop here; otherwise we create
                # one blank project page and immediately add a second one.
                self._create_blank_project(_rt("Novo painel"))
                return
            if self.current_project is None:
                return
            current_count = len(list(self.current_project.pages or []))
            page_title = str(title or "").strip() or self._page_display_title(current_count + 1)
            page = DashboardPage(title=page_title).normalized()
            widget = self._create_page_widget(page)
            self._page_widgets[widget.page_id] = widget
            self.page_stack.addWidget(widget)
            self.current_project.pages = list(self.current_project.pages or []) + [page]
            self.current_project.active_page_id = page.page_id
            if activate:
                self._refresh_page_tabs(page.page_id)
                self._set_active_page(page.page_id, sync_project=True, update_tabs=False)
            else:
                self._refresh_page_tabs(self.current_project.active_page_id)
                self._sync_project_from_pages(self.current_project.active_page_id)
            self._dirty = True
            self._commit_history_if_changed()
            self._refresh_ui_state()
        finally:
            self._is_adding_page = False

    def _delete_current_page(self):
        self._delete_page_by_id(self._current_page_id())

    def _delete_page_by_id(self, page_id: str):
        if self._single_page_mode:
            return
        page_index = self._page_index_from_id(page_id)
        if page_index < 0 and self.page_strip is not None:
            try:
                order = list(self.page_strip.page_ids() or [])
            except Exception:
                order = []
            if order and self.current_project is not None and len(order) == len(list(self.current_project.pages or [])):
                try:
                    page_index = order.index(str(page_id or "").strip())
                except Exception:
                    page_index = -1
        if page_index < 0 or self.current_project is None:
            return
        pages = list(self.current_project.pages or [])
        if len(pages) <= 1:
            slim_message(self, _rt("Model"), _rt("O painel precisa manter ao menos uma pagina."))
            return
        pages.pop(page_index)
        self.current_project.pages = pages
        next_index = min(page_index, len(pages) - 1)
        next_page = pages[next_index]
        self.current_project.active_page_id = next_page.page_id
        self._selected_page_id = next_page.page_id
        self._dirty = True
        self._rebuild_page_stack(next_page.page_id)
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _rename_page_by_id(self, page_id: str, title: str):
        if self.current_project is None:
            return
        page = self._page_state_by_id(page_id)
        new_title = str(title or "").strip()
        if page is None or not new_title:
            return
        page.title = new_title
        widget = self._page_widget_for_id(page.page_id)
        if widget is not None:
            widget.set_page_identity(page.page_id, new_title)
        if self.page_strip is not None:
            self.page_strip.update_page_title(page.page_id, new_title)
        self._sync_project_from_pages(self._current_page_id() or page.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _build_model_chart_item_from_builder(self) -> Optional[DashboardChartItem]:
        layer = self._current_builder_layer()
        if layer is None or not layer.isValid():
            slim_message(self, _rt("Model"), _rt("Selecione uma camada valida para criar o grafico."))
            return None
        dimension_field = str(self.builder_dimension_combo.currentData() or "").strip()
        if not dimension_field:
            slim_message(self, _rt("Model"), _rt("Selecione o campo de categoria."))
            return None
        value_field = str(self.builder_value_combo.currentData() or "__count__").strip() or "__count__"
        aggregation = str(self.builder_agg_combo.currentData() or "count").strip().lower() or "count"
        chart_type = self._current_builder_chart_type()
        top_n = max(3, int(self.builder_topn_spin.value()))

        dimension_field = self._resolve_layer_field_name(layer, dimension_field)
        if not dimension_field:
            slim_message(self, _rt("Model"), _rt("O campo de categoria nao existe na camada selecionada."))
            return None
        if value_field != "__count__":
            value_field = self._resolve_layer_field_name(layer, value_field)
            if not value_field:
                slim_message(self, _rt("Model"), _rt("O campo de metrica nao existe na camada selecionada."))
                return None

        grouped: Dict[str, Dict[str, object]] = {}
        has_numeric_values = False
        for feature in layer.getFeatures():
            raw_category = feature.attribute(dimension_field)
            category = str(raw_category).strip() if raw_category is not None else ""
            if not category:
                category = "(vazio)"
            bucket = grouped.setdefault(
                category,
                {
                    "raw_category": raw_category if raw_category is not None else category,
                    "feature_ids": [],
                    "sum": 0.0,
                    "count": 0,
                    "min": None,
                    "max": None,
                },
            )
            try:
                bucket["feature_ids"].append(int(feature.id()))
            except Exception:
                log_exception("falha opcional ignorada")

            if value_field == "__count__":
                value = 1.0
            else:
                value = self._safe_float(feature.attribute(value_field))
                if value is None:
                    continue
                has_numeric_values = True

            bucket["sum"] = float(bucket.get("sum") or 0.0) + float(value)
            bucket["count"] = int(bucket.get("count") or 0) + 1
            current_min = bucket.get("min")
            current_max = bucket.get("max")
            bucket["min"] = float(value) if current_min is None else min(float(current_min), float(value))
            bucket["max"] = float(value) if current_max is None else max(float(current_max), float(value))

        if value_field != "__count__" and not has_numeric_values:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel calcular valores numericos para esse campo."))
            return None
        if not grouped:
            slim_message(self, _rt("Model"), _rt("A camada nao possui dados suficientes para montar o grafico."))
            return None

        rows: List[Dict[str, object]] = []
        for category, bucket in grouped.items():
            count = int(bucket.get("count") or 0)
            if count <= 0:
                continue
            if aggregation == "avg":
                metric_value = float(bucket.get("sum") or 0.0) / float(count)
            elif aggregation == "min":
                metric_value = float(bucket.get("min") or 0.0)
            elif aggregation == "max":
                metric_value = float(bucket.get("max") or 0.0)
            elif aggregation == "sum":
                metric_value = float(bucket.get("sum") or 0.0)
            else:
                metric_value = float(count)
            rows.append(
                {
                    "category": str(category),
                    "value": metric_value,
                    "raw_category": bucket.get("raw_category"),
                    "feature_ids": list(bucket.get("feature_ids") or []),
                }
            )

        if not rows:
            slim_message(self, _rt("Model"), _rt("Sem resultados para os campos selecionados."))
            return None

        rows.sort(key=lambda item: float(item.get("value") or 0.0), reverse=True)
        truncated = len(rows) > top_n
        rows = rows[:top_n]

        categories = [str(item.get("category") or "") for item in rows]
        values = [float(item.get("value") or 0.0) for item in rows]
        raw_categories = [item.get("raw_category") for item in rows]
        feature_groups = [list(item.get("feature_ids") or []) for item in rows]

        agg_label = {
            "count": _rt("Contagem"),
            "sum": _rt("Soma"),
            "avg": _rt("Media"),
            "min": _rt("Minimo"),
            "max": _rt("Maximo"),
        }.get(aggregation, _rt("Contagem"))
        value_label = _rt("Contagem") if value_field == "__count__" else _rt("{agg_label} de {value_field}", agg_label=agg_label, value_field=value_field)
        title_text = str(self.builder_title_edit.text() or "").strip()
        if not title_text:
            if value_field == "__count__":
                title_text = _rt("Contagem por {dimension_field}", dimension_field=dimension_field)
            else:
                title_text = _rt("{agg_label} de {value_field} por {dimension_field}", agg_label=agg_label, value_field=value_field, dimension_field=dimension_field)

        payload = ChartPayload.build(
            chart_type=chart_type,
            title=title_text,
            categories=categories,
            values=values,
            value_label=value_label,
            truncated=truncated,
            selection_layer_id=layer.id(),
            selection_layer_name=layer.name(),
            category_field=dimension_field,
            raw_categories=raw_categories,
            category_feature_ids=feature_groups,
        )

        item_id = uuid.uuid4().hex
        visual_state = ChartVisualState(chart_type=chart_type, show_legend=chart_type in {"pie", "donut", "funnel"})
        value_binding_field = dimension_field if value_field == "__count__" else value_field
        value_binding_label = _rt("Contagem") if value_field == "__count__" else value_field
        binding = DashboardChartBinding(
            chart_id=item_id,
            chart_type=chart_type,
            source_id=layer.id(),
            dimension_field=dimension_field,
            semantic_field_key=dimension_field,
            semantic_field_aliases=[dimension_field],
            measure_field="" if value_field == "__count__" else value_field,
            aggregation=aggregation,
            top_n=top_n,
            title_override=title_text,
            source_name=layer.name(),
            bindings={
                ROLE_X_AXIS: [
                    FieldBindingItem(
                        field=dimension_field,
                        display_name=dimension_field,
                        type=self._field_kind_for_layer_field(layer, dimension_field),
                        aggregation="none",
                        role=ROLE_X_AXIS,
                        order=0,
                    )
                ],
                ROLE_VALUES: [
                    FieldBindingItem(
                        field=value_binding_field,
                        display_name=value_binding_label,
                        type=self._field_kind_for_layer_field(layer, value_binding_field),
                        aggregation=aggregation,
                        role=ROLE_VALUES,
                        order=0,
                    )
                ],
            },
        ).normalized()
        subtitle = f"{layer.name()} - {dimension_field} - {value_label}"
        return DashboardChartItem(
            item_id=item_id,
            origin="model_builder",
            payload=payload,
            visual_state=visual_state,
            binding=binding,
            title=title_text,
            subtitle=subtitle,
            source_meta={
                "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
                "config": {"row_field": dimension_field, "semantic_field_key": dimension_field, "aggregation": aggregation},
            },
        )

    def _add_chart_from_builder(self):
        item = self._build_model_chart_item_from_builder()
        if item is None:
            return
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _open_canvas_context_menu(self, global_pos, page_id: Optional[str] = None):
        menu = QMenu(self)
        add_chart_action = menu.addAction(_rt("Adicionar grafico em branco"))
        open_panel_action = menu.addAction(_rt("Abrir painel de camada"))
        chosen = menu.exec_(global_pos)
        if chosen is add_chart_action:
            self._add_chart_from_builder()
        elif chosen is open_panel_action:
            self._set_builder_panel_open(True, focus=True)

    def _build_action_card(self, title: str, description: str, icon_name: str) -> QWidget:
        card = _ModelCardAction(title, description, icon_name, self)
        return card

    def current_project_name(self) -> str:
        if self.current_project is None:
            return ""
        return str(self.current_project.name or "")

    def prompt_add_chart(self, snapshot: Dict[str, object]) -> bool:
        chart_title = str(snapshot.get("title") or snapshot.get("payload", {}).get("title", _rt("Grafico")))
        dialog = DashboardAddDialog(
            chart_title,
            has_current_project=self.current_project is not None,
            current_project_name=self.current_project_name(),
            recent_projects=self.store.load_recents(),
            parent=self,
        )
        if dialog.exec_() != dialog.Accepted:
            return False

        selection = dialog.selection()
        mode = selection.get("mode")
        if mode == "new":
            self._create_blank_project(selection.get("name") or _rt("Novo painel"))
        elif mode == "file":
            path = selection.get("path") or ""
            if not path:
                path, _ = QFileDialog.getOpenFileName(
                    self,
                    _rt("Escolher painel salvo"),
                    self.store.default_directory(),
                    f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
                )
            if not path:
                return False
            self.open_project(path)
        elif self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))

        self.add_chart_snapshot(snapshot)
        return True

    def add_chart_snapshot(self, snapshot: Dict[str, object]):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        item = DashboardChartItem.from_chart_snapshot(snapshot)
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def new_project(self):
        self._create_blank_project(_rt("Novo painel"))

    def close_project(self):
        if self.current_project is not None and self._dirty:
            answer = slim_question(
                self,
                _rt("Model"),
                _rt("O painel atual tem alterações não salvas. Deseja salvar antes de fechar?"),
                buttons=QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                default_button=QMessageBox.Yes,
            )
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Yes:
                self.save_project()
                if self.current_project is not None and self._dirty:
                    return
        self.current_project = None
        self.current_path = ""
        self._dirty = False
        self._selected_page_id = ""
        self._suspend_canvas_events = True
        try:
            self._clear_page_widgets()
            self._clear_page_tab_buttons()
            self.canvas = None
        finally:
            self._suspend_canvas_events = False
        self._refresh_builder_layers()
        self._refresh_recents()
        self._reset_history()
        self._refresh_ui_state()

    def _create_blank_project(self, name: str):
        page = DashboardPage(title=self._page_display_title(1)).normalized()
        self.current_project = DashboardProject(
            name=str(name or _rt("Novo painel")),
            pages=[page],
            active_page_id=page.page_id,
        )
        self.current_project.edit_mode = bool(self.edit_mode_btn.isChecked())
        self.current_project.source_meta["canvas_style"] = self._default_canvas_style()
        self.current_path = ""
        self._dirty = False
        self._rebuild_page_stack(page.page_id)
        self._set_active_page(page.page_id, sync_project=False, update_tabs=False)
        self.set_edit_mode(bool(self.edit_mode_btn.isChecked()))
        self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
        self._refresh_builder_layers()
        self._reset_history()
        self._refresh_ui_state()

    def open_project(self, path: Optional[str] = None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                _rt("Abrir painel salvo"),
                self.store.default_directory(),
                f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
            )
        if not path:
            return
        try:
            project = self.store.load_project(path)
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel abrir o painel: {error}", error=exc))
            return
        try:
            if bool(project.source_meta.get("_legacy_single_page")) and len(list(project.pages or [])) == 1:
                legacy_page = list(project.pages or [])[0].normalized()
                project_name = str(project.name or "").strip().lower()
                page_title = str(legacy_page.title or "").strip().lower()
                if not page_title or page_title == project_name:
                    legacy_page.title = self._page_display_title(1)
                    project.pages = [legacy_page]
                    project.active_page_id = legacy_page.page_id
                    project.set_active_page(legacy_page.page_id)
        except Exception:
            log_exception("falha opcional ignorada")
        source_meta = dict(getattr(project, "source_meta", {}) or {})
        source_meta["canvas_style"] = self._normalized_canvas_style(source_meta.get("canvas_style"))
        project.source_meta = source_meta
        self.current_project = project
        self.current_path = self.store.normalize_path(path)
        self._dirty = False
        self._selected_page_id = ""
        self._rebuild_page_stack(project.active_page_id or (project.pages[0].page_id if project.pages else ""))
        self.edit_mode_btn.blockSignals(True)
        try:
            self.edit_mode_btn.setChecked(bool(project.edit_mode))
        finally:
            self.edit_mode_btn.blockSignals(False)
        self.set_edit_mode(bool(project.edit_mode))
        self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
        self._refresh_builder_layers()
        self._refresh_recents()
        self._reset_history()
        self._refresh_ui_state()

    def import_project(self):
        self.open_project()

    def save_project(self, save_as: bool = False):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        active_widget = self._active_page_widget()
        if active_widget is not None:
            self._sync_project_from_pages(active_widget.page_id)
        target_path = self.current_path
        if save_as or not target_path:
            suggested_name = (self.current_project.name or _rt("painel")).strip().replace(" ", "_")
            suggested_path = os.path.join(self.store.default_directory(), suggested_name)
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                _rt("Salvar painel"),
                suggested_path,
                f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
            )
        if not target_path:
            return
        try:
            self.current_path = self.store.save_project(target_path, self.current_project)
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel salvar o painel: {error}", error=exc))
            return
        self._dirty = False
        self._history_current = self._snapshot_state()
        self._refresh_recents()
        self._update_undo_redo_buttons()
        self._refresh_ui_state()

    def export_project(self):
        active_canvas = self._active_canvas()
        if active_canvas is None or not active_canvas.has_items():
            slim_message(self, _rt("Model"), _rt("Adicione ao menos um grafico antes de exportar."))
            return
        suggested_name = (self.current_project_name() or _rt("painel_model")).strip().replace(" ", "_")
        suggested_path = os.path.join(self.store.default_directory(), f"{suggested_name}.png")
        path, _ = QFileDialog.getSaveFileName(self, _rt("Exportar painel"), suggested_path, "PNG (*.png)")
        if not path:
            return
        if not active_canvas.export_image(path):
            slim_message(self, _rt("Model"), _rt("Nao foi possivel exportar a imagem do painel."))
            return
        slim_message(self, _rt("Model"), _rt("Painel exportado para:\n{path}", path=path))

    def _sync_mode_switch_state(self, editing_enabled: bool):
        state_text = _rt("Edição") if editing_enabled else _rt("Pré-visualizar")
        self.mode_state_label.setText(state_text)
        self.mode_state_label.setProperty("modeState", "editing" if editing_enabled else "preview")
        self.mode_state_label.style().unpolish(self.mode_state_label)
        self.mode_state_label.style().polish(self.mode_state_label)
        self.mode_toggle.blockSignals(True)
        try:
            self.mode_toggle.setChecked(bool(editing_enabled), animated=False)
        finally:
            self.mode_toggle.blockSignals(False)

    def _handle_mode_toggle(self, checked: bool):
        target = bool(checked)
        self.edit_mode_btn.blockSignals(True)
        try:
            self.edit_mode_btn.setChecked(target)
        finally:
            self.edit_mode_btn.blockSignals(False)
        self.set_edit_mode(target)

    def _sync_visual_side_tab_buttons(self):
        active_tab = str(getattr(self, "_active_visual_side_tab", "build") or "build")
        if active_tab not in {"build", "format"}:
            active_tab = "build"
        if hasattr(self, "visual_side_stack"):
            self.visual_side_stack.setCurrentIndex(1 if active_tab == "format" else 0)
        for button, checked in (
            (getattr(self, "visual_data_tab_btn", None), active_tab == "build"),
            (getattr(self, "visual_format_tab_btn", None), active_tab == "format"),
        ):
            if button is None:
                continue
            button.blockSignals(True)
            try:
                button.setChecked(bool(checked))
            finally:
                button.blockSignals(False)

    def _set_visual_side_tab(self, tab_name: str):
        target = "format" if str(tab_name or "").strip().lower() == "format" else "build"
        if target == "format":
            self._set_visual_panel_open(True, focus=False)
        else:
            self._set_builder_panel_open(True, focus=False)

    def _set_builder_panel_open(self, enabled: bool, *, focus: bool = False):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        active = bool(enabled) and bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page
        self._builder_panel_open = bool(active)
        if active:
            self._visual_panel_open = False
            self._active_visual_side_tab = "build"
            self._sync_builder_selection_state()
            self._sync_visual_side_tab_buttons()
        self.visual_side_panel.setVisible(active or self._visual_panel_open)
        self.data_panel.setVisible(bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self.create_chart_btn.blockSignals(True)
        try:
            if self.create_chart_btn.isChecked() != active:
                self.create_chart_btn.setChecked(active)
        finally:
            self.create_chart_btn.blockSignals(False)
        self.format_visual_btn.blockSignals(True)
        try:
            if self.format_visual_btn.isChecked() != bool(self._visual_panel_open):
                self.format_visual_btn.setChecked(bool(self._visual_panel_open))
        finally:
            self.format_visual_btn.blockSignals(False)
        if active and focus:
            try:
                self.builder_layer_combo.setFocus(Qt.TabFocusReason)
            except Exception:
                log_exception("falha opcional ignorada")

    def _handle_create_chart_toggle(self, checked: bool):
        self._set_builder_panel_open(bool(checked), focus=bool(checked))

    def _ensure_canvas_splitter_sizes(self):
        splitter = getattr(self, "canvas_splitter", None)
        if splitter is None:
            return
        try:
            sizes = list(splitter.sizes())
            total = sum(int(size or 0) for size in sizes)
            if total <= 0 or len(sizes) < 3:
                return
            visual_visible = bool(self.visual_side_panel.isVisible())
            data_visible = bool(self.data_panel.isVisible())
            target_visual = int(min(max(sizes[1] if sizes[1] > 0 else 292, 260), 420)) if visual_visible else 0
            target_data = int(min(max(sizes[2] if sizes[2] > 0 else 292, 260), 420)) if data_visible else 0
            if visual_visible and sizes[1] < 220:
                target_visual = 292
            if data_visible and sizes[2] < 220:
                target_data = 292
            target_canvas = max(360, total - target_visual - target_data)
            splitter.setSizes([target_canvas, target_visual, target_data])
        except Exception:
            log_exception("falha opcional ignorada")

    def _set_visual_panel_open(self, enabled: bool, *, focus: bool = False):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        active = bool(enabled) and bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page
        self._visual_panel_open = bool(active)
        if active:
            self._builder_panel_open = False
            self._active_visual_side_tab = "format"
            self._sync_visual_side_tab_buttons()
        self.visual_side_panel.setVisible(active or self._builder_panel_open)
        self.data_panel.setVisible(bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self.format_visual_btn.blockSignals(True)
        try:
            if self.format_visual_btn.isChecked() != active:
                self.format_visual_btn.setChecked(active)
        finally:
            self.format_visual_btn.blockSignals(False)
        self.create_chart_btn.blockSignals(True)
        try:
            if self.create_chart_btn.isChecked() != self._builder_panel_open:
                self.create_chart_btn.setChecked(self._builder_panel_open)
        finally:
            self.create_chart_btn.blockSignals(False)
        if not active:
            self._sync_visual_side_tab_buttons()
        if not active:
            self.visual_panel.clear_selection()
            return
        item_widget = None
        active_page = self._active_page_widget()
        if active_page is not None:
            item_widget = active_page.canvas.selected_item_widget()
        if item_widget is None:
            self.visual_panel.clear_selection()
            return
        self.visual_panel.set_current_item(item_widget)
        if focus:
            try:
                self.visual_panel.setFocus(Qt.TabFocusReason)
            except Exception:
                log_exception("falha opcional ignorada")

    def _handle_format_visual_toggle(self, checked: bool):
        self._set_visual_panel_open(bool(checked), focus=bool(checked))

    def set_edit_mode(self, enabled: bool):
        enabled = bool(enabled)
        for widget in self._page_widgets_in_order():
            try:
                widget.set_edit_mode(enabled)
            except Exception:
                continue
        self.create_chart_btn.setVisible(enabled and self.current_project is not None)
        self.format_visual_btn.setVisible(enabled and self.current_project is not None)
        if enabled and self.current_project is not None:
            self._builder_panel_open = True
            self._visual_panel_open = False
        else:
            self._builder_panel_open = False
            self._visual_panel_open = False
        self._set_builder_panel_open(self._builder_panel_open)
        self._set_visual_panel_open(self._visual_panel_open)
        self.data_panel.setVisible(enabled and self.current_project is not None and self.body_stack.currentWidget() is self.canvas_page)
        self._ensure_canvas_splitter_sizes()
        if self.edit_mode_btn.isChecked() != enabled:
            self.edit_mode_btn.blockSignals(True)
            try:
                self.edit_mode_btn.setChecked(enabled)
            finally:
                self.edit_mode_btn.blockSignals(False)
        self._sync_mode_switch_state(enabled)
        if self.current_project is not None:
            self.current_project.edit_mode = enabled
        self._refresh_ui_state()

    def _zoom_canvas_in(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "zoom_in"):
            active_canvas.zoom_in()

    def _zoom_canvas_out(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "zoom_out"):
            active_canvas.zoom_out()

    def _zoom_canvas_reset(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "reset_zoom"):
            active_canvas.reset_zoom()

    def _handle_canvas_zoom_changed(self, zoom: float, page_id: Optional[str] = None):
        if self.current_project is not None and page_id:
            self._sync_project_from_pages(page_id)
        try:
            percent = int(round(float(zoom) * 100.0))
        except Exception:
            percent = 100
        if not page_id or page_id == self._current_page_id():
            self._sync_zoom_controls(percent)

    def _zoom_slider_changed(self, value: int):
        if self._syncing_zoom_controls:
            return
        try:
            zoom_value = max(0.6, min(2.0, float(value) / 100.0))
        except Exception:
            zoom_value = 1.0
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "set_zoom"):
            active_canvas.set_zoom(zoom_value)
    def _sync_zoom_controls(self, percent: int):
        self._syncing_zoom_controls = True
        try:
            value = max(60, min(200, int(percent)))
            self.zoom_label.setText(f"{value}%")
            if self.zoom_slider.value() != value:
                self.zoom_slider.setValue(value)
        finally:
            self._syncing_zoom_controls = False

    def _update_footer_visibility(self):
        self.footer_bar.setVisible(self.current_project is not None)

    def _update_toolbar_visibility(self):
        has_project = self.current_project is not None
        show_project_actions = has_project
        for button in (
            self.undo_btn,
            self.redo_btn,
            self.save_btn,
            self.save_as_btn,
            self.export_btn,
            self.edit_mode_btn,
            self.format_visual_btn,
            self.settings_btn,
            self.close_project_btn,
        ):
            button.setVisible(show_project_actions)
        self.create_chart_btn.setVisible(show_project_actions and bool(self.edit_mode_btn.isChecked()))
        self.mode_switch_wrap.setVisible(show_project_actions)
        if has_project:
            self._configure_toolbar_icon_button(self.new_btn, "Walker-New.svg", _rt("Novo"))
            self._configure_toolbar_icon_button(self.open_btn, "Walker-Open.svg", _rt("Abrir"))
        else:
            self._configure_toolbar_text_icon_button(self.new_btn, "Walker-New.svg", _rt("Novo"), _rt("Novo"))
            self._configure_toolbar_text_icon_button(self.open_btn, "Walker-Open.svg", _rt("Abrir"), _rt("Abrir"))
        try:
            self.new_btn.style().unpolish(self.new_btn)
            self.new_btn.style().polish(self.new_btn)
            self.open_btn.style().unpolish(self.open_btn)
            self.open_btn.style().polish(self.open_btn)
        except Exception:
            log_exception("falha opcional ignorada")
        self._update_undo_redo_buttons()

    def _handle_canvas_changed(self, page_id: Optional[str] = None):
        if self._suspend_canvas_events:
            return
        if self.current_project is not None:
            self._sync_project_from_pages(page_id or self._current_page_id())
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_canvas_filters_changed(self, summary: Dict[str, object], page_id: Optional[str] = None):
        if self.current_project is not None:
            self._sync_project_from_pages(page_id or self._current_page_id())
        if not page_id or page_id == self._current_page_id():
            self._update_filters_bar(summary)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_canvas_item_selection(self, page_id: str, item_id: str, item_widget):
        if page_id and page_id != self._current_page_id():
            return
        self._sync_builder_selection_state()
        if not self.visual_side_panel.isVisible():
            return
        if item_widget is None:
            self.visual_panel.clear_selection()
            return
        self.visual_panel.set_current_item(item_widget)

    def _handle_canvas_field_binding_drop(self, page_id: str, item_id: str, slot_name: str, payload):
        if page_id and page_id != self._current_page_id():
            self._set_active_page(page_id, sync_project=True, update_tabs=True)
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return
        active_canvas.select_item(item_id, emit_signal=True)
        self._sync_builder_selection_state()
        self._apply_dropped_field_to_selected_visual(slot_name, payload)

    def _handle_canvas_visual_panel_requested(self, page_id: str, item_id: str):
        if page_id and page_id != self._current_page_id():
            self._set_active_page(page_id, sync_project=True, update_tabs=True)
        active_page = self._active_page_widget()
        if active_page is not None and item_id:
            active_page.canvas.select_item(item_id, emit_signal=False)
            item_widget = active_page.canvas.selected_item_widget()
            if item_widget is not None:
                self.visual_panel.set_current_item(item_widget)
        self._set_visual_panel_open(True, focus=False)

    def _update_filters_bar(self, summary: Optional[Dict[str, object]] = None):
        active_canvas = self._active_canvas()
        if summary is None and active_canvas is not None:
            summary = active_canvas.interaction_manager.active_filters_summary()
        summary = summary or {"items": [], "count": 0}
        items = list(summary.get("items") or [])
        if not self.edit_mode_btn.isChecked() or not items:
            self.filters_label.clear()
            self.clear_filters_btn.setVisible(False)
            self.filters_bar.setVisible(False)
            return
        self.filters_label.clear()
        self.clear_filters_btn.setVisible(True)
        self.filters_bar.setVisible(False)

    def _clear_model_filters(self):
        try:
            active_canvas = self._active_canvas()
            if active_canvas is not None:
                active_canvas.clear_filters()
        except Exception:
            log_exception("falha opcional ignorada")

    def _refresh_recents(self):
        while self.recents_layout.count():
            item = self.recents_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        recents = self.store.load_recents()
        if not recents:
            self.recents_placeholder.setVisible(True)
            self.recents_container.setVisible(False)
            return

        self.recents_placeholder.setVisible(False)
        self.recents_container.setVisible(True)
        for recent in recents:
            path = str(recent.get("path") or "")
            name = str(os.path.splitext(os.path.basename(path))[0] or recent.get("name") or "")
            card = _ModelRecentCard(name, path, self.recents_container)
            card.setMinimumHeight(68)
            card.clicked.connect(lambda selected_path=path: self.open_project(selected_path))
            self.recents_layout.addWidget(card)
        self.recents_layout.addStretch(1)

    def _refresh_ui_state(self):
        has_project = self.current_project is not None
        self.body_stack.setCurrentWidget(self.canvas_page if has_project else self.empty_page)
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        if has_project:
            active_id = self.current_project.active_page_id or (self.current_project.pages[0].page_id if self.current_project.pages else "")
            active_widget = self._active_page_widget()
            if active_widget is None or str(active_widget.page_id or "").strip() != str(active_id or "").strip():
                self._set_active_page(active_id, sync_project=False, update_tabs=True)
            else:
                self.canvas = active_widget.canvas
                self._select_page_button(active_id)
                try:
                    self._sync_zoom_controls(int(round(float(active_widget.zoom_value() or 1.0) * 100.0)))
                except Exception:
                    log_exception("falha opcional ignorada")
        else:
            self.canvas = None
        self.new_btn.setVisible(True)
        self.open_btn.setVisible(True)
        self._update_toolbar_visibility()
        self.close_project_btn.setVisible(has_project)
        self._set_builder_panel_open(self._builder_panel_open)
        self._set_visual_panel_open(self._visual_panel_open)
        self.data_panel.setVisible(has_project and bool(self.edit_mode_btn.isChecked()) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self._sync_builder_selection_state()
        self._update_footer_visibility()
        self._update_filters_bar()
        self.filters_bar.setVisible(bool(self.edit_mode_btn.isChecked()) and self.filters_bar.isVisible())
        self._sync_mode_switch_state(bool(self.edit_mode_btn.isChecked()))
        self._update_undo_redo_buttons()

