# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Mapping, Optional

try:
    from qgis.PyQt.QtCore import QBuffer, QRectF
    from qgis.PyQt.QtGui import QImage, QPainter

    from ..report_view.visuals import BarChartRenderer, VisualDefinition, VisualTheme
except Exception:  # pragma: no cover - used by unit tests outside QGIS
    QBuffer = None
    QRectF = None
    QImage = None
    QPainter = None
    BarChartRenderer = None
    VisualDefinition = None
    VisualTheme = None

try:
    from ..result_style import apply_result_style
except Exception:  # pragma: no cover - fallback for non-QGIS test environments

    def apply_result_style(html: str) -> str:
        return html


from .summary_results_view import escape_html


def chart_preview_style_block() -> str:
    return """
        <style>
            .preview-card {
                background: #f5f6fb;
                border: 1px solid #e3e7f1;
                border-radius: 0px;
                padding: 18px 22px;
                display: flex;
                flex-direction: column;
                gap: 18px;
            }
            .preview-card.empty {
                gap: 24px;
            }
            .preview-header h2 {
                margin: 0 0 12px 0;
                font-size: 18px;
                color: #1d2a4b;
            }
            .meta-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 10px;
            }
            .meta-item {
                background: #ffffff;
                border-radius: 0px;
                border: 1px solid #e6eaf4;
                padding: 10px 12px;
                display: flex;
                flex-direction: column;
                gap: 2px;
            }
            .meta-label {
                font-size: 10pt;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .meta-value {
                font-size: 12pt;
                font-weight: 600;
                color: #1d2a4b;
            }
            .groups-wrapper {
                display: flex;
                justify-content: center;
                padding: 4px;
            }
            .preview-chart {
                max-width: 100%;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 0px;
                padding: 6px;
                border: 1px solid #e6eaf4;
            }
            .preview-footer {
                margin-top: 8px;
                font-size: 10pt;
                color: #7b8794;
                text-align: right;
            }
            .empty-body {
                background: #ffffff;
                border-radius: 0px;
                border: 1px dashed #d2d8e6;
                padding: 18px;
                text-align: center;
                color: #7b8794;
                font-size: 11pt;
            }
        </style>
        """


def _chart_heading_html(field_name: Any, layer_name: Any, *, accent: bool = False) -> str:
    title = "Distribuição" if accent else "Distribuicao"
    return (
        f'<h2>{title} percentual dos grupos - "{escape_html(field_name)}" '
        f'em {escape_html(layer_name)}</h2>'
    )


def _empty_groups_html() -> str:
    return '<div class="empty-body">Nenhum agrupamento disponível para exibir.</div>'


def summary_data_from_pivot_result(summary_data: Mapping[str, Any], pivot_result) -> dict[str, Any]:
    metadata = dict(getattr(pivot_result, "metadata", {}) or {})
    grouped_data = {}
    totals_source = pivot_result.row_totals or pivot_result.column_totals or {}
    grand_total = float(pivot_result.grand_total or 0.0)
    for key, value in totals_source.items():
        if value is None:
            continue
        label = " / ".join(str(item) for item in (key or ()) if item not in (None, ""))
        label = label or "Total"
        numeric_value = float(value)
        grouped_data[label] = {
            "sum": numeric_value,
            "percentage": (numeric_value / grand_total * 100) if grand_total else 0.0,
        }
    preview_data = dict(summary_data or {})
    preview_data["grouped_data"] = grouped_data
    basic_stats = dict(preview_data.get("basic_stats") or {})
    basic_stats["total"] = grand_total
    preview_data["basic_stats"] = basic_stats
    merged_metadata = dict(preview_data.get("metadata") or {})
    merged_metadata.update(
        {
            "layer_name": metadata.get("layer_name", merged_metadata.get("layer_name", "-")),
            "field_name": metadata.get("value_field", merged_metadata.get("field_name", "-")),
        }
    )
    preview_data["metadata"] = merged_metadata
    return preview_data


def _human_timestamp(timestamp_str: Optional[str]) -> str:
    try:
        return datetime.fromisoformat(timestamp_str).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return datetime.now().strftime("%d/%m/%Y %H:%M")


