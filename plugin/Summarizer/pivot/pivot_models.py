from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class PivotFieldResolution:
    requested: str = ""
    resolved: str = ""
    fallback_candidates: Tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PivotExportSpec:
    file_path: str
    include_totals: bool = True
    include_percentages: bool = True
    sheet_name: str = "Pivot"
    data_sheet_name: str = "Dados_Camada"
    pivot_sheet_name: str = "Tabela_Dinamica"
    metadata: Dict[str, Any] = field(default_factory=dict)
    extra_fields: List[str] = field(default_factory=list)
    layer_name: str = "tabela_dinamica"
    aggregation: str = "count"
    value_field: str = ""
    value_label: str = ""
    row_fields: List[str] = field(default_factory=list)
    column_fields: List[str] = field(default_factory=list)
    filter_fields: List[str] = field(default_factory=list)
