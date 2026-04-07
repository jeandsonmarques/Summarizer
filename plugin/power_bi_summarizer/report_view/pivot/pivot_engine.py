from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeatureRequest, QgsProject

from .pivot_formatters import PivotFormatter
from .pivot_models import PivotBucket, PivotCell, PivotFieldSpec, PivotRequest, PivotResult
from .pivot_validators import PivotValidator


class PivotEngine:
    SIMPLE_AGGREGATIONS = {"count", "sum", "average", "min", "max"}
    HEAVY_AGGREGATIONS = {"median", "variance", "stddev", "unique"}

    def __init__(self, iface=None, logger=None):
        self.iface = iface
        self.logger = logger
        self._active_buckets: Dict[Tuple[Tuple[Any, ...], Tuple[Any, ...]], PivotBucket] = {}
        self._active_aggregation: str = "count"

    def execute(self, request: PivotRequest) -> PivotResult:
        layer = self._resolve_layer(request.layer_id)
        PivotValidator.validate_request(request, layer)

        feature_request = self._build_feature_request(layer, request)
        buckets: Dict[Tuple[Tuple[Any, ...], Tuple[Any, ...]], PivotBucket] = {}
        feature_count = 0

        for feature in self._iter_features(layer, feature_request, request):
            row_key = self._extract_key(feature, request.row_fields)
            col_key = self._extract_key(feature, request.column_fields)
            if not request.include_nulls and (
                any(value is None for value in row_key) or any(value is None for value in col_key)
            ):
                continue

            value = self._extract_value(feature, request.value_field)
            bucket_key = (row_key or (), col_key or ())
            bucket = buckets.setdefault(bucket_key, self._init_bucket())
            self._accumulate_bucket(bucket, value, int(feature.id()), request.aggregation, request.include_nulls)
            feature_count += 1

        row_headers, column_headers = self._build_headers(buckets)
        matrix = self._build_matrix(buckets, row_headers, column_headers, request.aggregation)
        self._active_buckets = buckets
        self._active_aggregation = request.aggregation
        result = PivotResult(
            row_headers=row_headers,
            column_headers=column_headers,
            matrix=matrix,
            metadata=self._build_result_metadata(request, layer, feature_count),
        )
        if request.include_totals:
            self._compute_totals(result.matrix, result.row_headers, result.column_headers)
            result.row_totals = dict(getattr(self, "_last_row_totals", {}))
            result.column_totals = dict(getattr(self, "_last_column_totals", {}))
            result.grand_total = getattr(self, "_last_grand_total", None)
        if request.include_percentages:
            self._apply_percentages(result)
        return result

    def _resolve_layer(self, layer_id):
        if not layer_id:
            return None
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if layer is not None:
            return layer
        matches = project.mapLayersByName(layer_id)
        return matches[0] if matches else None

    def _build_feature_request(self, layer, request: PivotRequest):
        feature_request = QgsFeatureRequest()
        if request.filter_expression:
            feature_request.setFilterExpression(request.filter_expression)
        needed_attributes = self._collect_needed_attributes(request)
        if needed_attributes:
            try:
                feature_request.setSubsetOfAttributes(needed_attributes, layer.fields())
            except Exception:
                pass
        geometry_required = any(spec.source_type == "geometry" for spec in self._iter_specs(request))
        if not geometry_required:
            try:
                feature_request.setFlags(QgsFeatureRequest.NoGeometry)
            except Exception:
                pass
        return feature_request

    def _collect_needed_attributes(self, request: PivotRequest):
        names = []
        for field_spec in self._iter_specs(request):
            if field_spec.source_type != "attribute":
                continue
            if field_spec.field_name not in names:
                names.append(field_spec.field_name)
        return names

    def _iter_features(self, layer, feature_request, request: PivotRequest):
        selected_ids = set()
        if request.only_selected:
            try:
                selected_ids = set(layer.selectedFeatureIds())
            except Exception:
                selected_ids = set()
        for feature in layer.getFeatures(feature_request):
            if selected_ids and feature.id() not in selected_ids:
                continue
            yield feature

    def _extract_key(self, feature, field_specs: Sequence[PivotFieldSpec]):
        if not field_specs:
            return ()
        return tuple(self._normalize_value(self._extract_field_value(feature, field_spec)) for field_spec in field_specs)

    def _extract_value(self, feature, value_field):
        if value_field is None:
            return None
        return self._normalize_value(self._extract_field_value(feature, value_field))

    def _extract_field_value(self, feature, field_spec: PivotFieldSpec):
        if field_spec.source_type == "geometry":
            return self._extract_geometry_value(feature, field_spec.geometry_op)
        return feature[field_spec.field_name]

    def _extract_geometry_value(self, feature, geometry_op):
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            return None
        if geometry_op == "length":
            return geometry.length()
        if geometry_op == "area":
            return geometry.area()
        return None

    def _normalize_value(self, value):
        if value is None:
            return None
        if hasattr(value, "isNull"):
            try:
                if value.isNull():
                    return None
            except Exception:
                pass
        if isinstance(value, QVariant):
            try:
                value = value.value()
            except Exception:
                value = str(value)
        if isinstance(value, str):
            value = value.strip()
            return value or None
        if hasattr(value, "toPyDateTime"):
            try:
                return value.toPyDateTime()
            except Exception:
                return str(value)
        return value

    def _init_bucket(self):
        return PivotBucket()

    def _accumulate_bucket(self, bucket, value, feature_id, aggregation, include_nulls):
        bucket.feature_ids.append(feature_id)
        if aggregation == "count":
            bucket.count += 1
            return

        if value is None:
            if include_nulls and aggregation == "unique":
                bucket.unique_values.add(None)
            return

        if aggregation in {"sum", "average"}:
            numeric_value = float(value)
            bucket.count += 1
            bucket.sum_value += numeric_value
            return

        if aggregation == "min":
            comparable = float(value) if isinstance(value, (int, float)) else value
            bucket.count += 1
            if bucket.min_value is None or comparable < bucket.min_value:
                bucket.min_value = comparable
            return

        if aggregation == "max":
            comparable = float(value) if isinstance(value, (int, float)) else value
            bucket.count += 1
            if bucket.max_value is None or comparable > bucket.max_value:
                bucket.max_value = comparable
            return

        if aggregation in {"median", "variance", "stddev"}:
            numeric_value = float(value)
            bucket.count += 1
            bucket.values.append(numeric_value)
            bucket.sum_value += numeric_value
            return

        if aggregation == "unique":
            bucket.count += 1
            bucket.unique_values.add(value)

    def _finalize_bucket_value(self, bucket, aggregation):
        if aggregation == "count":
            return float(bucket.count)
        if aggregation == "sum":
            return bucket.sum_value
        if aggregation == "average":
            return bucket.sum_value / bucket.count if bucket.count else None
        if aggregation == "min":
            return bucket.min_value
        if aggregation == "max":
            return bucket.max_value
        if aggregation == "median":
            return statistics.median(bucket.values) if bucket.values else None
        if aggregation == "variance":
            return statistics.pvariance(bucket.values) if bucket.values else None
        if aggregation == "stddev":
            return statistics.pstdev(bucket.values) if bucket.values else None
        if aggregation == "unique":
            return float(len(bucket.unique_values))
        return None

    def _build_headers(self, buckets):
        row_headers = sorted({key[0] for key in buckets.keys()} or {()}, key=self._sort_tuple_key)
        column_headers = sorted({key[1] for key in buckets.keys()} or {()}, key=self._sort_tuple_key)
        return row_headers, column_headers

    def _build_matrix(self, buckets, row_headers, column_headers, aggregation):
        matrix: List[List[PivotCell]] = []
        for row_key in row_headers:
            row_cells = []
            for col_key in column_headers:
                bucket = buckets.get((row_key, col_key))
                if bucket is None:
                    row_cells.append(PivotCell())
                    continue
                raw_value = self._finalize_bucket_value(bucket, aggregation)
                row_cells.append(
                    PivotCell(
                        raw_value=raw_value,
                        display_value=PivotFormatter.format_value(raw_value, aggregation),
                        feature_ids=list(bucket.feature_ids),
                    )
                )
            matrix.append(row_cells)
        return matrix

    def _compute_totals(self, matrix, row_headers, column_headers):
        row_totals = {}
        column_totals = {}

        for row_key in row_headers:
            buckets = [
                self._active_buckets[(row_key, col_key)]
                for col_key in column_headers
                if (row_key, col_key) in self._active_buckets
            ]
            row_totals[row_key] = self._combine_total_buckets(buckets, self._active_aggregation)

        for col_key in column_headers:
            buckets = [
                self._active_buckets[(row_key, col_key)]
                for row_key in row_headers
                if (row_key, col_key) in self._active_buckets
            ]
            column_totals[col_key] = self._combine_total_buckets(buckets, self._active_aggregation)

        self._last_row_totals = row_totals
        self._last_column_totals = column_totals
        self._last_grand_total = self._combine_total_buckets(list(self._active_buckets.values()), self._active_aggregation)

    def _apply_percentages(self, result):
        if not result.matrix:
            return
        grand_total = result.grand_total
        for row_index, row_key in enumerate(result.row_headers):
            row_total = result.row_totals.get(row_key)
            for column_index, col_key in enumerate(result.column_headers):
                cell = result.matrix[row_index][column_index]
                column_total = result.column_totals.get(col_key)
                raw_value = cell.raw_value
                if raw_value is None or not isinstance(raw_value, (int, float)):
                    continue
                if isinstance(grand_total, (int, float)) and grand_total:
                    cell.percent_of_total = float(raw_value) / float(grand_total)
                if isinstance(row_total, (int, float)) and row_total:
                    cell.percent_of_row = float(raw_value) / float(row_total)
                if isinstance(column_total, (int, float)) and column_total:
                    cell.percent_of_column = float(raw_value) / float(column_total)

    def _build_result_metadata(self, request, layer, feature_count):
        return {
            "layer_id": layer.id(),
            "layer_name": layer.name(),
            "aggregation": request.aggregation,
            "value_field": request.value_field.display_name if request.value_field is not None else "",
            "row_fields": [field.display_name for field in request.row_fields],
            "column_fields": [field.display_name for field in request.column_fields],
            "feature_count": feature_count,
            "filtered": bool(request.filter_expression),
            "only_selected": bool(request.only_selected),
        }

    def _combine_total_buckets(self, buckets: Sequence[PivotBucket], aggregation: str):
        valid_buckets = [bucket for bucket in buckets if bucket is not None]
        if not valid_buckets:
            return None
        if aggregation == "count":
            return float(sum(bucket.count for bucket in valid_buckets))
        if aggregation == "sum":
            return sum(bucket.sum_value for bucket in valid_buckets)
        if aggregation == "average":
            total_count = sum(bucket.count for bucket in valid_buckets)
            total_sum = sum(bucket.sum_value for bucket in valid_buckets)
            return total_sum / total_count if total_count else None
        if aggregation == "min":
            values = [bucket.min_value for bucket in valid_buckets if bucket.min_value is not None]
            return min(values) if values else None
        if aggregation == "max":
            values = [bucket.max_value for bucket in valid_buckets if bucket.max_value is not None]
            return max(values) if values else None
        if aggregation == "median":
            values = []
            for bucket in valid_buckets:
                values.extend(bucket.values)
            return statistics.median(values) if values else None
        if aggregation == "variance":
            values = []
            for bucket in valid_buckets:
                values.extend(bucket.values)
            return statistics.pvariance(values) if values else None
        if aggregation == "stddev":
            values = []
            for bucket in valid_buckets:
                values.extend(bucket.values)
            return statistics.pstdev(values) if values else None
        if aggregation == "unique":
            merged = set()
            for bucket in valid_buckets:
                merged.update(bucket.unique_values)
            return float(len(merged))
        return None

    def _iter_specs(self, request: PivotRequest) -> Iterable[PivotFieldSpec]:
        for field_spec in request.row_fields:
            yield field_spec
        for field_spec in request.column_fields:
            yield field_spec
        if request.value_field is not None:
            yield request.value_field

    def _sort_tuple_key(self, values: Tuple[Any, ...]):
        return tuple("" if value is None else str(value).lower() for value in values)
