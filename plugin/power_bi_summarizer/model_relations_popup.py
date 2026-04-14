from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import QgsProject, QgsVectorLayer

from .dashboard_models import DashboardChartItem, DashboardChartRelation
from .slim_dialogs import slim_message


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _first_value(values) -> str:
    if values is None:
        return ""
    if isinstance(values, (list, tuple, set)):
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""
    return str(values or "").strip()


def _text_values(values) -> List[str]:
    results: List[str] = []
    seen = set()

    def _walk(item):
        if item is None:
            return
        if isinstance(item, (list, tuple, set)):
            for nested in item:
                _walk(nested)
            return
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            return
        seen.add(key)
        results.append(text)

    _walk(values)
    return results


def _type_group(type_name: str) -> str:
    text = str(type_name or "").strip().lower()
    if any(token in text for token in ("int", "double", "float", "real", "decimal", "numeric", "long", "short")):
        return "number"
    if any(token in text for token in ("date", "time", "timestamp")):
        return "datetime"
    if any(token in text for token in ("string", "text", "char")):
        return "text"
    if any(token in text for token in ("bool", "bit")):
        return "bool"
    return "unknown"


@dataclass
class _FieldOption:
    name: str
    type_name: str = ""

    def normalized_name(self) -> str:
        return _normalize_name(self.name)

    def group(self) -> str:
        return _type_group(self.type_name)


