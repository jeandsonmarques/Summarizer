from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryHistoryRecord:
    id: Optional[int] = None
    created_utc: str = ""
    user_id: str = ""
    session_id: str = ""
    raw_query: str = ""
    normalized_query: str = ""
    intent: str = ""
    metric: str = ""
    entity: str = ""
    filters_json: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses_json: List[Dict[str, Any]] = field(default_factory=list)
    chosen_hypothesis_json: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    execution_payload_json: Dict[str, Any] = field(default_factory=dict)
    execution_result_summary: str = ""
    success_flag: Optional[bool] = None
    error_message: str = ""
    duration_ms: int = 0
    source_context_json: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryFeedbackRecord:
    id: Optional[int] = None
    query_history_id: int = 0
    created_utc: str = ""
    feedback_type: str = ""
    corrected_intent: str = ""
    corrected_metric: str = ""
    corrected_entity: str = ""
    corrected_filters_json: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    user_action_json: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticAliasRecord:
    id: Optional[int] = None
    created_utc: str = ""
    alias_term: str = ""
    canonical_term: str = ""
    alias_type: str = ""
    weight: float = 1.0
    active: bool = True
    source: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovedExampleRecord:
    id: Optional[int] = None
    created_utc: str = ""
    example_query: str = ""
    normalized_query: str = ""
    intent: str = ""
    metric: str = ""
    entity: str = ""
    filters_json: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    success_weight: float = 1.0
    last_used_utc: str = ""
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimilarQueryMatch:
    query_history_id: int
    raw_query: str
    normalized_query: str
    intent: str = ""
    metric: str = ""
    entity: str = ""
    filters_json: List[Dict[str, Any]] = field(default_factory=list)
    execution_result_summary: str = ""
    success_flag: Optional[bool] = None
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryHistoryHandle:
    history_id: Optional[int]
    session_id: str
    raw_query: str
    normalized_query: str
    source_context_json: Dict[str, Any] = field(default_factory=dict)
    started_perf: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
