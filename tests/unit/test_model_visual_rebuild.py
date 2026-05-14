from plugin.Summarizer.dashboard_models import DashboardChartBinding, FieldBindingItem, ROLE_VALUES, ROLE_X_AXIS
from plugin.Summarizer.model_view.model_visual_rebuild import (
    aggregate_feature_rows,
    build_model_chart_item_from_layer,
    resolve_binding_items_for_layer,
    safe_float,
)


class FakeField:
    def __init__(self, name, type_name="string", numeric=False):
        self._name = name
        self._type_name = type_name
        self._numeric = numeric

    def name(self):
        return self._name

    def typeName(self):
        return self._type_name

    def isNumeric(self):
        return self._numeric


class FakeFields:
    def __init__(self, fields):
        self._fields = list(fields)

    def __iter__(self):
        return iter(self._fields)

    def lookupField(self, name):
        target = str(name or "")
        for index, field in enumerate(self._fields):
            if field.name() == target:
                return index
        return -1

    def field(self, index):
        return self._fields[index]


class FakeFeature:
    def __init__(self, feature_id, attrs):
        self._id = feature_id
        self._attrs = dict(attrs)

    def id(self):
        return self._id

    def attribute(self, name):
        return self._attrs.get(name)


class FakeLayer:
    def __init__(self, fields, features, valid=True):
        self._fields = FakeFields(fields)
        self._features = list(features)
        self._valid = bool(valid)

    def fields(self):
        return self._fields

    def getFeatures(self):
        return iter(self._features)

    def name(self):
        return "Layer A"

    def id(self):
        return "layer-a"

    def isValid(self):
        return self._valid


def test_safe_float_accepts_common_number_formats():
    assert safe_float("1.234,50") == 1234.5
    assert safe_float("12,5") == 12.5
    assert safe_float(" 42 ") == 42.0
    assert safe_float("") is None
    assert safe_float(None) is None
    assert safe_float("abc") is None


def test_aggregate_feature_rows_ignores_null_numeric_values():
    layer = FakeLayer(
        [FakeField("grupo"), FakeField("valor", "double", numeric=True)],
        [
            FakeFeature(1, {"grupo": "A", "valor": "10"}),
            FakeFeature(2, {"grupo": "A", "valor": None}),
            FakeFeature(3, {"grupo": "B", "valor": "5"}),
        ],
    )

    rows, truncated, has_numeric = aggregate_feature_rows(
        layer,
        dimension_field="grupo",
        value_field="valor",
        aggregation="sum",
        top_n=10,
    )

    assert truncated is False
    assert has_numeric is True
    assert [(row["category"], row["value"]) for row in rows] == [("A", 10.0), ("B", 5.0)]


def test_resolve_binding_items_for_layer_skips_missing_fields():
    layer = FakeLayer([FakeField("Grupo"), FakeField("Valor", "double", numeric=True)], [])
    binding = DashboardChartBinding(
        chart_type="bar",
        bindings={
            ROLE_X_AXIS: [FieldBindingItem("grupo", "grupo", "text", "none", ROLE_X_AXIS, 0)],
            ROLE_VALUES: [FieldBindingItem("ausente", "ausente", "numeric", "sum", ROLE_VALUES, 0)],
        },
    ).normalized()

    x_items = resolve_binding_items_for_layer(binding, ROLE_X_AXIS, layer)
    value_items = resolve_binding_items_for_layer(binding, ROLE_VALUES, layer)

    assert [item.field for item in x_items] == ["Grupo"]
    assert value_items == []


def test_build_model_chart_item_from_layer_creates_bar_payload():
    layer = FakeLayer(
        [FakeField("grupo"), FakeField("valor", "double", numeric=True)],
        [
            FakeFeature(1, {"grupo": "A", "valor": "10"}),
            FakeFeature(2, {"grupo": "B", "valor": "3"}),
        ],
    )

    result = build_model_chart_item_from_layer(
        layer,
        dimension_field="grupo",
        value_field="valor",
        aggregation="sum",
        chart_type="bar",
        top_n=5,
        title_text="",
    )

    assert result.error == ""
    assert result.item is not None
    assert result.item.payload.chart_type == "bar"
    assert result.item.payload.categories == ["A", "B"]
    assert result.item.payload.values == [10.0, 3.0]
    assert result.item.binding.to_dict()["bindings"]


def test_build_model_chart_item_from_layer_handles_count_card_and_empty_layer():
    populated = FakeLayer([FakeField("grupo")], [FakeFeature(1, {"grupo": "A"}), FakeFeature(2, {"grupo": None})])
    card = build_model_chart_item_from_layer(
        populated,
        dimension_field="grupo",
        value_field="__count__",
        aggregation="count",
        chart_type="card",
        top_n=5,
        title_text="",
    )
    empty = build_model_chart_item_from_layer(
        FakeLayer([FakeField("grupo")], []),
        dimension_field="grupo",
        value_field="__count__",
        aggregation="count",
        chart_type="bar",
        top_n=5,
        title_text="",
    )

    assert card.error == ""
    assert card.item.payload.chart_type == "card"
    assert card.item.payload.values == [1.0, 1.0]
    assert empty.item is None
    assert empty.error == "A camada nao possui dados suficientes para montar o grafico."


def test_build_model_chart_item_from_layer_reports_missing_fields():
    layer = FakeLayer([FakeField("grupo")], [FakeFeature(1, {"grupo": "A"})])

    result = build_model_chart_item_from_layer(
        layer,
        dimension_field="missing",
        value_field="__count__",
        aggregation="count",
        chart_type="bar",
        top_n=5,
        title_text="",
    )

    assert result.item is None
    assert result.error == "O campo de categoria nao existe na camada selecionada."
