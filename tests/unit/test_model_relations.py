from plugin.Summarizer.model_view.model_relations import (
    deduplicate_relationships,
    default_selected_fields,
    ensure_field_selections,
    normalize_direction,
)


def test_normalize_direction_supports_legacy_aliases():
    assert normalize_direction("forward") == "forward"
    assert normalize_direction("origem") == "forward"
    assert normalize_direction("backward") == "backward"
    assert normalize_direction("destino") == "backward"
    assert normalize_direction(None) == "both"


def test_default_selected_fields_excludes_only_one_field():
    fields = ["id", "name", "created_at"]
    assert default_selected_fields(fields, "name") == ["id", "created_at"]


def test_ensure_field_selections_fills_defaults_and_persists_direction():
    metadata = {
        "id": "rel-1",
        "source_table": "orders",
        "source_field": "id",
        "target_table": "customers",
        "target_field": "customer_id",
        "flow_direction": "reverse",
    }
    updates = []

    def field_lookup(table_name):
        return {
            "orders": ["id", "number", "customer_id"],
            "customers": ["customer_id", "name"],
        }.get(table_name, [])

    def on_update(rel_id, payload):
        updates.append((rel_id, dict(payload)))

    result = ensure_field_selections(
        metadata,
        field_lookup,
        persist=True,
        update_callback=on_update,
    )

    assert result["direction"] == "backward"
    assert result["selected_fields_origin_to_dest"] == ["number", "customer_id"]
    assert result["selected_fields_dest_to_origin"] == ["name"]
    assert updates and updates[0][0] == "rel-1"


def test_deduplicate_relationships_keeps_first_semantic_entry():
    relationships = [
        {
            "id": "r1",
            "source_table": "orders",
            "source_field": "customer_id",
            "target_table": "customers",
            "target_field": "id",
            "direction": "both",
            "cardinality": "1:*",
        },
        {
            "id": "r2",
            "source_table": "orders",
            "source_field": "customer_id",
            "target_table": "customers",
            "target_field": "id",
            "direction": "both",
            "cardinality": "1:*",
        },
        {
            "id": "r3",
            "source_table": "orders",
            "source_field": "id",
            "target_table": "customers",
            "target_field": "id",
            "direction": "both",
            "cardinality": "1:*",
        },
    ]

    deduped = deduplicate_relationships(relationships)

    assert [item["id"] for item in deduped] == ["r1", "r3"]
