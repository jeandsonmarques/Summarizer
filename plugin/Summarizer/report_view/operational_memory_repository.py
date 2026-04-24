from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .operational_memory_models import (
    ApprovedExampleRecord,
    QueryFeedbackRecord,
    QueryHistoryRecord,
    SemanticAliasRecord,
)
from .operational_memory_store import OperationalMemoryStore


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_loads(payload: Any, fallback):
    if payload in (None, ""):
        return fallback
    try:
        return json.loads(payload)
    except Exception:
        return fallback


QUERY_HISTORY_MUTABLE_COLUMNS = {
    "user_id",
    "session_id",
    "raw_query",
    "normalized_query",
    "intent",
    "metric",
    "entity",
    "filters_json",
    "hypotheses_json",
    "chosen_hypothesis_json",
    "confidence",
    "execution_payload_json",
    "execution_result_summary",
    "success_flag",
    "error_message",
    "duration_ms",
    "source_context_json",
}


class IQueryMemoryRepository(ABC):
    @abstractmethod
    def create(self, record: QueryHistoryRecord) -> QueryHistoryRecord:
        raise NotImplementedError

    @abstractmethod
    def update(self, query_history_id: int, changes: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, query_history_id: int) -> Optional[QueryHistoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_recent_by_session(self, session_id: str, limit: int = 10) -> List[QueryHistoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self, limit: int = 200) -> List[QueryHistoryRecord]:
        raise NotImplementedError


class IFeedbackRepository(ABC):
    @abstractmethod
    def create(self, record: QueryFeedbackRecord) -> QueryFeedbackRecord:
        raise NotImplementedError

    @abstractmethod
    def list_by_query(self, query_history_id: int) -> List[QueryFeedbackRecord]:
        raise NotImplementedError


class ISemanticAliasRepository(ABC):
    @abstractmethod
    def upsert(self, record: SemanticAliasRecord) -> SemanticAliasRecord:
        raise NotImplementedError

    @abstractmethod
    def list_active(self, alias_type: str = "", limit: int = 200) -> List[SemanticAliasRecord]:
        raise NotImplementedError


class IApprovedExampleRepository(ABC):
    @abstractmethod
    def create(self, record: ApprovedExampleRecord) -> ApprovedExampleRecord:
        raise NotImplementedError

    @abstractmethod
    def list_active(self, limit: int = 200) -> List[ApprovedExampleRecord]:
        raise NotImplementedError

    @abstractmethod
    def touch(self, example_id: int, last_used_utc: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, example_id: int, last_used_utc: str, success_weight: float) -> None:
        raise NotImplementedError


class QueryMemoryRepository(IQueryMemoryRepository):
    def __init__(self, store: OperationalMemoryStore):
        self.store = store

    def create(self, record: QueryHistoryRecord) -> QueryHistoryRecord:
        with self.store.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_history (
                    created_utc, user_id, session_id, raw_query, normalized_query,
                    intent, metric, entity, filters_json, hypotheses_json,
                    chosen_hypothesis_json, confidence, execution_payload_json,
                    execution_result_summary, success_flag, error_message,
                    duration_ms, source_context_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.created_utc,
                    record.user_id,
                    record.session_id,
                    record.raw_query,
                    record.normalized_query,
                    record.intent,
                    record.metric,
                    record.entity,
                    _json_dumps(record.filters_json or []),
                    _json_dumps(record.hypotheses_json or []),
                    _json_dumps(record.chosen_hypothesis_json or {}),
                    float(record.confidence or 0.0),
                    _json_dumps(record.execution_payload_json or {}),
                    record.execution_result_summary,
                    None if record.success_flag is None else int(bool(record.success_flag)),
                    record.error_message,
                    int(record.duration_ms or 0),
                    _json_dumps(record.source_context_json or {}),
                ),
            )
            record.id = int(cursor.lastrowid)
        return record

    def update(self, query_history_id: int, changes: Dict[str, Any]) -> None:
        if not query_history_id or not changes:
            return
        encoded = {}
        for key, value in changes.items():
            if key not in QUERY_HISTORY_MUTABLE_COLUMNS:
                continue
            if key in {"filters_json", "hypotheses_json", "chosen_hypothesis_json", "execution_payload_json", "source_context_json"}:
                encoded[key] = _json_dumps(value)
            elif key == "success_flag":
                encoded[key] = None if value is None else int(bool(value))
            elif key == "duration_ms":
                encoded[key] = int(value or 0)
            elif key == "confidence":
                encoded[key] = float(value or 0.0)
            else:
                encoded[key] = value
        if not encoded:
            return
        columns = ", ".join(f"{column} = ?" for column in encoded.keys())
        values = list(encoded.values()) + [int(query_history_id)]
        with self.store.connection() as connection:
            # Dynamic columns are restricted to QUERY_HISTORY_MUTABLE_COLUMNS above.
            connection.execute(
                f"UPDATE query_history SET {columns} WHERE id = ?",  # nosec B608
                values,
            )

    def get_by_id(self, query_history_id: int) -> Optional[QueryHistoryRecord]:
        if not query_history_id:
            return None
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM query_history WHERE id = ?",
                (int(query_history_id),),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_recent_by_session(self, session_id: str, limit: int = 10) -> List[QueryHistoryRecord]:
        if not session_id:
            return []
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM query_history
                WHERE session_id = ?
                ORDER BY created_utc DESC, id DESC
                LIMIT ?
                """,
                (session_id, max(1, int(limit))),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_all(self, limit: int = 200) -> List[QueryHistoryRecord]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM query_history
                ORDER BY created_utc DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row) -> QueryHistoryRecord:
        return QueryHistoryRecord(
            id=int(row["id"]),
            created_utc=str(row["created_utc"] or ""),
            user_id=str(row["user_id"] or ""),
            session_id=str(row["session_id"] or ""),
            raw_query=str(row["raw_query"] or ""),
            normalized_query=str(row["normalized_query"] or ""),
            intent=str(row["intent"] or ""),
            metric=str(row["metric"] or ""),
            entity=str(row["entity"] or ""),
            filters_json=_json_loads(row["filters_json"], []),
            hypotheses_json=_json_loads(row["hypotheses_json"], []),
            chosen_hypothesis_json=_json_loads(row["chosen_hypothesis_json"], {}),
            confidence=float(row["confidence"] or 0.0),
            execution_payload_json=_json_loads(row["execution_payload_json"], {}),
            execution_result_summary=str(row["execution_result_summary"] or ""),
            success_flag=None if row["success_flag"] is None else bool(int(row["success_flag"])),
            error_message=str(row["error_message"] or ""),
            duration_ms=int(row["duration_ms"] or 0),
            source_context_json=_json_loads(row["source_context_json"], {}),
        )


class FeedbackRepository(IFeedbackRepository):
    def __init__(self, store: OperationalMemoryStore):
        self.store = store

    def create(self, record: QueryFeedbackRecord) -> QueryFeedbackRecord:
        with self.store.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_feedback (
                    query_history_id, created_utc, feedback_type, corrected_intent,
                    corrected_metric, corrected_entity, corrected_filters_json,
                    notes, user_action_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(record.query_history_id),
                    record.created_utc,
                    record.feedback_type,
                    record.corrected_intent,
                    record.corrected_metric,
                    record.corrected_entity,
                    _json_dumps(record.corrected_filters_json or []),
                    record.notes,
                    _json_dumps(record.user_action_json or {}),
                ),
            )
            record.id = int(cursor.lastrowid)
        return record

    def list_by_query(self, query_history_id: int) -> List[QueryFeedbackRecord]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM query_feedback
                WHERE query_history_id = ?
                ORDER BY created_utc DESC, id DESC
                """,
                (int(query_history_id),),
            ).fetchall()
        return [
            QueryFeedbackRecord(
                id=int(row["id"]),
                query_history_id=int(row["query_history_id"]),
                created_utc=str(row["created_utc"] or ""),
                feedback_type=str(row["feedback_type"] or ""),
                corrected_intent=str(row["corrected_intent"] or ""),
                corrected_metric=str(row["corrected_metric"] or ""),
                corrected_entity=str(row["corrected_entity"] or ""),
                corrected_filters_json=_json_loads(row["corrected_filters_json"], []),
                notes=str(row["notes"] or ""),
                user_action_json=_json_loads(row["user_action_json"], {}),
            )
            for row in rows
        ]


