from __future__ import annotations

from ..result_models import QueryResult
from .report_export import build_result_export_bundle as _build_result_export_bundle
from .report_models import ReportExportBundle, ReportPreviewModel
from .report_preview import build_result_preview_model as _build_result_preview_model
from .report_templates import build_reports_stylesheet


def build_result_preview_model(result: QueryResult) -> ReportPreviewModel:
    return _build_result_preview_model(result)


def build_result_export_bundle(result: QueryResult) -> ReportExportBundle:
    return _build_result_export_bundle(result)


__all__ = [
    "build_reports_stylesheet",
    "build_result_export_bundle",
    "build_result_preview_model",
]
