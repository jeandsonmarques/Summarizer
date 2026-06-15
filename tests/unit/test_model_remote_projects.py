import json
from pathlib import Path

from plugin.Summarizer.model_view.model_remote_projects import (
    DEFAULT_REMOTE_PROJECT_TABLE,
    connection_key,
    connection_label,
    is_pbsdash_payload,
    normalize_remote_project_table_target,
    postgres_candidate_tables_from_column_rows,
    project_payload_from_file,
    project_payload_from_value,
    remote_project_record_from_row,
)

ROOT = Path(__file__).resolve().parents[2]


def _project_payload(**extra):
    payload = {
        "version": 2,
        "project_id": "proj-1",
        "name": "Painel Comercial",
        "active_page_id": "page-1",
        "pages": [{"page_id": "page-1", "title": "Resumo", "items": []}],
        "items": [],
        "visual_links": [],
        "chart_relations": [],
        "source_meta": {},
        "updated_at": "2026-06-15T11:24:41",
    }
    payload.update(extra)
    return payload


def test_project_payload_from_value_accepts_native_and_nested_pbsdash_json():
    payload = _project_payload()

    assert is_pbsdash_payload(payload)
    assert project_payload_from_value(json.dumps(payload))["name"] == "Painel Comercial"
    assert project_payload_from_value({"payload": json.dumps(payload)})["project_id"] == "proj-1"
    assert project_payload_from_value({"unrelated": True}) == {}


def test_project_payload_from_file_and_table_target_helpers(tmp_path):
    path = tmp_path / "painel-novo.pbsdash"
    path.write_text(json.dumps(_project_payload(name="Painel Novo")), encoding="utf-8")

    assert project_payload_from_file(str(path))["name"] == "Painel Novo"
    assert normalize_remote_project_table_target("db_engenharia_raw.paineis") == (
        "db_engenharia_raw",
        "paineis",
    )
    assert normalize_remote_project_table_target("", default_schema="db_engenharia_raw") == (
        "db_engenharia_raw",
        DEFAULT_REMOTE_PROJECT_TABLE,
    )


def test_remote_project_record_from_row_uses_database_metadata_and_payload_fallbacks():
    connection = {
        "driver": "PostgreSQL",
        "name": "BI Corporativo",
        "host": "db.local",
        "port": 5432,
        "database": "summarizer",
        "user": "analista",
    }

    record = remote_project_record_from_row(
        payload_value=json.dumps(_project_payload(name="Payload Name")),
        connection_meta=connection,
        schema="public",
        table="summarizer_dashboards",
        row_id=42,
        name_value="Linha Name",
        updated_at_value="2026-06-15T12:00:00",
        can_edit=True,
    )

    assert record is not None
    assert record.name == "Linha Name"
    assert record.connection_label == "BI Corporativo"
    assert record.schema == "public"
    assert record.table == "summarizer_dashboards"
    assert record.row_id == "42"
    assert record.can_edit is True
    assert record.payload["name"] == "Payload Name"
    assert "summarizer_dashboards" in record.source_id
    assert connection_label(connection) == "BI Corporativo"
    assert "postgresql" in connection_key(connection)
    assert connection_key({}) == ""


def test_remote_project_service_checks_postgres_update_permission():
    source = Path(ROOT / "plugin" / "Summarizer" / "model_view" / "model_remote_projects.py").read_text(
        encoding="utf-8"
    )

    assert "def _can_update_remote_project_table" in source
    assert "has_table_privilege(current_user, ?, 'UPDATE')" in source
    assert "can_edit=can_edit_table" in source
    assert "row_id: str = \"\"" in source
    assert "record_id = str(record_id or \"\").strip()" in source


def test_postgres_candidate_tables_group_payload_columns_from_metadata_rows():
    rows = [
        {"table_schema": "public", "table_name": "summarizer_dashboards", "column_name": "id", "data_type": "integer"},
        {
            "table_schema": "public",
            "table_name": "summarizer_dashboards",
            "column_name": "payload",
            "data_type": "jsonb",
        },
        {"table_schema": "public", "table_name": "clientes", "column_name": "nome", "data_type": "text"},
    ]

    candidates = postgres_candidate_tables_from_column_rows(rows)

    assert len(candidates) == 1
    assert candidates[0].schema == "public"
    assert candidates[0].table == "summarizer_dashboards"
    assert [column.name for column in candidates[0].payload_columns()] == ["payload"]