class SemanticAliasRepository(ISemanticAliasRepository):
    def __init__(self, store: OperationalMemoryStore):
        self.store = store

    def upsert(self, record: SemanticAliasRecord) -> SemanticAliasRecord:
        with self.store.connection() as connection:
            existing = connection.execute(
                """
                SELECT id FROM semantic_alias
                WHERE alias_term = ? AND canonical_term = ? AND alias_type = ?
                LIMIT 1
                """,
                (record.alias_term, record.canonical_term, record.alias_type),
            ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO semantic_alias (
                        created_utc, alias_term, canonical_term, alias_type,
                        weight, active, source, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.created_utc,
                        record.alias_term,
                        record.canonical_term,
                        record.alias_type,
                        float(record.weight or 1.0),
                        int(bool(record.active)),
                        record.source,
                        record.notes,
                    ),
                )
                record.id = int(cursor.lastrowid)
            else:
                record.id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE semantic_alias
                    SET weight = ?, active = ?, source = ?, notes = ?
                    WHERE id = ?
                    """,
                    (
                        float(record.weight or 1.0),
                        int(bool(record.active)),
                        record.source,
                        record.notes,
                        record.id,
                    ),
                )
        return record

    def list_active(self, alias_type: str = "", limit: int = 200) -> List[SemanticAliasRecord]:
        query = """
            SELECT * FROM semantic_alias
            WHERE active = 1
        """
        params: List[Any] = []
        if alias_type:
            query += " AND alias_type = ?"
            params.append(alias_type)
        query += " ORDER BY weight DESC, alias_term ASC LIMIT ?"
        params.append(max(1, int(limit)))
        with self.store.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            SemanticAliasRecord(
                id=int(row["id"]),
                created_utc=str(row["created_utc"] or ""),
                alias_term=str(row["alias_term"] or ""),
                canonical_term=str(row["canonical_term"] or ""),
                alias_type=str(row["alias_type"] or ""),
                weight=float(row["weight"] or 1.0),
                active=bool(int(row["active"] or 0)),
                source=str(row["source"] or ""),
                notes=str(row["notes"] or ""),
            )
            for row in rows
        ]


class ApprovedExampleRepository(IApprovedExampleRepository):
    def __init__(self, store: OperationalMemoryStore):
        self.store = store

    def create(self, record: ApprovedExampleRecord) -> ApprovedExampleRecord:
        with self.store.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approved_examples (
                    created_utc, example_query, normalized_query, intent,
                    metric, entity, filters_json, notes, success_weight,
                    last_used_utc, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.created_utc,
                    record.example_query,
                    record.normalized_query,
                    record.intent,
                    record.metric,
                    record.entity,
                    _json_dumps(record.filters_json or []),
                    record.notes,
                    float(record.success_weight or 1.0),
                    record.last_used_utc,
                    int(bool(record.active)),
                ),
            )
            record.id = int(cursor.lastrowid)
        return record

    def list_active(self, limit: int = 200) -> List[ApprovedExampleRecord]:
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM approved_examples
                WHERE active = 1
                ORDER BY success_weight DESC, last_used_utc DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            ApprovedExampleRecord(
                id=int(row["id"]),
                created_utc=str(row["created_utc"] or ""),
                example_query=str(row["example_query"] or ""),
                normalized_query=str(row["normalized_query"] or ""),
                intent=str(row["intent"] or ""),
                metric=str(row["metric"] or ""),
                entity=str(row["entity"] or ""),
                filters_json=_json_loads(row["filters_json"], []),
                notes=str(row["notes"] or ""),
                success_weight=float(row["success_weight"] or 1.0),
                last_used_utc=str(row["last_used_utc"] or ""),
                active=bool(int(row["active"] or 0)),
            )
            for row in rows
        ]

    def touch(self, example_id: int, last_used_utc: str) -> None:
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE approved_examples SET last_used_utc = ? WHERE id = ?",
                (last_used_utc, int(example_id)),
            )

    def update(self, example_id: int, last_used_utc: str, success_weight: float) -> None:
        with self.store.connection() as connection:
            connection.execute(
                """
                UPDATE approved_examples
                SET last_used_utc = ?, success_weight = ?
                WHERE id = ?
                """,
                (last_used_utc, float(success_weight or 0.0), int(example_id)),
            )
