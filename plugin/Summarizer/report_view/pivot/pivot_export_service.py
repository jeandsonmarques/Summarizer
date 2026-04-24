from __future__ import annotations

import csv
from typing import List

from .pivot_formatters import PivotFormatter
from .pivot_models import PivotResult


class PivotExportService:
    def export_to_excel(
        self,
        result: PivotResult,
        file_path: str,
        include_totals: bool = True,
        include_percentages: bool = True,
    ):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Pivot"
        rows = self._result_to_2d_array(
            result,
            include_totals=include_totals,
            include_percentages=include_percentages,
        )
        for row_index, row_values in enumerate(rows, start=1):
            for column_index, value in enumerate(row_values, start=1):
                sheet.cell(row=row_index, column=column_index, value=value)
        workbook.save(file_path)

    def export_to_csv(self, result: PivotResult, file_path: str):
        with open(file_path, "w", encoding="utf-8-sig", newline="") as handler:
            writer = csv.writer(handler)
            writer.writerows(self._result_to_2d_array(result))

    def _result_to_2d_array(
        self,
        result: PivotResult,
        include_totals: bool = True,
        include_percentages: bool = True,
    ):
        metadata = dict(result.metadata or {})
        row_fields = list(metadata.get("row_fields") or [])
        row_depth = max(len(row_fields), max((len(key) for key in result.row_headers), default=0), 1)
        column_headers = list(result.column_headers or [()])
        aggregation = str(metadata.get("aggregation") or "count")

        header_row: List[str] = []
        for index in range(row_depth):
            if index < len(row_fields):
                header_row.append(str(row_fields[index]))
            elif row_depth == 1:
                header_row.append("Linha")
            else:
                header_row.append(f"Linha {index + 1}")
        for column_key in column_headers:
            header_row.append(PivotFormatter.format_header_tuple(column_key))
        if include_totals and result.row_totals:
            header_row.append("Total")

        rows = [header_row]
        for row_index, row_key in enumerate(result.row_headers or [()]):
            line: List[str] = []
            row_values = list(row_key)
            while len(row_values) < row_depth:
                row_values.append("")
            for value in row_values[:row_depth]:
                line.append("" if value is None else str(value))
            matrix_row = result.matrix[row_index] if row_index < len(result.matrix) else []
            for cell in matrix_row:
                text = cell.display_value or PivotFormatter.format_value(cell.raw_value, aggregation)
                if include_percentages and cell.percent_of_total is not None:
                    percent = PivotFormatter.format_percent(cell.percent_of_total)
                    if percent:
                        text = f"{text} ({percent})" if text else percent
                line.append(text)
            if include_totals and result.row_totals:
                total_value = result.row_totals.get(row_key)
                line.append(PivotFormatter.format_value(total_value, aggregation))
            rows.append(line)

        if include_totals and result.column_totals:
            total_row = [""] * max(row_depth - 1, 0) + ["Total"]
            for column_key in column_headers:
                total_value = result.column_totals.get(column_key)
                total_row.append(PivotFormatter.format_value(total_value, aggregation))
            if result.row_totals:
                total_row.append(PivotFormatter.format_value(result.grand_total, aggregation))
            rows.append(total_row)

        return rows
