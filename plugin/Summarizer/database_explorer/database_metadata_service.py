# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Dict, List, Optional

from qgis.core import (
    QgsAbstractDatabaseProviderConnection,
    QgsDataSourceUri,
    QgsProviderRegistry,
)
try:  # pragma: no cover - QtSql availability depends on the QGIS install
    from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery
except Exception:  # pragma: no cover
    QSqlDatabase = None
    QSqlQuery = None

from ..utils.i18n_runtime import tr_text as _rt
from .database_models import DatabaseConnectionSnapshot, DatabaseGroup, DatabaseObject


SUPPORTED_DATABASE_DRIVERS = {
    "postgres",
    "postgresql",
    "postgis",
    "sql server",
    "mssql",
}


def provider_key_for_driver(driver: str) -> Optional[str]:
    normalized = (driver or "").strip().lower()
    if normalized in ("postgres", "postgresql", "postgis"):
        return "postgres"
    if normalized in ("sql server", "mssql"):
        return "mssql"
    return None


def is_supported_driver(driver: str) -> bool:
    return (driver or "").strip().lower() in SUPPORTED_DATABASE_DRIVERS


class DatabaseMetadataService:
    """Loads database schemas and table-like objects through QGIS providers."""

    def __init__(self, connection_meta: Dict, object_limit: int = 0):
        self.connection_meta = dict(connection_meta or {})
        self.provider_key = provider_key_for_driver(str(self.connection_meta.get("driver") or ""))
        self.object_limit = max(0, int(object_limit or 0))

    def load_snapshot(self) -> DatabaseConnectionSnapshot:
        if not self.provider_key:
            return self._snapshot(False, _rt("Provedor nao suportado para esta conexao."))

        if self.provider_key == "postgres":
            snapshot = self._load_postgres_snapshot()
            if snapshot is not None:
                return snapshot

        metadata = QgsProviderRegistry.instance().providerMetadata(self.provider_key)
        if metadata is None:
            return self._snapshot(
                False,
                _rt("Provedor '{provider}' nao encontrado.", provider=self.provider_key),
            )

        uri = self.build_connection_uri(self.connection_meta)
        if uri is None:
            return self._snapshot(False, _rt("Parametros da conexao incompletos."))

        try:
            connection = metadata.createConnection(uri.connectionInfo(), {})
        except Exception as exc:  # pragma: no cover - provider specific
            return self._snapshot(False, self._safe_error(exc))

        if not isinstance(connection, QgsAbstractDatabaseProviderConnection):
            return self._snapshot(False, _rt("Provedor nao suporta navegacao no navegador."))

        try:
            grouped = self._load_grouped_objects(connection)
        except Exception as exc:  # pragma: no cover - driver specific
            return self._snapshot(False, self._safe_error(exc))

        groups = [
            DatabaseGroup(name=schema, objects=sorted(objects, key=lambda obj: obj.name.lower()))
            for schema, objects in sorted(grouped.items(), key=lambda item: item[0].lower())
        ]
        return DatabaseConnectionSnapshot(
            connection_meta=self._public_connection_meta(),
            provider_key=self.provider_key,
            groups=groups,
            connected=True,
            error_message="",
        )

    def _load_postgres_snapshot(self) -> Optional[DatabaseConnectionSnapshot]:
        if QSqlDatabase is None or QSqlQuery is None:
            return None
        params = self.connection_meta
        database = str(params.get("database") or "").strip()
        user = str(params.get("user") or "").strip()
        if not database or not user:
            return self._snapshot(False, _rt("Parametros da conexao incompletos."))

        conn_name = f"summarizer_catalog_{id(self)}"
        db = QSqlDatabase.addDatabase("QPSQL", conn_name)
        try:
            error = self._configure_postgres_database(db)
            if error:
                return self._snapshot(False, error)
            if not db.open():
                return self._snapshot(False, self._safe_text(db.lastError().text()))
            return self._query_postgres_catalog(db)
        finally:
            try:
                db.close()
            except Exception:
                pass
            db = None
            QSqlDatabase.removeDatabase(conn_name)

    def _configure_postgres_database(self, db) -> str:
        params = self.connection_meta
        database = str(params.get("database") or "").strip()
        user = str(params.get("user") or "").strip()
        if not database or not user:
            return _rt("Parametros da conexao incompletos.")

        service = str(params.get("service") or "").strip()
        if service:
            db.setDatabaseName(service)
        else:
            db.setHostName(str(params.get("host") or ""))
            try:
                db.setPort(int(params.get("port") or 5432))
            except (TypeError, ValueError):
                db.setPort(5432)
            db.setDatabaseName(database)
        db.setUserName(user)
        db.setPassword(str(params.get("password") or ""))
        ssl_mode = str(params.get("ssl_mode") or params.get("sslmode") or "").strip()
        if ssl_mode:
            db.setConnectOptions(f"sslmode={ssl_mode}")
        return ""

    def _query_postgres_catalog(self, db) -> DatabaseConnectionSnapshot:
        query = QSqlQuery(db)
        sql = (
            "SELECT n.nspname AS table_schema, "
            "       c.relname AS table_name, "
            "       CASE c.relkind "
            "           WHEN 'r' THEN 'BASE TABLE' "
            "           WHEN 'p' THEN 'PARTITIONED TABLE' "
            "           WHEN 'v' THEN 'VIEW' "
            "           WHEN 'm' THEN 'MATERIALIZED VIEW' "
            "           WHEN 'f' THEN 'FOREIGN TABLE' "
            "           ELSE 'TABLE' "
            "       END AS table_type, "
            "       COALESCE(g.geometry_column, '') AS geometry_column "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "LEFT JOIN LATERAL ("
            "    SELECT a.attname AS geometry_column "
            "    FROM pg_attribute a "
            "    JOIN pg_type t ON t.oid = a.atttypid "
            "    WHERE a.attrelid = c.oid "
            "      AND a.attnum > 0 "
            "      AND NOT a.attisdropped "
            "      AND t.typname IN ('geometry', 'geography') "
            "    ORDER BY a.attnum "
            "    LIMIT 1"
            ") g ON true "
            "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
            "  AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "ORDER BY table_schema, table_name"
        )
        if self.object_limit > 0:
            sql += f" LIMIT {int(self.object_limit)}"
        if not query.exec(sql):
            return self._snapshot(False, self._safe_text(query.lastError().text()))

        grouped: Dict[str, List[DatabaseObject]] = {}
        while query.next():
            schema = str(query.value(0) or "")
            name = str(query.value(1) or "")
            table_type = str(query.value(2) or "").upper()
            geometry_column = str(query.value(3) or "")
            obj = DatabaseObject(
                schema=schema,
                name=name,
                object_type=self._postgres_object_type(table_type, geometry_column),
                geometry_column=geometry_column,
                comment="",
                is_vector=bool(geometry_column),
                provider_key=self.provider_key or "",
            )
            if self._can_embed_object_uri():
                obj.uri = self.build_object_uri(self.connection_meta, obj)
            grouped.setdefault(schema, []).append(obj)

        groups = [
            DatabaseGroup(name=schema, objects=objects)
            for schema, objects in sorted(grouped.items(), key=lambda item: item[0].lower())
        ]
        return DatabaseConnectionSnapshot(
            connection_meta=self._public_connection_meta(),
            provider_key=self.provider_key or "",
            groups=groups,
            connected=True,
            error_message="",
        )

    def _postgres_object_type(self, table_type: str, geometry_column: str) -> str:
        if geometry_column:
            return "vector"
        if table_type == "VIEW":
            return "view"
        return "table"

    def _load_grouped_objects(self, connection: QgsAbstractDatabaseProviderConnection) -> Dict[str, List[DatabaseObject]]:
        grouped: Dict[str, List[DatabaseObject]] = {}
        for table in connection.tables():
            schema = str(table.schema() or "")
            obj = DatabaseObject(
                schema=schema,
                name=str(table.tableName() or ""),
                object_type=self._object_type(table),
                geometry_column=str(table.geometryColumn() or ""),
                comment=str(table.comment() or ""),
                is_vector=bool(table.geometryColumn()),
                provider_key=self.provider_key or "",
            )
            if self._can_embed_object_uri():
                obj.uri = self.build_object_uri(self.connection_meta, obj)
            grouped.setdefault(schema, []).append(obj)
        return grouped

    def _object_type(self, table) -> str:
        flags = self._table_object_flags(table)
        table_flag = QgsAbstractDatabaseProviderConnection.TableFlag
        candidates = (
            ("Raster", "raster"),
            ("MaterializedView", "materialized_view"),
            ("View", "view"),
            ("Vector", "vector"),
        )
        for flag_name, object_type in candidates:
            flag_value = getattr(table_flag, flag_name, None)
            if flag_value is not None and flags & int(flag_value):
                return object_type
        if table.geometryColumn():
            return "vector"
        return "table"

    def _table_object_flags(self, table) -> int:
        flags_getter = getattr(table, "flags", None)
        if callable(flags_getter):
            try:
                return int(flags_getter())
            except Exception:
                return 0
        return 0

    def _snapshot(self, connected: bool, error_message: str = "") -> DatabaseConnectionSnapshot:
        return DatabaseConnectionSnapshot(
            connection_meta=self._public_connection_meta(),
            provider_key=self.provider_key or "",
            groups=[],
            connected=connected,
            error_message=error_message,
        )

    def _public_connection_meta(self) -> Dict:
        public = dict(self.connection_meta)
        if "password" in public:
            public["password"] = ""
        return public

    def _can_embed_object_uri(self) -> bool:
        return not bool(self.connection_meta.get("password"))

    def _safe_error(self, exc: Exception) -> str:
        return self._safe_text(str(exc or "").strip())

    def _safe_text(self, message: str) -> str:
        message = str(message or "").strip()
        password = str(self.connection_meta.get("password") or "")
        if password and password in message:
            message = message.replace(password, "********")
        return message or _rt("Falha ao ler metadados da conexao.")

    @staticmethod
    def build_connection_uri(connection_meta: Dict) -> Optional[QgsDataSourceUri]:
        host = connection_meta.get("host")
        database = connection_meta.get("database")
        user = connection_meta.get("user")
        password = connection_meta.get("password", "")
        service = connection_meta.get("service")
        if not database or not user:
            return None

        uri = QgsDataSourceUri()
        if service:
            uri.setConnection(service, database, user, password)
        else:
            uri.setConnection(host or "", str(connection_meta.get("port") or ""), database, user, password)
        authcfg = connection_meta.get("authcfg")
        if authcfg:
            uri.setAuthConfigId(authcfg)
        return uri

    @staticmethod
    def build_object_uri(connection_meta: Dict, database_object: DatabaseObject) -> str:
        uri = DatabaseMetadataService.build_connection_uri(connection_meta)
        if uri is None:
            return ""
        schema = database_object.schema or ""
        table_name = database_object.name or ""
        if schema and table_name:
            provider_key = str(database_object.provider_key or provider_key_for_driver(str(connection_meta.get("driver") or "")) or "")
            try:
                metadata = QgsProviderRegistry.instance().providerMetadata(provider_key)
            except Exception:
                metadata = None
            if metadata is not None:
                try:
                    connection = metadata.createConnection(uri.connectionInfo(), {})
                except Exception:
                    connection = None
                if connection is not None:
                    table_uri_getter = getattr(connection, "tableUri", None)
                    if callable(table_uri_getter):
                        try:
                            table_uri = str(table_uri_getter(schema, table_name) or "")
                            if table_uri:
                                return table_uri
                        except Exception:
                            pass
        uri.setDataSource(
            schema,
            table_name,
            database_object.geometry_column or "",
        )
        return uri.uri()
