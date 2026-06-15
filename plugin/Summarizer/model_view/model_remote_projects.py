# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

try:  # pragma: no cover - QtSql availability depends on the QGIS install
    from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery
except Exception:  # pragma: no cover
    QSqlDatabase = None
    QSqlQuery = None

try:
    from ..utils.i18n_runtime import tr_text as _rt
except Exception:

    def _rt(text: str, **kwargs) -> str:
        return str(text).format(**kwargs) if kwargs else str(text)


REMOTE_PROJECT_LIMIT = 8
DEFAULT_REMOTE_PROJECT_TABLE = "summarizer_model_projects"
_SCAN_TABLE_LIMIT = 24
_SCAN_ROWS_PER_PAYLOAD_COLUMN = 20
_PG_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_PROJECT_TABLE_NAME_MARKERS = ("summarizer", "pbsdash", "dashboard", "painel", "project", "projeto")

_PAYLOAD_COLUMN_HINTS = {
    "payload",
    "project",
    "project_payload",
    "dashboard",
    "dashboard_payload",
    "pbsdash",
    "content",
    "conteudo",
    "arquivo",
    "file_content",
    "body",
    "definition",
    "config",
    "configuration",
    "document",
    "project_json",
    "dashboard_json",
    "json",
    "data",
}
_NAME_COLUMN_HINTS = (
    "name",
    "title",
    "project_name",
    "dashboard_name",
    "file_name",
    "filename",
    "nome",
    "titulo",
)
_UPDATED_COLUMN_HINTS = (
    "updated_at",
    "modified_at",
    "changed_at",
    "created_at",
    "data_atualizacao",
    "data_modificacao",
    "atualizado_em",
    "criado_em",
)
_ID_COLUMN_HINTS = ("id", "project_id", "dashboard_id", "uuid", "codigo")
_FORMAT_COLUMN_HINTS = ("format", "file_format", "extension", "extensao", "mime_type", "type", "tipo")
_SOURCE_FILE_COLUMN_HINTS = ("source_file", "file_name", "filename", "arquivo", "origem")


@dataclass
class RemoteProjectRecord:
    source_id: str
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    connection_meta: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""
    connection_label: str = ""
    schema: str = ""
    table: str = ""
    row_id: str = ""
    source_file: str = ""
    can_edit: bool = False


@dataclass
class RemoteProjectScanResult:
    records: List[RemoteProjectRecord] = field(default_factory=list)
    connected: bool = False
    error_message: str = ""


@dataclass
class _PostgresColumnInfo:
    schema: str
    table: str
    name: str
    data_type: str = ""


@dataclass
class _PostgresCandidateTable:
    schema: str
    table: str
    columns: List[_PostgresColumnInfo] = field(default_factory=list)

    def has_table_hint(self) -> bool:
        return is_remote_project_table_name(self.table)

    def payload_columns(self) -> List[_PostgresColumnInfo]:
        if not self.has_table_hint():
            return []
        results: List[_PostgresColumnInfo] = []
        for column in self.columns:
            data_type = column.data_type.lower()
            name = column.name.lower()
            text_payload_hint = (
                name in _PAYLOAD_COLUMN_HINTS
                or "payload" in name
                or "content" in name
                or "conteudo" in name
                or "json" in name
                or "pbsdash" in name
            )
            if (
                name in _PAYLOAD_COLUMN_HINTS
                or "pbsdash" in name
                or data_type in {"json", "jsonb"}
                or (text_payload_hint and ("text" in data_type or "char" in data_type))
            ):
                results.append(column)
        return results

    def column_by_hints(self, hints: Iterable[str]) -> Optional[_PostgresColumnInfo]:
        lowered = {str(item).lower() for item in hints}
        for column in self.columns:
            if column.name.lower() in lowered:
                return column
        return None


def connection_key(connection_meta: Mapping[str, Any]) -> str:
    meta = dict(connection_meta or {})
    parts = [
        str(meta.get("source_driver") or meta.get("driver") or ""),
        str(meta.get("host") or ""),
        str(meta.get("port") or ""),
        str(meta.get("database") or ""),
        str(meta.get("service") or ""),
        str(meta.get("user") or ""),
        str(meta.get("name") or ""),
    ]
    cleaned = [part.strip().lower() for part in parts]
    if not any(cleaned):
        return ""
    return "|".join(cleaned)


