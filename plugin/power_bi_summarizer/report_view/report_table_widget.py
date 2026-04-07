from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
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

    def load_pivot_result(self, result: PivotResult):
        self._pivot_result = result
        self._row_keys = list(result.row_headers or [])
        self._column_keys = list(result.column_headers or [])
        self.clear()

        row_count = len(self._row_keys) + (1 if self._show_totals and result.row_totals else 0)
        column_count = len(self._column_keys) + (1 if self._show_totals and result.column_totals else 0)
        self.setRowCount(row_count)
        self.setColumnCount(column_count)

        horizontal_labels = [PivotFormatter.format_header_tuple(column_key) for column_key in self._column_keys]
        if self._show_totals and result.column_totals:
            horizontal_labels.append("Total")
        vertical_labels = [PivotFormatter.format_header_tuple(row_key) for row_key in self._row_keys]
        if self._show_totals and result.row_totals:
            vertical_labels.append("Total")
        self.setHorizontalHeaderLabels(horizontal_labels)
        self.setVerticalHeaderLabels(vertical_labels)

        aggregation = str((result.metadata or {}).get("aggregation") or "count")
        for row_index, row_key in enumerate(self._row_keys):
            matrix_row = result.matrix[row_index] if row_index < len(result.matrix) else []
            for column_index, cell in enumerate(matrix_row):
                item = QTableWidgetItem(cell.display_value or PivotFormatter.format_value(cell.raw_value, aggregation))
                item.setTextAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                    if isinstance(cell.raw_value, (int, float))
                    else Qt.AlignLeft | Qt.AlignVCenter
                )
                self.setItem(row_index, column_index, item)
            if self._show_totals and result.row_totals:
                total_value = result.row_totals.get(row_key)
                total_item = QTableWidgetItem(PivotFormatter.format_value(total_value, aggregation))
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(row_index, len(self._column_keys), total_item)

        if self._show_totals and result.column_totals:
            total_row = len(self._row_keys)
            for column_index, column_key in enumerate(self._column_keys):
                total_value = result.column_totals.get(column_key)
                total_item = QTableWidgetItem(PivotFormatter.format_value(total_value, aggregation))
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(total_row, column_index, total_item)
            if result.row_totals:
                grand_item = QTableWidgetItem(PivotFormatter.format_value(result.grand_total, aggregation))
                grand_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(total_row, len(self._column_keys), grand_item)

        self.resizeColumnsToContents()

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
