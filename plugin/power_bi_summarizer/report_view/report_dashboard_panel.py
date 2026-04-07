from __future__ import annotations

from qgis.PyQt.QtWidgets import QGridLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from .pivot.pivot_formatters import PivotFormatter
from .pivot.pivot_models import PivotResult


class ReportDashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pivot_result = None
        self._summary_labels = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        cards = QWidget(self)
        cards_layout = QGridLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        for column_index, key in enumerate(("total", "groups", "largest_group", "aggregation")):
            label = QLabel("-", cards)
            cards_layout.addWidget(label, 0, column_index)
            self._summary_labels[key] = label
        layout.addWidget(cards)

        self.breakdown_text = QTextEdit(self)
        self.breakdown_text.setReadOnly(True)
        layout.addWidget(self.breakdown_text, 1)

        self.highlights_text = QTextEdit(self)
        self.highlights_text.setReadOnly(True)
        layout.addWidget(self.highlights_text, 1)

    def set_pivot_result(self, result: PivotResult):
        self._pivot_result = result
        self.render_summary_cards()
        self.render_breakdown()
        self.render_highlights()

    def render_summary_cards(self):
        result = self._pivot_result
        if result is None:
            for label in self._summary_labels.values():
                label.setText("-")
            return
        groups = len(result.row_headers) * max(len(result.column_headers), 1)
        largest_key = None
        largest_value = None
        for row_key, value in (result.row_totals or {}).items():
            if value is None:
                continue
            if largest_value is None or value > largest_value:
                largest_value = value
                largest_key = row_key
        aggregation = str(result.metadata.get("aggregation") or "count")
        self._summary_labels["total"].setText(
            f"Total: {PivotFormatter.format_value(result.grand_total, aggregation)}"
        )
        self._summary_labels["groups"].setText(f"Grupos: {groups}")
        self._summary_labels["largest_group"].setText(
            "Maior grupo: "
            + (
                f"{PivotFormatter.format_header_tuple(largest_key)} ({PivotFormatter.format_value(largest_value, aggregation)})"
                if largest_key is not None
                else "-"
            )
        )
        self._summary_labels["aggregation"].setText(f"Agregacao: {aggregation}")

    def render_breakdown(self):
        result = self._pivot_result
        if result is None:
            self.breakdown_text.clear()
            return
        aggregation = str(result.metadata.get("aggregation") or "count")
        lines = []
        for row_key in result.row_headers[:20]:
            total_value = result.row_totals.get(row_key)
            lines.append(
                f"{PivotFormatter.format_header_tuple(row_key)}: {PivotFormatter.format_value(total_value, aggregation)}"
            )
        self.breakdown_text.setPlainText("\n".join(lines))

    def render_highlights(self):
        result = self._pivot_result
        if result is None:
            self.highlights_text.clear()
            return
        warnings = list(result.warnings or [])
        if result.grand_total in (None, 0):
            warnings.append("O resultado nao possui total geral numerico.")
        if not warnings:
            warnings.append("Pivot calculada com sucesso.")
        self.highlights_text.setPlainText("\n".join(warnings))
