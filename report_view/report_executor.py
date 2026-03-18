from collections import defaultdict
from typing import Dict, Optional

from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureRequest,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorLayer,
)

from .layer_schema_service import normalize_compact, normalize_text
from .result_models import FilterSpec, QueryPlan, QueryResult, ResultRow, SummaryPayload


class ReportExecutor:
    def execute(self, plan: QueryPlan) -> QueryResult:
        if plan.intent == "value_insight":
            return self._execute_value_insight(plan)
        if plan.intent == "aggregate_chart":
            return self._execute_direct(plan)
        if plan.intent == "spatial_aggregate":
            return self._execute_spatial(plan)
        return QueryResult(ok=False, message="Nao foi possivel montar um plano de consulta valido.")

    def _execute_value_insight(self, plan: QueryPlan) -> QueryResult:
        layer = self._get_layer(plan.target_layer_id)
        if layer is None or not layer.isValid():
            return QueryResult(ok=False, message="Nao encontrei a camada escolhida para esse relatorio.")
        if not plan.metric.field or plan.metric.field not in layer.fields().names():
            return QueryResult(ok=False, message="O campo consultado nao existe mais nessa camada.")

        values = []
        processed = 0
        for feature in layer.getFeatures():
            if not self._feature_matches_filters(feature, plan.filters, layer.fields().names(), "target"):
                continue
            processed += 1
            numeric_value = self._coerce_numeric(feature[plan.metric.field])
            if numeric_value is None:
                continue
            values.append(float(numeric_value))

        if not values:
            return QueryResult(ok=False, message="Nao encontrei dados compativeis com essa pergunta.")

        selected_value = min(values) if plan.metric.operation == "min" else max(values)
        label = plan.metric.field_label or plan.metric.field or "Valor"
        return QueryResult(
            ok=True,
            summary=SummaryPayload(text=self._build_value_insight_summary(plan, selected_value, processed)),
            rows=[ResultRow(category=label, value=float(selected_value), raw_category=label)],
            value_label=self._value_label(plan),
            show_percent=False,
            plan=plan,
            total_records=processed,
            total_value=float(selected_value),
        )

    def _execute_direct(self, plan: QueryPlan) -> QueryResult:
        layer = self._get_layer(plan.target_layer_id)
        if layer is None or not layer.isValid():
            return QueryResult(ok=False, message="Nao encontrei a camada escolhida para esse relatorio.")
        if plan.group_field not in layer.fields().names():
            return QueryResult(ok=False, message="O campo de agrupamento nao existe mais nessa camada.")
        if plan.metric.field and plan.metric.field not in layer.fields().names():
            return QueryResult(ok=False, message="O campo numerico usado na consulta nao existe mais.")

        totals = defaultdict(float)
        counts = defaultdict(int)
        processed = 0
        distance_area = self._distance_area(layer)

        for feature in layer.getFeatures():
            if not self._feature_matches_filters(feature, plan.filters, layer.fields().names(), "target"):
                continue
            category_value = self._render_category(feature[plan.group_field])
            if not category_value:
                continue

            if plan.metric.operation == "count":
                value = 1.0
            elif plan.metric.use_geometry:
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                if plan.metric.operation == "length":
                    value = self._safe_float(distance_area.measureLength(geometry))
                else:
                    value = self._safe_float(distance_area.measureArea(geometry))
                if value is None:
                    continue
            else:
                value = self._safe_float(feature[plan.metric.field]) if plan.metric.field else None
                if value is None:
                    continue

            totals[category_value] += float(value)
            counts[category_value] += 1
            processed += 1

        return self._build_result(plan, totals, counts, processed)

    def _execute_spatial(self, plan: QueryPlan) -> QueryResult:
        source_layer = self._get_layer(plan.source_layer_id)
        boundary_layer = self._get_layer(plan.boundary_layer_id)
        if source_layer is None or not source_layer.isValid():
            return QueryResult(ok=False, message="Nao encontrei a camada de origem dessa consulta.")
        if boundary_layer is None or not boundary_layer.isValid():
            return QueryResult(ok=False, message="Nao encontrei a camada de limites dessa consulta.")
        if plan.group_field not in boundary_layer.fields().names():
            return QueryResult(ok=False, message="O campo de agrupamento nao existe mais na camada de limites.")

        request = QgsFeatureRequest()
        if boundary_layer.fields().indexFromName(plan.group_field) >= 0:
            request.setSubsetOfAttributes([plan.group_field], boundary_layer.fields())

        boundary_features: Dict[int, object] = {}
        spatial_index = QgsSpatialIndex()
        transform = None
        if source_layer.crs() != boundary_layer.crs():
            try:
                transform = QgsCoordinateTransform(
                    boundary_layer.crs(),
                    source_layer.crs(),
                    QgsProject.instance(),
                )
            except Exception:
                transform = None
        for feature in boundary_layer.getFeatures(request):
            if not self._feature_matches_filters(feature, plan.filters, boundary_layer.fields().names(), "boundary"):
                continue
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            if transform is not None:
                try:
                    geometry.transform(transform)
                except Exception:
                    continue

            boundary_features[feature.id()] = (geometry, feature[plan.group_field])
            index_feature = QgsFeature()
            index_feature.setId(feature.id())
            index_feature.setGeometry(geometry)
            spatial_index.addFeature(index_feature)

        if not boundary_features:
            return QueryResult(ok=False, message="A camada de limites nao possui geometrias validas.")

        totals = defaultdict(float)
        counts = defaultdict(int)
        processed = 0
        distance_area = self._distance_area(source_layer)

        for source_feature in source_layer.getFeatures():
            if not self._feature_matches_filters(source_feature, plan.filters, source_layer.fields().names(), "source"):
                continue
            source_geometry = source_feature.geometry()
            if source_geometry is None or source_geometry.isEmpty():
                continue

            candidate_ids = spatial_index.intersects(source_geometry.boundingBox())
            matched = False
            for boundary_id in candidate_ids:
                boundary_feature = boundary_features.get(boundary_id)
                if boundary_feature is None:
                    continue
                boundary_geometry, boundary_value = boundary_feature
                if boundary_geometry is None or boundary_geometry.isEmpty():
                    continue

                if plan.spatial_relation == "within":
                    is_match = source_geometry.within(boundary_geometry) or source_geometry.intersects(boundary_geometry)
                else:
                    is_match = source_geometry.intersects(boundary_geometry)
                if not is_match:
                    continue

                category_value = self._render_category(boundary_value)
                if not category_value:
                    continue

                if plan.metric.operation == "count":
                    value = 1.0
                else:
                    intersection = source_geometry.intersection(boundary_geometry)
                    if intersection is None or intersection.isEmpty():
                        continue
                    if plan.metric.operation == "length":
                        value = self._safe_float(distance_area.measureLength(intersection))
                    else:
                        value = self._safe_float(distance_area.measureArea(intersection))
                    if value is None:
                        continue

                totals[category_value] += float(value)
                counts[category_value] += 1
                matched = True

            if matched:
                processed += 1

        return self._build_result(plan, totals, counts, processed)

    def _build_result(self, plan: QueryPlan, totals, counts, processed: int) -> QueryResult:
        rows = []
        for category, total in totals.items():
            value = float(total)
            if plan.metric.operation == "avg":
                divider = max(1, counts.get(category, 0))
                value = value / divider
            rows.append(ResultRow(category=str(category), value=float(value), raw_category=category))

        if not rows:
            return QueryResult(ok=False, message="Nao encontrei dados compativeis com essa pergunta.")

        if plan.group_field_kind in {"date", "datetime"}:
            rows.sort(key=lambda item: str(item.raw_category))
        elif plan.group_field_kind in {"integer", "numeric"}:
            rows.sort(key=lambda item: (self._coerce_numeric(item.raw_category) or 0.0, item.category.lower()), reverse=True)
        else:
            rows.sort(key=lambda item: (-item.value, item.category.lower()))

        if plan.top_n:
            rows = rows[: plan.top_n]

        total_value = sum(row.value for row in rows)
        show_percent = plan.metric.operation != "avg" and total_value > 0 and len(rows) > 1
        if show_percent:
            for row in rows:
                row.percent = (row.value / total_value) * 100.0 if total_value else None

        return QueryResult(
            ok=True,
            summary=SummaryPayload(text=self._build_summary(plan, rows, processed)),
            rows=rows,
            value_label=self._value_label(plan),
            show_percent=show_percent,
            plan=plan,
            total_records=processed,
            total_value=total_value,
        )

    def _build_summary(self, plan: QueryPlan, rows, processed: int) -> str:
        if not rows:
            return "Nao encontrei dados compativeis com essa pergunta."

        top = rows[0].category
        if plan.metric.operation == "count":
            if any(token in normalize_text(plan.group_field) for token in ("dn", "diam", "diametro", "bitola")):
                message = f"Foram encontrados {len(rows)} diametros distintos. O mais frequente e {top}."
            else:
                message = f"{top} possui a maior quantidade."
        elif plan.metric.operation == "length":
            message = f"{top} possui a maior extensao total."
        elif plan.metric.operation == "area":
            message = f"{top} possui a maior area total."
        elif plan.metric.operation == "avg":
            message = f"{top} possui a maior media."
        else:
            message = f"{top} possui o maior total."

        if plan.metric.operation == "count" and processed > 0 and len(rows) > 1:
            message += f" Foram encontrados {processed} registros distribuidos em {len(rows)} categorias."
        return message

    def _build_value_insight_summary(self, plan: QueryPlan, value: float, processed: int) -> str:
        field_label = (plan.metric.field_label or plan.metric.field or "valor").strip()
        value_text = self._format_summary_value(value)
        filters = [str(item.value).strip() for item in plan.filters if item.value not in (None, "")]
        scope_text = f" em {', '.join(filters[:3])}" if filters else ""
        if plan.metric.operation == "min":
            message = f"O menor {field_label.lower()}{scope_text} e {value_text}."
        else:
            message = f"O maior {field_label.lower()}{scope_text} e {value_text}."
        if processed > 0:
            message += f" Foram analisados {processed} registros."
        return message

    def _value_label(self, plan: QueryPlan) -> str:
        if plan.metric.operation == "count":
            return "Quantidade"
        if plan.metric.operation == "length":
            return "Extensao"
        if plan.metric.operation == "area":
            return "Area"
        if plan.metric.operation == "avg":
            return "Media"
        if plan.metric.operation == "max":
            return plan.metric.label or "Maior valor"
        if plan.metric.operation == "min":
            return plan.metric.label or "Menor valor"
        return "Valor"

    def _distance_area(self, layer: QgsVectorLayer) -> QgsDistanceArea:
        distance_area = QgsDistanceArea()
        distance_area.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        ellipsoid = QgsProject.instance().ellipsoid()
        if ellipsoid:
            try:
                distance_area.setEllipsoid(ellipsoid)
            except Exception:
                pass
        return distance_area

    def _get_layer(self, layer_id: Optional[str]) -> Optional[QgsVectorLayer]:
        if not layer_id:
            return None
        layer = QgsProject.instance().mapLayer(layer_id)
        if isinstance(layer, QgsVectorLayer):
            return layer
        return None

    def _render_category(self, value) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip()

    def _safe_float(self, value) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _feature_matches_filters(self, feature, filters, field_names, layer_role: str) -> bool:
        if not filters:
            return True
        field_names = set(field_names or [])
        for filter_spec in filters:
            if not isinstance(filter_spec, FilterSpec):
                continue
            if filter_spec.layer_role not in {"any", layer_role}:
                continue
            if not filter_spec.field or filter_spec.field not in field_names:
                return False

            current_value = feature[filter_spec.field]
            if not self._match_filter_value(current_value, filter_spec):
                return False
        return True

    def _match_filter_value(self, current_value, filter_spec: FilterSpec) -> bool:
        operator = (filter_spec.operator or "eq").lower()
        if operator in {"is_null", "null"}:
            return current_value in (None, "")
        if current_value in (None, ""):
            return False

        expected = filter_spec.value
        current_text = normalize_text(current_value)
        expected_text = normalize_text(expected)
        current_compact = normalize_compact(current_value)
        expected_compact = normalize_compact(expected)
        current_number = self._coerce_numeric(current_value)
        expected_number = self._coerce_numeric(expected)

        matches = False
        if current_number is not None and expected_number is not None:
            matches = abs(current_number - expected_number) < 0.0001
        if not matches and expected_text:
            matches = current_text == expected_text or current_compact == expected_compact
        if not matches and expected_text:
            matches = f" {expected_text} " in f" {current_text} " or expected_text in current_text
        if not matches and expected_compact:
            matches = expected_compact in current_compact

        if operator == "contains":
            return bool(expected_text and expected_text in current_text) or bool(expected_compact and expected_compact in current_compact)
        if operator == "neq":
            return not matches
        return matches

    def _coerce_numeric(self, value) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            cleaned = "".join(char for char in str(value) if char.isdigit() or char in ",.-")
            if not cleaned:
                return None
            cleaned = cleaned.replace(",", ".")
            if cleaned.count(".") > 1:
                cleaned = cleaned.replace(".", "", cleaned.count(".") - 1)
            return float(cleaned)
        except Exception:
            return None

    def _format_summary_value(self, value: float) -> str:
        if abs(value - round(value)) < 0.0001:
            return str(int(round(value)))
        return f"{value:.2f}".replace(".", ",")
