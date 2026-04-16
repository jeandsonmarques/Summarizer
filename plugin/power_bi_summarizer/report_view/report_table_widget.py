from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem

from .pivot.pivot_formatters import PivotFormatter
from .pivot.pivot_models import PivotResult


class ReportPivotTableWidget(QTableWidget):
    pivotCellClicked = pyqtSignal(object)
    pivotRowHeaderClicked = pyqtSignal(object)
    pivotColumnHeaderClicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pivot_result = None
        self._row_keys = []
        self._column_keys = []
        self._show_totals = True
        self.cellClicked.connect(self._handle_cell_clicked)
        self.verticalHeader().sectionClicked.connect(self._handle_row_header_clicked)
        self.horizontalHeader().sectionClicked.connect(self._handle_column_header_clicked)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setWordWrap(False)
        self.setStyleSheet(
            """
            QTableWidget {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                gridline-color: #E5E7EB;
                selection-background-color: rgba(79, 70, 229, 0.12);
                selection-color: #111827;
            }
            QTableWidget::item {
                padding: 6px 10px;
            }
            QHeaderView::section {
                background: #F8FAFC;
                color: #475569;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 6px 8px;
                font-weight: 600;
            }
            QTableCornerButton::section {
                background: #F8FAFC;
                border: none;
                border-bottom: 1px solid #E5E7EB;
            }
            """
        )

    def load_pivot_result(self, result: PivotResult):
        self._pivot_result = result
        self._row_keys = list(result.row_headers or [])
        self._column_keys = list(result.column_headers or [])
        self.clear()

        row_count = len(self._row_keys) + (1 if self._show_totals and result.row_totals else 0)
        column_count = 1 + len(self._column_keys) + (1 if self._show_totals and result.column_totals else 0)
        self.setRowCount(row_count)
        self.setColumnCount(column_count)

        row_fields = list((result.metadata or {}).get("row_fields") or [])
        row_header_label = "Linha" if not row_fields else " / ".join(str(field) for field in row_fields)
        horizontal_labels = [row_header_label]
        horizontal_labels.extend(PivotFormatter.format_header_tuple(column_key) for column_key in self._column_keys)
        if self._show_totals and result.column_totals:
            horizontal_labels.append("Total")
        self.setHorizontalHeaderLabels(horizontal_labels)

        aggregation = str((result.metadata or {}).get("aggregation") or "count")
        base_font = QFont(self.font())
        base_font.setPointSize(max(9, base_font.pointSize()))
        base_font.setWeight(QFont.Medium)
        row_font = QFont(base_font)
        row_font.setBold(True)

        for row_index, row_key in enumerate(self._row_keys):
            row_label = PivotFormatter.format_header_tuple(row_key)
            row_item = QTableWidgetItem(row_label)
            row_item.setFont(row_font if row_index == 0 or row_label.lower() == "total" else base_font)
            row_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_item.setBackground(QColor("#F8FAFC" if row_index % 2 else "#FFFFFF"))
            row_item.setForeground(QColor("#1F2937"))
            self.setItem(row_index, 0, row_item)
            matrix_row = result.matrix[row_index] if row_index < len(result.matrix) else []
            for column_index, cell in enumerate(matrix_row):
                cell_text = cell.display_value or PivotFormatter.format_value(cell.raw_value, aggregation)
                item = QTableWidgetItem(cell_text)
                display_column = column_index + 1
                item.setFont(base_font)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setBackground(QColor("#FAFAFC" if row_index % 2 else "#FFFFFF"))
                item.setForeground(QColor("#111827"))
                self.setItem(row_index, display_column, item)
            if self._show_totals and result.row_totals:
                total_value = result.row_totals.get(row_key)
                total_item = QTableWidgetItem(PivotFormatter.format_value(total_value, aggregation))
                total_item.setFont(row_font)
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                total_item.setBackground(QColor("#EEF2FF"))
                total_item.setForeground(QColor("#111827"))
                self.setItem(row_index, len(self._column_keys) + 1, total_item)

        if self._show_totals and result.column_totals:
            total_row = len(self._row_keys)
            total_label = QTableWidgetItem("Total")
            total_label.setFont(row_font)
            total_label.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            total_label.setBackground(QColor("#EDE9FE"))
            total_label.setForeground(QColor("#111827"))
            self.setItem(total_row, 0, total_label)
            for column_index, column_key in enumerate(self._column_keys):
                total_value = result.column_totals.get(column_key)
                total_item = QTableWidgetItem(PivotFormatter.format_value(total_value, aggregation))
                total_item.setFont(row_font)
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                total_item.setBackground(QColor("#EDE9FE" if column_index % 2 else "#F5F3FF"))
                total_item.setForeground(QColor("#111827"))
                self.setItem(total_row, column_index + 1, total_item)
            if result.row_totals:
                grand_item = QTableWidgetItem(PivotFormatter.format_value(result.grand_total, aggregation))
                grand_item.setFont(row_font)
                grand_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                grand_item.setBackground(QColor("#DDD6FE"))
                grand_item.setForeground(QColor("#111827"))
                self.setItem(total_row, len(self._column_keys) + 1, grand_item)

        self.resizeColumnsToContents()
        self.setColumnWidth(0, max(self.columnWidth(0), 140))
        self.verticalHeader().setDefaultSectionSize(28)
        self.horizontalHeader().setMinimumHeight(34)

    def clear_pivot(self):
        self._pivot_result = None
        self._row_keys = []
        self._column_keys = []
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)

    def _handle_cell_clicked(self, row, col):
        if self._pivot_result is None:
            return
        if row >= len(self._row_keys) or col >= len(self._column_keys):
            return
        if row >= len(self._pivot_result.matrix) or col >= len(self._pivot_result.matrix[row]):
            return
        self.pivotCellClicked.emit(self._pivot_result.matrix[row][col])

    def _handle_row_header_clicked(self, row):
        if row < len(self._row_keys):
            self.pivotRowHeaderClicked.emit(self._row_keys[row])

    def _handle_column_header_clicked(self, col):
        if col < len(self._column_keys):
            self.pivotColumnHeaderClicked.emit(self._column_keys[col])
