from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PivotFieldSpec:
    field_name: str
    display_name: str
    source_type: str  # "attribute" | "geometry"
    geometry_op: Optional[str] = None  # "length" | "area" | None
    data_type: Optional[str] = None  # "text" | "numeric" | "date" | "bool"


@dataclass
class PivotRequest:
    layer_id: str
    filter_expression: str = ""
    row_fields: List[PivotFieldSpec] = field(default_factory=list)
    column_fields: List[PivotFieldSpec] = field(default_factory=list)
    value_field: Optional[PivotFieldSpec] = None
    aggregation: str = "count"
    only_selected: bool = False
    include_nulls: bool = False
    include_percentages: bool = True
    include_totals: bool = True


@dataclass
class PivotCell:
    raw_value: Any = None
    display_value: str = ""
    feature_ids: List[int] = field(default_factory=list)
    percent_of_total: Optional[float] = None
    percent_of_row: Optional[float] = None
    percent_of_column: Optional[float] = None


@dataclass
class PivotResult:
    row_headers: List[Tuple[Any, ...]] = field(default_factory=list)
    column_headers: List[Tuple[Any, ...]] = field(default_factory=list)
    matrix: List[List[PivotCell]] = field(default_factory=list)
    grand_total: Optional[float] = None
    row_totals: Dict[Tuple[Any, ...], float] = field(default_factory=dict)
    column_totals: Dict[Tuple[Any, ...], float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PivotBucket:
    count: int = 0
    sum_value: float = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    values: List[Any] = field(default_factory=list)
    unique_values: set = field(default_factory=set)
    feature_ids: List[int] = field(default_factory=list)
