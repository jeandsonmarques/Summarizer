import math
from typing import Optional

from qgis.PyQt.QtCore import QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from qgis.PyQt.QtWidgets import QWidget

from .result_models import ChartPayload, QueryResult


class ChartFactory:
    def build_payload(self, result: QueryResult) -> Optional[ChartPayload]:
        if not result.ok or not result.rows:
            return None

        rows = result.rows[:12]
        return ChartPayload(
            chart_type=self._choose_chart_type(result),
            title=result.plan.chart.title if result.plan is not None else "Relatório",
            categories=[row.category for row in rows],
            values=[row.value for row in rows],
            value_label=result.value_label,
            truncated=len(result.rows) > len(rows),
        )

    def _choose_chart_type(self, result: QueryResult) -> str:
        plan = result.plan
        if plan is not None and plan.chart.type not in {"", "auto"}:
            return plan.chart.type
        if plan is not None and plan.group_field_kind in {"date", "datetime"} and len(result.rows) > 1:
            return "line"
        if 1 < len(result.rows) <= 5 and plan is not None and plan.metric.operation in {"count", "sum", "length", "area"}:
            return "pie"
        return "bar"


class ReportChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._payload: Optional[ChartPayload] = None
        self._empty_text = ""
        self.setMinimumHeight(280)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def set_payload(self, payload: Optional[ChartPayload], empty_text: Optional[str] = None):
        self._payload = payload
        if empty_text is not None:
            self._empty_text = empty_text
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)

        if self._payload is None or not self._payload.categories:
            if self._empty_text:
                painter.setPen(QPen(QColor("#6B7280")))
                painter.drawText(rect, Qt.AlignCenter, self._empty_text)
            return

        self._draw_title(painter, rect, self._payload.title)
        chart_rect = rect.adjusted(0, 36, 0, 0)

        if self._payload.chart_type == "pie":
            self._draw_pie_chart(painter, chart_rect, self._payload)
        elif self._payload.chart_type == "line":
            self._draw_line_chart(painter, chart_rect, self._payload)
        elif self._payload.chart_type == "histogram":
            self._draw_histogram(painter, chart_rect, self._payload)
        else:
            self._draw_bar_chart(painter, chart_rect, self._payload)

    def _draw_title(self, painter: QPainter, rect: QRectF, title: str):
        title_font = QFont(self.font())
        title_font.setPointSize(max(10, title_font.pointSize() + 1))
        title_font.setBold(True)
        painter.save()
        painter.setFont(title_font)
        painter.setPen(QPen(QColor("#1F2937")))
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, title)
        painter.restore()

    def _draw_bar_chart(self, painter: QPainter, rect: QRectF, payload: ChartPayload):
        max_value = max(payload.values) if payload.values else 1.0
        max_value = max(max_value, 1.0)
        label_width = min(220.0, rect.width() * 0.34)
        value_width = 90.0
        chart_rect = rect.adjusted(label_width + 12, 8, -value_width, -8)
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        count = max(1, len(payload.categories))
        row_height = chart_rect.height() / count
        bar_height = max(12.0, row_height * 0.5)
        metrics = QFontMetrics(self.font())

        painter.save()
        for index, category in enumerate(payload.categories):
            y = chart_rect.top() + index * row_height + (row_height - bar_height) / 2
            bar_ratio = payload.values[index] / max_value if max_value else 0.0
            width = chart_rect.width() * bar_ratio

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2B7DE9"))
            painter.drawRoundedRect(QRectF(chart_rect.left(), y, width, bar_height), 6, 6)

            painter.setPen(QPen(QColor("#4B5563")))
            label_rect = QRectF(rect.left(), y - 2, label_width, bar_height + 4)
            painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, metrics.elidedText(category, Qt.ElideRight, int(label_width) - 8))

            painter.setPen(QPen(QColor("#1F2937")))
            value_rect = QRectF(chart_rect.right() + 10, y - 2, value_width - 10, bar_height + 4)
            painter.drawText(value_rect, Qt.AlignVCenter | Qt.AlignRight, self._format_value(payload.values[index]))
        painter.restore()

    def _draw_pie_chart(self, painter: QPainter, rect: QRectF, payload: ChartPayload):
        total = sum(payload.values)
        if total <= 0:
            self._draw_bar_chart(painter, rect, payload)
            return

        diameter = min(rect.width() * 0.46, rect.height() * 0.75)
        pie_rect = QRectF(rect.left(), rect.top() + 10, diameter, diameter)
        legend_rect = QRectF(pie_rect.right() + 24, rect.top(), rect.right() - pie_rect.right() - 24, rect.height())
        colors = [
            QColor("#2B7DE9"),
            QColor("#F2C811"),
            QColor("#2FB26A"),
            QColor("#F2994A"),
            QColor("#6D28D9"),
        ]

        start_angle = 0.0
        painter.save()
        for index, value in enumerate(payload.values):
            span = (value / total) * 360.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(colors[index % len(colors)])
            painter.drawPie(pie_rect, int(start_angle * 16), int(span * 16))
            start_angle += span

        metrics = QFontMetrics(self.font())
        line_height = 24
        for index, category in enumerate(payload.categories):
            color = colors[index % len(colors)]
            y = legend_rect.top() + index * line_height
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(legend_rect.left(), y + 4, 12, 12), 3, 3)

            percent = (payload.values[index] / total) * 100.0 if total else 0.0
            text = f"{category} ({percent:.1f}%)"
            painter.setPen(QPen(QColor("#374151")))
            text_rect = QRectF(legend_rect.left() + 20, y, legend_rect.width() - 20, line_height)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, metrics.elidedText(text, Qt.ElideRight, int(text_rect.width())))
        painter.restore()

    def _draw_line_chart(self, painter: QPainter, rect: QRectF, payload: ChartPayload):
        if len(payload.values) < 2:
            self._draw_bar_chart(painter, rect, payload)
            return

        left_margin = 24
        right_margin = 16
        bottom_margin = 36
        top_margin = 12
        chart_rect = rect.adjusted(left_margin, top_margin, -right_margin, -bottom_margin)
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        max_value = max(payload.values) if payload.values else 1.0
        max_value = max(max_value, 1.0)
        steps = max(1, len(payload.values) - 1)

        painter.save()
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        for grid_index in range(5):
            y = chart_rect.bottom() - (chart_rect.height() * grid_index / 4.0)
            painter.drawLine(chart_rect.left(), y, chart_rect.right(), y)

        points = []
        for index, value in enumerate(payload.values):
            x = chart_rect.left() + (chart_rect.width() * index / steps)
            y = chart_rect.bottom() - (chart_rect.height() * (value / max_value))
            points.append(QPointF(x, y))

        painter.setPen(QPen(QColor("#2B7DE9"), 2))
        for index in range(1, len(points)):
            painter.drawLine(points[index - 1], points[index])

        painter.setBrush(QColor("#2B7DE9"))
        painter.setPen(Qt.NoPen)
        for point in points:
            painter.drawEllipse(point, 4, 4)

        painter.setPen(QPen(QColor("#4B5563")))
        metrics = QFontMetrics(self.font())
        step = chart_rect.width() / max(1, len(payload.categories))
        for index, category in enumerate(payload.categories):
            x = chart_rect.left() + step * index
            label_rect = QRectF(x - step / 2, chart_rect.bottom() + 8, step, 24)
            painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, metrics.elidedText(category, Qt.ElideRight, int(step) - 4))
        painter.restore()

    def _draw_histogram(self, painter: QPainter, rect: QRectF, payload: ChartPayload):
        self._draw_bar_chart(painter, rect, payload)

    def _format_value(self, value: float) -> str:
        if math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-6):
            return f"{int(round(value)):,}".replace(",", ".")
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
