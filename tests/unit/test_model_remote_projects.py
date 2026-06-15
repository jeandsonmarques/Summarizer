import json
from pathlib import Path

import pytest
from plugin.Summarizer.model_view import model_remote_projects as remote_projects
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
    safe_source_filename,
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


def test_safe_source_filename_strips_windows_and_unix_directories():
    windows_path = r"C:\Users\jeandson.silva\Documents\Projetos\painel.pbsdash"
    unix_path = "/home/jeandson/projetos/painel.pbsdash"

    assert safe_source_filename(windows_path) == "painel.pbsdash"
    assert safe_source_filename(unix_path) == "painel.pbsdash"
    assert remote_projects._remote_project_record_values(
        _project_payload(),
        windows_path,
    )[4] == "painel.pbsdash"
    assert "Users" not in safe_source_filename(windows_path)
    assert "home" not in safe_source_filename(unix_path)


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
        source_file_value=r"C:\Users\analista\painel.pbsdash",
        can_edit=True,
    )

    assert record is not None
    assert record.name == "Linha Name"
    assert record.connection_label == "BI Corporativo"
    assert record.schema == "public"
    assert record.table == "summarizer_dashboards"
    assert record.row_id == "42"
    assert record.source_file == "painel.pbsdash"
    assert record.can_edit is True
    assert record.payload["name"] == "Payload Name"
    assert "summarizer_dashboards" in record.source_id
    assert connection_label(connection) == "BI Corporativo"
    assert "postgresql" in connection_key(connection)
    assert connection_key({}) == ""


def test_remote_project_service_checks_postgres_update_permission():
    source_path = ROOT / "plugin" / "Summarizer" / "model_view" / "model_remote_projects.py"
    source = source_path.read_text(encoding="utf-8")

    assert "def _can_update_remote_project_table" in source
    assert "has_table_privilege(current_user, ?, 'UPDATE')" in source
    assert "can_edit=can_edit_table" in source
    assert "row_id: str = \"\"" in source
    assert "record_id = str(record_id or \"\").strip()" in source


def test_postgres_candidate_tables_only_accept_remote_project_table_names():
    rows = [
        {
            "table_schema": "public",
            "table_name": DEFAULT_REMOTE_PROJECT_TABLE,
            "column_name": "payload",
            "data_type": "jsonb",
        },
        {
            "table_schema": "public",
            "table_name": "summarizer_dashboards",
            "column_name": "payload",
            "data_type": "jsonb",
        },
        {
            "table_schema": "public",
            "table_name": "clientes",
            "column_name": "data",
            "data_type": "jsonb",
        },
        {
            "table_schema": "audit",
            "table_name": "auditoria",
            "column_name": "body",
            "data_type": "text",
        },
    ]

    candidates = postgres_candidate_tables_from_column_rows(rows)

    assert len(candidates) == 2
    assert candidates[0].schema == "public"
    assert candidates[0].table == DEFAULT_REMOTE_PROJECT_TABLE
    assert candidates[1].table == "summarizer_dashboards"
    assert [column.name for column in candidates[0].payload_columns()] == ["payload"]
    assert normalize_remote_project_table_target("public.clientes") == ("public", "clientes")


@pytest.mark.parametrize(
    "identifier",
    [
        "public; DROP TABLE clientes",
        "tabela--",
        "tabela/*",
        "schema.tabela;DELETE",
        "nome\x01controle",
        "",
    ],
)
def test_malicious_postgres_identifiers_are_rejected(identifier):
    with pytest.raises(ValueError):
        remote_projects._validate_pg_identifier(identifier)


class _FakeSqlQuery:
    instances = []
    rows_affected = 1

    def __init__(self, db):
        self.db = db
        self.sql = ""
        self.binds = []
        _FakeSqlQuery.instances.append(self)

    def prepare(self, sql):
        self.sql = sql
        return True

    def addBindValue(self, value):
        self.binds.append(value)

    def exec_(self, sql=None):
        if sql is not None:
            self.sql = sql
        return True

    def numRowsAffected(self):
        return self.rows_affected


def _install_fake_query(monkeypatch, rows_affected=1):
    _FakeSqlQuery.instances = []
    _FakeSqlQuery.rows_affected = rows_affected
    monkeypatch.setattr(remote_projects, "QSqlQuery", _FakeSqlQuery)


def test_existing_remote_project_uses_update_without_insert(monkeypatch):
    _install_fake_query(monkeypatch)
    service = remote_projects.ModelRemoteProjectService({"driver": "PostgreSQL"})
    service._can_update_remote_project_table = lambda *_: True

    record = service._update_remote_project_record(
        object(),
        _project_payload(),
        "public",
        DEFAULT_REMOTE_PROJECT_TABLE,
        "painel.pbsdash",
        record_id="row-1",
    )

    sql = _FakeSqlQuery.instances[0].sql.upper()
    assert sql.startswith("UPDATE ")
    assert "INSERT" not in sql
    assert "WHERE id = ?" in _FakeSqlQuery.instances[0].sql
    assert _FakeSqlQuery.instances[0].binds[-1] == "row-1"
    assert record.row_id == "row-1"


def test_update_requires_existing_row_id_and_reports_missing_row(monkeypatch):
    _install_fake_query(monkeypatch, rows_affected=0)
    service = remote_projects.ModelRemoteProjectService({"driver": "PostgreSQL"})
    service._can_update_remote_project_table = lambda *_: True

    with pytest.raises(RuntimeError, match="identificador"):
        service._update_remote_project_record(
            object(),
            _project_payload(),
            "public",
            DEFAULT_REMOTE_PROJECT_TABLE,
            "",
            record_id="",
        )

    with pytest.raises(RuntimeError, match="nao encontrado"):
        service._update_remote_project_record(
            object(),
            _project_payload(),
            "public",
            DEFAULT_REMOTE_PROJECT_TABLE,
            "",
            record_id="missing-row",
        )


def test_new_remote_project_import_uses_insert(monkeypatch):
    _install_fake_query(monkeypatch)
    service = remote_projects.ModelRemoteProjectService({"driver": "PostgreSQL"})
    service._can_insert_remote_project_table = lambda *_: True
    service._can_update_remote_project_table = lambda *_: True

    record = service._insert_remote_project_record(
        object(),
        _project_payload(),
        "public",
        DEFAULT_REMOTE_PROJECT_TABLE,
        r"C:\Users\analista\painel.pbsdash",
    )

    sql = _FakeSqlQuery.instances[0].sql.upper()
    assert sql.startswith("INSERT INTO ")
    assert "ON CONFLICT" in sql
    assert _FakeSqlQuery.instances[0].binds[4] == "painel.pbsdash"
    assert record.source_file == "painel.pbsdash"