def _render_chart_image_html(labels: list[str], values: list[float]) -> str:
    if not values or max(values) <= 0:
        return ""
    if any(
        dependency is None
        for dependency in (
            QBuffer,
            QRectF,
            QImage,
            QPainter,
            BarChartRenderer,
            VisualDefinition,
            VisualTheme,
        )
    ):
        return ""

    height_px = max(320, int(len(values) * 38 + 120))
    width_px = 780
    image = QImage(width_px, height_px, QImage.Format_ARGB32)
    theme = VisualTheme()
    image.fill(theme.bg)
    painter = QPainter(image)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    definition = VisualDefinition(
        tipo="barra",
        categorias=labels,
        valores=values,
        titulo="% do total",
    )
    BarChartRenderer().render(painter, QRectF(0, 0, width_px, height_px), definition, theme)
    painter.end()
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    image.save(buffer, "PNG")
    encoded = base64.b64encode(bytes(buffer.data())).decode("utf-8")
    return (
        f'<img class="preview-chart" src="data:image/png;base64,{encoded}" '
        'alt="Distribuicao percentual dos grupos">'
    )


def build_chart_preview_html(summary_data: Mapping[str, Any]) -> str:
    grouped = summary_data.get("grouped_data") or {}
    layer_name = summary_data.get("metadata", {}).get("layer_name", "-")
    field_name = summary_data.get("metadata", {}).get("field_name", "-")
    stats = summary_data.get("basic_stats", {})
    human_ts = _human_timestamp(summary_data.get("metadata", {}).get("timestamp"))
    total_label = f"{stats.get('total', 0):,.2f}"

    if not grouped:
        empty_html = f"""
            <div class="preview-card empty">
                <div class="preview-header">
                    {_chart_heading_html(field_name, layer_name, accent=True)}
                    <div class="meta-grid">
                        <div class="meta-item">
                            <span class="meta-label">Camada</span>
                            <span class="meta-value">{escape_html(layer_name)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Campo numérico</span>
                            <span class="meta-value">{escape_html(field_name)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Total geral</span>
                            <span class="meta-value">{total_label}</span>
                        </div>
                    </div>
                </div>
                <div class="empty-body">
                    Nenhum agrupamento disponível para exibir.
                </div>
                <div class="preview-footer">Gerado em: {human_ts}</div>
            </div>
            """
        return apply_result_style(empty_html) + chart_preview_style_block()

    sorted_groups = sorted(
        grouped.items(), key=lambda item: item[1].get("percentage", 0), reverse=True
    )
    labels = ["Sem valor" if key in (None, "") else str(key) for key, _ in sorted_groups]
    values = [max(data.get("percentage", 0.0), 0.0) for _, data in sorted_groups]
    chart_html = _render_chart_image_html(labels, values)

    html = f"""
        <div class="preview-card">
            <div class="preview-header">
                {_chart_heading_html(field_name, layer_name)}
                <div class="meta-grid">
                    <div class="meta-item">
                        <span class="meta-label">Camada</span>
                        <span class="meta-value">{escape_html(layer_name)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Campo numerico</span>
                        <span class="meta-value">{escape_html(field_name)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Total geral</span>
                        <span class="meta-value">{total_label}</span>
                    </div>
                </div>
            </div>
            <div class="groups-wrapper">
                {chart_html or _empty_groups_html()}
            </div>
            <div class="preview-footer">Gerado em: {human_ts}</div>
        </div>
        """
    return apply_result_style(html) + chart_preview_style_block()


def update_charts_preview(
    chart_preview_text, summary_data: Mapping[str, Any], pivot_widget=None
) -> None:
    if chart_preview_text is None:
        return
    preview_data = summary_data
    if pivot_widget is not None and hasattr(pivot_widget, "get_current_pivot_result"):
        try:
            pivot_result = pivot_widget.get_current_pivot_result()
        except Exception:
            pivot_result = None
        if pivot_result is not None:
            preview_data = summary_data_from_pivot_result(summary_data, pivot_result)
    chart_preview_text.setHtml(build_chart_preview_html(preview_data or {}))
