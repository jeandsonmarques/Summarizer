from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ReportStyleContext:
    values: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        return dict(self.values)

    def asdict(self) -> Dict[str, str]:
        return self.to_dict()


@dataclass(frozen=True)
class ReportPreviewRow:
    category: str
    value_text: str
    percent_text: str = ""


@dataclass(frozen=True)
class ReportPreviewModel:
    helper_text: str
    rows: List[ReportPreviewRow] = field(default_factory=list)
    value_label: str = ""
    show_percent: bool = False


@dataclass(frozen=True)
class ReportExportBundle:
    headers: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    helper_text: str = ""
    value_label: str = ""

