from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ChartVisualState:
    chart_type: str = "bar"
    palette: str = "purple"
    font_scale: float = 1.0
    show_legend: bool = False
    show_values: bool = True
    show_percent: bool = False
    show_grid: bool = False
    show_border: bool = False
    sort_mode: str = "default"
    bar_corner_style: str = "square"
    title_override: str = ""
    legend_label_override: str = ""
    legend_item_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class ChartDataProfile:
    count: int = 0
    unique_category_count: int = 0
    positive_count: int = 0
    nonzero_count: int = 0
    has_positive: bool = False
    has_negative: bool = False
    truncated: bool = False
    sequential_hint: bool = False
