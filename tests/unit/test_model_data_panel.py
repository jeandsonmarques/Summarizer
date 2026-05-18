from plugin.Summarizer.model_view.model_data_panel import (
    field_catalog_for_layer,
    field_group_for_def,
    field_is_date_like,
    field_is_numeric,
    resolve_layer_field_name,
)


class FakeField:
    def __init__(self, name, type_name, numeric=False, raises_numeric=False):
        self._name = name
        self._type_name = type_name
        self._numeric = numeric
        self._raises_numeric = raises_numeric

    def name(self):
        return self._name

    def typeName(self):
        return self._type_name

    def isNumeric(self):
        if self._raises_numeric:
            raise RuntimeError("numeric metadata unavailable")
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


class FakeLayer:
    def __init__(self, fields):
        self._fields = FakeFields(fields)

    def fields(self):
        return self._fields

    def name(self):
        return "Layer A"

    def id(self):
        return "layer-a"


def test_field_classification_uses_numeric_metadata_first():
    field = FakeField("valor", "varchar", numeric=True)

    assert field_is_numeric(field) is True
    assert field_group_for_def(field) == "measure"


def test_field_classification_falls_back_to_type_name():
    numeric = FakeField("valor", "decimal", raises_numeric=True)
    date = FakeField("data", "datetime")
    text = FakeField("nome", "string")
    other = FakeField("geom", "geometry")

    assert field_is_numeric(numeric) is True
    assert field_is_date_like(date) is True
    assert field_group_for_def(numeric) == "measure"
    assert field_group_for_def(date) == "date"
    assert field_group_for_def(text) == "dimension"
    assert field_group_for_def(other) == "other"


def test_field_catalog_preserves_grouping_and_suggested_roles():
    layer = FakeLayer(
        [
            FakeField("nome", "string"),
            FakeField("valor", "double", numeric=True),
            FakeField("data", "date"),
            FakeField("", "string"),
        ]
    )

    catalog = field_catalog_for_layer(layer)

    assert [item["field_name"] for item in catalog["all"]] == ["nome", "valor", "data"]
    assert [item["field_group"] for item in catalog["all"]] == ["dimension", "measure", "date"]
    assert catalog["all"][0]["suggested_role"] == "x_axis"
    assert catalog["all"][1]["suggested_role"] == "values"
    assert catalog["all"][2]["suggested_role"] == "x_axis"


def test_resolve_layer_field_name_accepts_exact_and_case_insensitive_matches():
    layer = FakeLayer([FakeField("Municipio", "string"), FakeField("Valor", "double")])

    assert resolve_layer_field_name(layer, "Valor") == "Valor"
    assert resolve_layer_field_name(layer, "municipio") == "Municipio"
    assert resolve_layer_field_name(layer, "missing") == ""