class ModelRelationsPopup(QDialog):
    def __init__(
        self,
        source_item: DashboardChartItem,
        target_item: DashboardChartItem,
        *,
        existing_relation: Optional[DashboardChartRelation] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("ModelRelationsPopup")
        self.setWindowTitle("Relacao entre graficos")
        self.setMinimumWidth(560)
        self._source_item = source_item
        self._target_item = target_item
        self._existing_relation = existing_relation.normalized() if existing_relation is not None else None
        self._remove_requested = False

        self._source_fields = self._collect_fields(self._source_item)
        self._target_fields = self._collect_fields(self._target_item)
        self._suggestions = self._build_suggestions()

        self._build_ui()
        self._apply_initial_selection()

    def remove_requested(self) -> bool:
        return bool(self._remove_requested)

    def selected_relation(self) -> Optional[DashboardChartRelation]:
        source_field = str(self.source_field_combo.currentText() or "").strip()
        target_field = str(self.target_field_combo.currentText() or "").strip()
        if not source_field or not target_field:
            return None
        interaction_mode = str(self.mode_combo.currentData() or "filter").strip().lower() or "filter"
        direction = str(self.direction_combo.currentData() or "both").strip().lower() or "both"
        relation_id = self._existing_relation.relation_id if self._existing_relation is not None else ""
        return DashboardChartRelation(
            relation_id=relation_id,
            source_chart_id=self._source_item.item_id,
            target_chart_id=self._target_item.item_id,
            source_id=str(self._source_item.binding.source_id or "").strip(),
            target_id=str(self._target_item.binding.source_id or "").strip(),
            source_field=source_field,
            target_field=target_field,
            interaction_mode=interaction_mode,
            direction=direction,
            active=bool(self.active_check.isChecked()),
        ).normalized()

    def _build_ui(self):
        self.setStyleSheet(
            """
            QDialog#ModelRelationsPopup {
                background: #FFFFFF;
            }
            QDialog#ModelRelationsPopup QLabel {
                color: #111827;
                font-size: 12px;
            }
            QDialog#ModelRelationsPopup QLabel[role="title"] {
                font-size: 14px;
                font-weight: 600;
            }
            QDialog#ModelRelationsPopup QLabel[role="subtle"] {
                color: #6B7280;
                font-size: 11px;
            }
            QDialog#ModelRelationsPopup QFrame#ModelRelationsInfoFrame {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #F9FAFB;
            }
            QDialog#ModelRelationsPopup QComboBox {
                min-height: 32px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 0 10px;
                background: #FFFFFF;
                color: #111827;
            }
            QDialog#ModelRelationsPopup QComboBox:focus {
                border-color: #2563EB;
            }
            QDialog#ModelRelationsPopup QPushButton {
                min-height: 30px;
                min-width: 92px;
                border-radius: 6px;
                border: 1px solid #D1D5DB;
                background: #FFFFFF;
                color: #111827;
                font-weight: 500;
            }
            QDialog#ModelRelationsPopup QPushButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QDialog#ModelRelationsPopup QPushButton#PrimaryActionButton {
                border-color: #2563EB;
                background: #EFF6FF;
                color: #1D4ED8;
            }
            QDialog#ModelRelationsPopup QPushButton#PrimaryActionButton:hover {
                background: #DBEAFE;
                border-color: #1D4ED8;
            }
            QDialog#ModelRelationsPopup QPushButton#DangerActionButton {
                border-color: #EF4444;
                background: #FEF2F2;
                color: #B91C1C;
            }
            QDialog#ModelRelationsPopup QPushButton#DangerActionButton:hover {
                border-color: #DC2626;
                background: #FEE2E2;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Relacao entre graficos", self)
        title.setProperty("role", "title")
        root.addWidget(title)

        info_frame = QFrame(self)
        info_frame.setObjectName("ModelRelationsInfoFrame")
        info_layout = QFormLayout(info_frame)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(6)

        source_title = self._source_item.display_title()
        target_title = self._target_item.display_title()
        info_layout.addRow("Grafico origem:", QLabel(source_title, info_frame))
        info_layout.addRow("Source id origem:", QLabel(str(self._source_item.binding.source_id or "-"), info_frame))
        info_layout.addRow("Grafico destino:", QLabel(target_title, info_frame))
        info_layout.addRow("Source id destino:", QLabel(str(self._target_item.binding.source_id or "-"), info_frame))
        root.addWidget(info_frame)

        fields_row = QHBoxLayout()
        fields_row.setContentsMargins(0, 0, 0, 0)
        fields_row.setSpacing(10)

        source_col = QVBoxLayout()
        source_col.setContentsMargins(0, 0, 0, 0)
        source_col.setSpacing(4)
        source_col.addWidget(QLabel("Campo origem", self))
        self.source_field_combo = QComboBox(self)
        for field in self._source_fields:
            self.source_field_combo.addItem(field.name)
        source_col.addWidget(self.source_field_combo)
        fields_row.addLayout(source_col, 1)

        target_col = QVBoxLayout()
        target_col.setContentsMargins(0, 0, 0, 0)
        target_col.setSpacing(4)
        target_col.addWidget(QLabel("Campo destino", self))
        self.target_field_combo = QComboBox(self)
        for field in self._target_fields:
            self.target_field_combo.addItem(field.name)
        target_col.addWidget(self.target_field_combo)
        fields_row.addLayout(target_col, 1)
        root.addLayout(fields_row)

        config_row = QHBoxLayout()
        config_row.setContentsMargins(0, 0, 0, 0)
        config_row.setSpacing(10)

        mode_col = QVBoxLayout()
        mode_col.setContentsMargins(0, 0, 0, 0)
        mode_col.setSpacing(4)
        mode_col.addWidget(QLabel("Modo da interacao", self))
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItem("Filtrar", "filter")
        self.mode_combo.addItem("Nenhum", "none")
        mode_col.addWidget(self.mode_combo)
        config_row.addLayout(mode_col, 1)

        direction_col = QVBoxLayout()
        direction_col.setContentsMargins(0, 0, 0, 0)
        direction_col.setSpacing(4)
        direction_col.addWidget(QLabel("Direcao", self))
        self.direction_combo = QComboBox(self)
        self.direction_combo.addItem("Ambos", "both")
        self.direction_combo.addItem("Origem -> Destino", "origem_para_destino")
        self.direction_combo.addItem("Destino -> Origem", "destino_para_origem")
        direction_col.addWidget(self.direction_combo)
        config_row.addLayout(direction_col, 1)

        active_col = QVBoxLayout()
        active_col.setContentsMargins(0, 0, 0, 0)
        active_col.setSpacing(4)
        active_col.addWidget(QLabel("Ativo", self))
        self.active_check = QCheckBox("Relacao ativa", self)
        self.active_check.setChecked(True)
        active_col.addWidget(self.active_check)
        config_row.addLayout(active_col, 1)

        root.addLayout(config_row)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(8)
        if self._existing_relation is not None:
            remove_btn = QPushButton("Remover relacao", self)
            remove_btn.setObjectName("DangerActionButton")
            remove_btn.clicked.connect(self._handle_remove)
            actions.addWidget(remove_btn, 0)
        actions.addStretch(1)

        cancel_btn = QPushButton("Cancelar", self)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn, 0)

        save_btn = QPushButton("Salvar", self)
        save_btn.setObjectName("PrimaryActionButton")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._handle_accept)
        actions.addWidget(save_btn, 0)

        root.addLayout(actions)

    def _handle_accept(self):
        relation = self.selected_relation()
        if relation is None:
            slim_message(
                self,
                "Relacao",
                "Selecione campo origem e campo destino.",
                accept_label="OK",
            )
            return
        self._remove_requested = False
        self.accept()

    def _handle_remove(self):
        self._remove_requested = True
        self.accept()

    def _apply_initial_selection(self):
        if self._existing_relation is not None:
            source_index = self.source_field_combo.findText(self._existing_relation.source_field, Qt.MatchFixedString)
            target_index = self.target_field_combo.findText(self._existing_relation.target_field, Qt.MatchFixedString)
            if source_index >= 0:
                self.source_field_combo.setCurrentIndex(source_index)
            if target_index >= 0:
                self.target_field_combo.setCurrentIndex(target_index)
            mode_index = self.mode_combo.findData(str(self._existing_relation.interaction_mode or "filter"))
            if mode_index < 0:
                mode_index = self.mode_combo.findData("filter")
            self.mode_combo.setCurrentIndex(max(0, mode_index))
            direction_index = self.direction_combo.findData(str(self._existing_relation.direction or "both"))
            if direction_index < 0:
                direction_index = self.direction_combo.findData("both")
            self.direction_combo.setCurrentIndex(max(0, direction_index))
            self.active_check.setChecked(bool(self._existing_relation.active))
            return
        if self._suggestions:
            best = self._suggestions[0]
            source_index = self.source_field_combo.findText(best[1], Qt.MatchFixedString)
            target_index = self.target_field_combo.findText(best[2], Qt.MatchFixedString)
            if source_index >= 0:
                self.source_field_combo.setCurrentIndex(source_index)
            if target_index >= 0:
                self.target_field_combo.setCurrentIndex(target_index)
        default_mode_index = self.mode_combo.findData("filter")
        self.mode_combo.setCurrentIndex(max(0, default_mode_index))
        default_direction_index = self.direction_combo.findData("both")
        self.direction_combo.setCurrentIndex(max(0, default_direction_index))
        self.active_check.setChecked(True)

    def _collect_fields(self, item: DashboardChartItem) -> List[_FieldOption]:
        seen = set()
        results: List[_FieldOption] = []

        def _append(name: str, type_name: str = ""):
            text = str(name or "").strip()
            if not text:
                return
            key = text.lower()
            if key in seen:
                return
            seen.add(key)
            results.append(_FieldOption(name=text, type_name=str(type_name or "").strip()))

        source_id = str(item.binding.source_id or "").strip()
        if source_id:
            try:
                layer = QgsProject.instance().mapLayer(source_id)
            except Exception:
                layer = None
            if isinstance(layer, QgsVectorLayer):
                try:
                    for field in layer.fields():
                        _append(field.name(), field.typeName())
                except Exception:
                    pass

        _append(item.binding.dimension_field)
        _append(item.binding.semantic_field_key)
        for alias in list(item.binding.semantic_field_aliases or []):
            _append(alias)

        source_meta = dict(item.source_meta or {})
        metadata = dict(source_meta.get("metadata") or {})
        config = dict(source_meta.get("config") or {})
        for key in ("row_field", "column_field", "row_label", "column_label", "group_field"):
            _append(config.get(key))
        for key in ("row_fields", "column_fields"):
            for value in _text_values(config.get(key)):
                _append(value)
            for value in _text_values(metadata.get(key)):
                _append(value)
        _append(item.payload.category_field)

        if not results:
            fallback = _first_value([item.payload.category_field, item.binding.dimension_field, "categoria"])
            _append(fallback)
        return results

    def _build_suggestions(self) -> List[Tuple[int, str, str, List[str]]]:
        if not self._source_fields or not self._target_fields:
            return []

        source_dimension = str(self._source_item.binding.dimension_field or "").strip().lower()
        target_dimension = str(self._target_item.binding.dimension_field or "").strip().lower()
        scored: List[Tuple[int, str, str, List[str]]] = []

        for source_field in self._source_fields:
            for target_field in self._target_fields:
                score, reasons = self._score_pair(
                    source_field,
                    target_field,
                    source_dimension=source_dimension,
                    target_dimension=target_dimension,
                )
                if score <= 0:
                    continue
                scored.append((score, source_field.name, target_field.name, reasons))

        scored.sort(key=lambda item: (-item[0], item[1].lower(), item[2].lower()))
        return scored[:24]

    def _score_pair(
        self,
        source_field: _FieldOption,
        target_field: _FieldOption,
        *,
        source_dimension: str,
        target_dimension: str,
    ) -> Tuple[int, List[str]]:
        reasons: List[str] = []
        score = 0

        source_name = source_field.normalized_name()
        target_name = target_field.normalized_name()
        if source_name and target_name and source_name == target_name:
            score += 100
            reasons.append("nome igual")
        else:
            ratio = SequenceMatcher(a=source_name, b=target_name).ratio() if source_name and target_name else 0.0
            if ratio >= 0.9:
                score += 60
                reasons.append("nome muito parecido")
            elif ratio >= 0.75:
                score += 38
                reasons.append("nome parecido")
            elif source_name and target_name and (source_name in target_name or target_name in source_name):
                score += 30
                reasons.append("nome relacionado")

        source_group = source_field.group()
        target_group = target_field.group()
        if source_group == target_group and source_group != "unknown":
            score += 22
            reasons.append("tipo compativel")
        elif source_group == "unknown" or target_group == "unknown":
            score += 8
            reasons.append("tipo indefinido")

        if source_field.name.lower() == source_dimension:
            score += 28
            reasons.append("dimensao origem")
        if target_field.name.lower() == target_dimension:
            score += 28
            reasons.append("dimensao destino")

        return score, reasons