def connection_label(connection_meta: Mapping[str, Any]) -> str:
    meta = dict(connection_meta or {})
    for key in ("name", "database", "host", "driver", "source_driver"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    return _rt("Banco")


def is_supported_remote_project_driver(driver: str) -> bool:
    normalized = str(driver or "").strip().lower()
    return normalized in {"postgres", "postgresql", "postgis"}


def is_remote_project_table_name(table: str) -> bool:
    table_name = str(table or "").strip().lower()
    if not table_name:
        return False
    return any(marker in table_name for marker in _PROJECT_TABLE_NAME_MARKERS)


def is_pbsdash_payload(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    keys = {str(key) for key in payload.keys()}
    project_markers = {"pages", "items", "visual_links", "chart_relations", "source_meta", "active_page_id"}
    identity_markers = {"name", "project_id", "version"}
    return bool(project_markers & keys) and bool(identity_markers & keys)


def project_payload_from_value(value: Any) -> Dict[str, Any]:
    parsed = _parse_json_value(value)
    if is_pbsdash_payload(parsed):
        return dict(parsed)
    if isinstance(parsed, Mapping):
        for key in ("project", "dashboard", "pbsdash", "payload", "content", "data"):
            nested = parsed.get(key)
            if is_pbsdash_payload(nested):
                return dict(nested)
            nested_parsed = _parse_json_value(nested)
            if is_pbsdash_payload(nested_parsed):
                return dict(nested_parsed)
    return {}


def project_payload_from_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handler:
        payload = json.load(handler)
    if not is_pbsdash_payload(payload):
        raise ValueError(_rt("Arquivo .pbsdash invalido."))
    return dict(payload)


def safe_source_filename(path: str) -> str:
    return os.path.basename(str(path or "").replace("\\", "/"))


def normalize_remote_project_table_target(value: str, default_schema: str = "public") -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return str(default_schema or "public").strip() or "public", DEFAULT_REMOTE_PROJECT_TABLE
    cleaned = text.replace('"', "").strip()
    parts = [part.strip() for part in cleaned.split(".") if part.strip()]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    if len(parts) == 1:
        return str(default_schema or "public").strip() or "public", parts[0]
    return str(default_schema or "public").strip() or "public", DEFAULT_REMOTE_PROJECT_TABLE


def remote_project_record_from_row(
    *,
    payload_value: Any,
    connection_meta: Mapping[str, Any],
    schema: str,
    table: str,
    row_id: Any = "",
    name_value: Any = "",
    updated_at_value: Any = "",
    source_file_value: Any = "",
    can_edit: bool = False,
) -> Optional[RemoteProjectRecord]:
    payload = project_payload_from_value(payload_value)
    if not payload:
        return None
    project_name = str(name_value or payload.get("name") or table or _rt("Painel remoto")).strip()
    updated_at = str(updated_at_value or payload.get("updated_at") or payload.get("created_at") or "").strip()
    project_id = str(payload.get("project_id") or "").strip()
    row_id_text = str(row_id or project_id or project_name).strip()
    label = connection_label(connection_meta)
    source_parts = [
        "db",
        connection_key(connection_meta),
        str(schema or ""),
        str(table or ""),
        row_id_text,
        project_id,
    ]
    source_id = "|".join(source_parts)
    return RemoteProjectRecord(
        source_id=source_id,
        name=project_name or _rt("Painel remoto"),
        payload=dict(payload),
        connection_meta=dict(connection_meta or {}),
        updated_at=updated_at,
        connection_label=label,
        schema=str(schema or ""),
        table=str(table or ""),
        row_id=row_id_text,
        source_file=safe_source_filename(str(source_file_value or "")),
        can_edit=bool(can_edit),
    )


def postgres_candidate_tables_from_column_rows(rows: Iterable[Any]) -> List[_PostgresCandidateTable]:
    grouped: Dict[tuple[str, str], _PostgresCandidateTable] = {}
    for row in rows or []:
        schema = _row_value(row, "table_schema", 0)
        table = _row_value(row, "table_name", 1)
        column = _row_value(row, "column_name", 2)
        data_type = _row_value(row, "data_type", 3)
        if not schema or not table or not column:
            continue
        key = (str(schema), str(table))
        grouped.setdefault(key, _PostgresCandidateTable(schema=str(schema), table=str(table))).columns.append(
            _PostgresColumnInfo(
                schema=str(schema),
                table=str(table),
                name=str(column),
                data_type=str(data_type or ""),
            )
        )
    candidates = [
        table_info
        for table_info in grouped.values()
        if table_info.payload_columns()
    ]
    candidates.sort(key=_remote_project_table_sort_key)
    return candidates[:_SCAN_TABLE_LIMIT]


class ModelRemoteProjectService:
    def __init__(
        self,
        connection_meta: Mapping[str, Any],
        limit: int = REMOTE_PROJECT_LIMIT,
        cancel_requested: Optional[Callable[[], bool]] = None,
    ):
        self.connection_meta = dict(connection_meta or {})
        self.limit = max(1, int(limit or REMOTE_PROJECT_LIMIT))
        self._cancel_requested = cancel_requested

    def load_recent_projects(self) -> RemoteProjectScanResult:
        driver = str(self.connection_meta.get("source_driver") or self.connection_meta.get("driver") or "")
        if not is_supported_remote_project_driver(driver):
            return RemoteProjectScanResult([], False, _rt("Conexao sem suporte para projetos remotos."))
        if QSqlDatabase is None or QSqlQuery is None:
            return RemoteProjectScanResult([], False, _rt("QtSql nao esta disponivel nesta instalacao."))

        db = None
        conn_name = f"summarizer_remote_projects_{id(self)}"
        try:
            if self._is_cancel_requested():
                return RemoteProjectScanResult([], False, "")
            ok, db_or_error = self._open_postgres_database(conn_name)
            if not ok:
                return RemoteProjectScanResult([], False, str(db_or_error or ""))
            db = db_or_error
            if self._is_cancel_requested():
                return RemoteProjectScanResult([], False, "")
            records = self._load_postgres_records(db)
            return RemoteProjectScanResult(records[: self.limit], True, "")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    _ignore_optional_cleanup_error()
            db = None
            db_or_error = None
            try:
                QSqlDatabase.removeDatabase(conn_name)
            except Exception:
                _ignore_optional_cleanup_error()

    def save_project_file(
        self,
        path: str,
        *,
        schema: str = "public",
        table: str = DEFAULT_REMOTE_PROJECT_TABLE,
    ) -> RemoteProjectRecord:
        payload = project_payload_from_file(path)
        return self.save_project_payload(
            payload,
            schema=schema,
            table=table,
            source_file=safe_source_filename(path),
        )

    def save_project_payload(
        self,
        payload: Mapping[str, Any],
        *,
        schema: str = "public",
        table: str = DEFAULT_REMOTE_PROJECT_TABLE,
        source_file: str = "",
        row_id: str = "",
    ) -> RemoteProjectRecord:
        driver = str(self.connection_meta.get("source_driver") or self.connection_meta.get("driver") or "")
        if not is_supported_remote_project_driver(driver):
            raise RuntimeError(_rt("Conexao sem suporte para salvar projetos remotos."))
        if QSqlDatabase is None or QSqlQuery is None:
            raise RuntimeError(_rt("QtSql nao esta disponivel nesta instalacao."))
        if not is_pbsdash_payload(payload):
            raise ValueError(_rt("Projeto .pbsdash invalido."))

        schema_name, table_name = normalize_remote_project_table_target(
            f"{schema}.{table}" if schema else table,
            default_schema="public",
        )
        row_id_text = str(row_id or "").strip()
        source_filename = safe_source_filename(source_file)
        db = None
        conn_name = f"summarizer_remote_project_save_{id(self)}"
        try:
            ok, db_or_error = self._open_postgres_database(conn_name)
            if not ok:
                raise RuntimeError(str(db_or_error or _rt("Falha ao abrir a conexao.")))
            db = db_or_error
            if row_id_text:
                return self._update_remote_project_record(
                    db,
                    dict(payload),
                    schema_name,
                    table_name,
                    source_filename,
                    record_id=row_id_text,
                )
            self._ensure_remote_project_table(db, schema_name, table_name)
            return self._insert_remote_project_record(
                db,
                dict(payload),
                schema_name,
                table_name,
                source_filename,
            )
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    _ignore_optional_cleanup_error()
            db = None
            db_or_error = None
            try:
                QSqlDatabase.removeDatabase(conn_name)
            except Exception:
                _ignore_optional_cleanup_error()

    def _is_cancel_requested(self) -> bool:
        callback = self._cancel_requested
        if callback is None:
            return False
        try:
            return bool(callback())
        except Exception:
            return False

    def _open_postgres_database(self, conn_name: str):
        available_drivers = set(QSqlDatabase.drivers())
        if "QPSQL" not in available_drivers:
            return False, _rt("Driver PostgreSQL (QPSQL) nao esta disponivel nesta instalacao.")
        db = QSqlDatabase.addDatabase("QPSQL", conn_name)
        meta = self.connection_meta
        service = str(meta.get("service") or "").strip()
        if service:
            db.setDatabaseName(service)
        else:
            db.setHostName(str(meta.get("host") or ""))
            try:
                db.setPort(int(meta.get("port") or 5432))
            except (TypeError, ValueError):
                db.setPort(5432)
            db.setDatabaseName(str(meta.get("database") or ""))
        db.setUserName(str(meta.get("user") or ""))
        db.setPassword(str(meta.get("password") or ""))
        ssl_mode = str(meta.get("ssl_mode") or meta.get("sslmode") or "").strip()
        if ssl_mode:
            db.setConnectOptions(f"sslmode={ssl_mode}")
        if not db.open():
            return False, _safe_error_text(db)
        return True, db

    def _load_postgres_records(self, db) -> List[RemoteProjectRecord]:
        column_rows = self._query_postgres_candidate_columns(db)
        candidates = postgres_candidate_tables_from_column_rows(column_rows)
        records: List[RemoteProjectRecord] = []
        edit_permissions: Dict[tuple[str, str], bool] = {}
        seen = set()
        for table_info in candidates:
            if self._is_cancel_requested():
                break
            if len(records) >= self.limit:
                break
            permission_key = (str(table_info.schema or ""), str(table_info.table or ""))
            if permission_key not in edit_permissions:
                edit_permissions[permission_key] = self._can_update_remote_project_table(
                    db,
                    table_info.schema,
                    table_info.table,
                )
            can_edit_table = bool(edit_permissions.get(permission_key))
            for payload_column in table_info.payload_columns():
                if self._is_cancel_requested():
                    break
                if len(records) >= self.limit:
                    break
                for row in self._query_postgres_project_rows(db, table_info, payload_column):
                    if self._is_cancel_requested():
                        break
                    record = remote_project_record_from_row(
                        payload_value=_row_value(row, "payload", 0),
                        connection_meta=self.connection_meta,
                        schema=table_info.schema,
                        table=table_info.table,
                        row_id=_row_value(row, "row_id", 3),
                        name_value=_row_value(row, "name", 1),
                        updated_at_value=_row_value(row, "updated_at", 2),
                        source_file_value=_row_value(row, "source_file", 4),
                        can_edit=can_edit_table,
                    )
                    if record is None or record.source_id in seen:
                        continue
                    seen.add(record.source_id)
                    records.append(record)
                    if len(records) >= self.limit:
                        break
        return records

    def _ensure_remote_project_table(self, db, schema: str, table: str) -> None:
        schema_name = _validate_pg_identifier(str(schema or "public").strip() or "public")
        table_name = _validate_pg_identifier(str(table or DEFAULT_REMOTE_PROJECT_TABLE).strip() or DEFAULT_REMOTE_PROJECT_TABLE)
        if self._remote_project_table_exists(db, schema_name, table_name):
            return
        if not self._can_create_remote_project_schema(db, schema_name):
            raise RuntimeError(
                _rt("Usuario sem permissao CREATE no esquema {schema}.", schema=schema_name)
            )
        qualified_table = _qualified_pg_identifier(schema_name, table_name)
        sql = (
            f"CREATE TABLE IF NOT EXISTS {qualified_table} ("
            "id text PRIMARY KEY, "
            "project_id text NOT NULL, "
            "name text NOT NULL, "
            "payload jsonb NOT NULL, "
            "source_file text, "
            "format text NOT NULL DEFAULT 'pbsdash', "
            "created_at timestamptz NOT NULL DEFAULT now(), "
            "updated_at timestamptz NOT NULL DEFAULT now()"
            ")"
        )
        query = QSqlQuery(db)
        if not query.exec_(sql):
            raise RuntimeError(_query_error_text(query))

    def _insert_remote_project_record(
        self,
        db,
        payload: Dict[str, Any],
        schema: str,
        table: str,
        source_file: str,
    ) -> RemoteProjectRecord:
        schema_name = _validate_pg_identifier(schema)
        table_name = _validate_pg_identifier(table)
        if not self._can_insert_remote_project_table(db, schema_name, table_name):
            raise RuntimeError(
                _rt("Usuario sem permissao INSERT na tabela {schema}.{table}.", schema=schema_name, table=table_name)
            )
        project_id, name, record_id, payload_text, source_filename = _remote_project_record_values(
            payload,
            source_file,
            record_id="",
        )
        qualified_table = _qualified_pg_identifier(schema_name, table_name)
        # SQL identifiers are validated and quoted; row values stay bound below.
        sql = (
            f"INSERT INTO {qualified_table} "  # nosec B608
            "(id, project_id, name, payload, source_file, format, updated_at) "
            "VALUES (?, ?, ?, CAST(? AS jsonb), ?, 'pbsdash', now()) "
            "ON CONFLICT (id) DO UPDATE SET "
            "project_id = EXCLUDED.project_id, "
            "name = EXCLUDED.name, "
            "payload = EXCLUDED.payload, "
            "source_file = EXCLUDED.source_file, "
            "format = EXCLUDED.format, "
            "updated_at = now()"
        )
        query = QSqlQuery(db)
        query.prepare(sql)
        query.addBindValue(record_id)
        query.addBindValue(project_id)
        query.addBindValue(name)
        query.addBindValue(payload_text)
        query.addBindValue(source_filename)
        if not query.exec_():
            raise RuntimeError(_query_error_text(query))
        record = remote_project_record_from_row(
            payload_value=payload_text,
            connection_meta=self.connection_meta,
            schema=schema_name,
            table=table_name,
            row_id=record_id,
            name_value=name,
            source_file_value=source_filename,
            can_edit=self._can_update_remote_project_table(db, schema_name, table_name),
        )
        if record is None:
            raise RuntimeError(_rt("Nao foi possivel preparar o painel salvo."))
        return record

    def _update_remote_project_record(
        self,
        db,
        payload: Dict[str, Any],
        schema: str,
        table: str,
        source_file: str,
        *,
        record_id: str,
    ) -> RemoteProjectRecord:
        schema_name = _validate_pg_identifier(schema)
        table_name = _validate_pg_identifier(table)
        record_id = str(record_id or "").strip()
        if not record_id:
            raise RuntimeError(_rt("Painel remoto sem identificador para atualizar."))
        if not self._can_update_remote_project_table(db, schema_name, table_name):
            raise RuntimeError(
                _rt("Usuario sem permissao UPDATE na tabela {schema}.{table}.", schema=schema_name, table=table_name)
            )
        project_id, name, record_id, payload_text, source_filename = _remote_project_record_values(
            payload,
            source_file,
            record_id=record_id,
        )
        qualified_table = _qualified_pg_identifier(schema_name, table_name)
        # SQL identifiers are validated and quoted; row values stay bound below.
        sql = (
            f"UPDATE {qualified_table} "  # nosec B608
            "SET project_id = ?, "
            "name = ?, "
            "payload = CAST(? AS jsonb), "
            "source_file = ?, "
            "format = 'pbsdash', "
            "updated_at = now() "
            "WHERE id = ?"
        )
        query = QSqlQuery(db)
        query.prepare(sql)
        query.addBindValue(project_id)
        query.addBindValue(name)
        query.addBindValue(payload_text)
        query.addBindValue(source_filename)
        query.addBindValue(record_id)
        if not query.exec_():
            raise RuntimeError(_query_error_text(query))
        try:
            rows_affected = int(query.numRowsAffected())
        except Exception:
            rows_affected = -1
        if rows_affected == 0:
            raise RuntimeError(
                _rt("Painel remoto nao encontrado para atualizar: {row_id}.", row_id=record_id)
            )
        record = remote_project_record_from_row(
            payload_value=payload_text,
            connection_meta=self.connection_meta,
            schema=schema_name,
            table=table_name,
            row_id=record_id,
            name_value=name,
            source_file_value=source_filename,
            can_edit=True,
        )
        if record is None:
            raise RuntimeError(_rt("Nao foi possivel preparar o painel salvo."))
        return record

    def _can_update_remote_project_table(self, db, schema: str, table: str) -> bool:
        relation = _qualified_pg_identifier(schema, table)
        if not relation or QSqlQuery is None:
            return False
        query = QSqlQuery(db)
        query.prepare("SELECT COALESCE(has_table_privilege(current_user, ?, 'UPDATE'), false)")
        query.addBindValue(relation)
        if not query.exec_() or not query.next():
            return False
        return _truthy_sql_value(query.value(0))

    def _can_insert_remote_project_table(self, db, schema: str, table: str) -> bool:
        relation = _qualified_pg_identifier(schema, table)
        if not relation or QSqlQuery is None:
            return False
        query = QSqlQuery(db)
        query.prepare("SELECT COALESCE(has_table_privilege(current_user, ?, 'INSERT'), false)")
        query.addBindValue(relation)
        if not query.exec_() or not query.next():
            return False
        return _truthy_sql_value(query.value(0))

    def _can_create_remote_project_schema(self, db, schema: str) -> bool:
        schema_name = _validate_pg_identifier(schema)
        query = QSqlQuery(db)
        query.prepare("SELECT COALESCE(has_schema_privilege(current_user, ?, 'CREATE'), false)")
        query.addBindValue(schema_name)
        if not query.exec_() or not query.next():
            return False
        return _truthy_sql_value(query.value(0))

    def _remote_project_table_exists(self, db, schema: str, table: str) -> bool:
        schema_name = _validate_pg_identifier(schema)
        table_name = _validate_pg_identifier(table)
        query = QSqlQuery(db)
        query.prepare(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name = ? LIMIT 1"
        )
        query.addBindValue(schema_name)
        query.addBindValue(table_name)
        return bool(query.exec_() and query.next())

    def _query_postgres_candidate_columns(self, db) -> List[Dict[str, Any]]:
        query = QSqlQuery(db)
        # Static metadata query; the limit is a local constant.
        sql = (
            "SELECT table_schema, table_name, column_name, data_type "  # nosec B608
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
            "AND ("
            "  lower(table_name) LIKE '%pbsdash%' "
            "  OR lower(table_name) LIKE '%summarizer%' "
            "  OR lower(table_name) LIKE '%dashboard%' "
            "  OR lower(table_name) LIKE '%painel%' "
            "  OR lower(table_name) LIKE '%project%' "
            "  OR lower(table_name) LIKE '%projeto%' "
            ") "
            "ORDER BY CASE WHEN lower(table_name) = 'summarizer_model_projects' THEN 0 ELSE 1 END, "
            "table_schema, table_name, ordinal_position "
            f"LIMIT {_SCAN_TABLE_LIMIT * 16}"
        )
        if not query.exec_(sql):
            return []
        rows: List[Dict[str, Any]] = []
        while query.next():
            rows.append(
                {
                    "table_schema": str(query.value(0) or ""),
                    "table_name": str(query.value(1) or ""),
                    "column_name": str(query.value(2) or ""),
                    "data_type": str(query.value(3) or ""),
                }
            )
        return rows

    def _query_postgres_project_rows(
        self,
        db,
        table_info: _PostgresCandidateTable,
        payload_column: _PostgresColumnInfo,
    ) -> List[Dict[str, Any]]:
        name_column = table_info.column_by_hints(_NAME_COLUMN_HINTS)
        updated_column = table_info.column_by_hints(_UPDATED_COLUMN_HINTS)
        id_column = table_info.column_by_hints(_ID_COLUMN_HINTS)
        format_column = table_info.column_by_hints(_FORMAT_COLUMN_HINTS)
        source_file_column = table_info.column_by_hints(_SOURCE_FILE_COLUMN_HINTS)

        payload_expr = f"{_quote_pg_identifier(payload_column.name)}::text AS payload"
        name_expr = (
            f"{_quote_pg_identifier(name_column.name)}::text AS name"
            if name_column is not None
            else "''::text AS name"
        )
        updated_expr = (
            f"{_quote_pg_identifier(updated_column.name)}::text AS updated_at"
            if updated_column is not None
            else "''::text AS updated_at"
        )
        id_expr = (
            f"{_quote_pg_identifier(id_column.name)}::text AS row_id"
            if id_column is not None
            else "''::text AS row_id"
        )
        source_file_expr = (
            f"{_quote_pg_identifier(source_file_column.name)}::text AS source_file"
            if source_file_column is not None
            else "''::text AS source_file"
        )
        where_parts = [f"{_quote_pg_identifier(payload_column.name)} IS NOT NULL"]
        if format_column is not None:
            format_expr = f"lower({_quote_pg_identifier(format_column.name)}::text)"
            where_parts.append(f"({format_expr} = 'pbsdash' OR {format_expr} LIKE '%.pbsdash')")
        order_expr = f" ORDER BY {_quote_pg_identifier(updated_column.name)} DESC" if updated_column else ""
        qualified_table = _qualified_pg_identifier(table_info.schema, table_info.table)
        # SQL identifiers are validated and quoted; row values stay bound below.
        sql = (
            f"SELECT {payload_expr}, {name_expr}, {updated_expr}, {id_expr}, {source_file_expr} "  # nosec B608
            f"FROM {qualified_table} "
            f"WHERE {' AND '.join(where_parts)}"
            f"{order_expr} "
            f"LIMIT {_SCAN_ROWS_PER_PAYLOAD_COLUMN}"
        )
        query = QSqlQuery(db)
        if not query.exec_(sql):
            return []
        rows: List[Dict[str, Any]] = []
        while query.next():
            rows.append(
                {
                    "payload": query.value(0),
                    "name": query.value(1),
                    "updated_at": query.value(2),
                    "row_id": query.value(3),
                    "source_file": query.value(4),
                }
            )
        return rows


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:
            return {}
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, "")
    try:
        return row[index]
    except Exception:
        return ""


def _remote_project_table_sort_key(table_info: _PostgresCandidateTable) -> tuple[int, str, str]:
    table_name = str(table_info.table or "").strip().lower()
    default_rank = 0 if table_name == DEFAULT_REMOTE_PROJECT_TABLE else 1
    return default_rank, str(table_info.schema or "").lower(), table_name


def _remote_project_record_values(
    payload: Mapping[str, Any],
    source_file: str,
    *,
    record_id: str = "",
) -> tuple[str, str, str, str, str]:
    source_filename = safe_source_filename(source_file)
    project_id = str(payload.get("project_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    record_id = str(record_id or "").strip()
    if not project_id:
        project_id = record_id or os.path.splitext(source_filename)[0] or name
    if not record_id:
        record_id = project_id
    if not name:
        name = os.path.splitext(source_filename)[0] or project_id or _rt("Painel remoto")
    payload_text = json.dumps(dict(payload), ensure_ascii=False)
    return project_id, name, record_id, payload_text, source_filename


def _validate_pg_identifier(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(_rt("Identificador PostgreSQL vazio."))
    if ";" in text or "--" in text or "/*" in text or "*/" in text:
        raise ValueError(_rt("Identificador PostgreSQL invalido: {value}", value=text))
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError(_rt("Identificador PostgreSQL invalido: {value}", value=repr(text)))
    if not _PG_IDENTIFIER_RE.match(text):
        raise ValueError(_rt("Identificador PostgreSQL invalido: {value}", value=text))
    return text


def _quote_pg_identifier(value: str) -> str:
    return '"{}"'.format(_validate_pg_identifier(value).replace('"', '""'))


def _qualified_pg_identifier(schema: str, table: str) -> str:
    table_name = _validate_pg_identifier(table)
    if not table_name:
        return ""
    schema_name = str(schema or "").strip()
    if not schema_name:
        return _quote_pg_identifier(table_name)
    return f"{_quote_pg_identifier(schema_name)}.{_quote_pg_identifier(table_name)}"


def _truthy_sql_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _safe_error_text(db) -> str:
    try:
        return str(db.lastError().text() or "").strip() or _rt("Falha ao abrir a conexao.")
    except Exception:
        return _rt("Falha ao abrir a conexao.")


def _query_error_text(query) -> str:
    try:
        return str(query.lastError().text() or "").strip() or _rt("Falha ao executar SQL.")
    except Exception:
        return _rt("Falha ao executar SQL.")


def _ignore_optional_cleanup_error() -> None:
    """Keep cleanup best-effort without hiding active operation errors."""
    return None


__all__ = [
    "ModelRemoteProjectService",
    "DEFAULT_REMOTE_PROJECT_TABLE",
    "REMOTE_PROJECT_LIMIT",
    "RemoteProjectRecord",
    "RemoteProjectScanResult",
    "connection_key",
    "connection_label",
    "is_pbsdash_payload",
    "is_remote_project_table_name",
    "is_supported_remote_project_driver",
    "normalize_remote_project_table_target",
    "postgres_candidate_tables_from_column_rows",
    "project_payload_from_file",
    "project_payload_from_value",
    "remote_project_record_from_row",
    "safe_source_filename",
]
