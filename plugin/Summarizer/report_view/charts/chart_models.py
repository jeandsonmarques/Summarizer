from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ChartVisualState:
    chart_type: str = "bar"
    palette: str = "purple"
    font_scale: float = 0.82
    show_legend: bool = False
    show_values: bool = True
    show_percent: bool = False
    show_grid: bool = False
    show_title: bool = True
    show_border: bool = False
    sort_mode: str = "default"
    bar_corner_style: str = "square"
    title_override: str = ""
    legend_label_override: str = ""
    legend_item_overrides: Dict[str, str] = field(default_factory=dict)
    show_background: bool = True
    background_color: str = "#FFFFFF"
    background_opacity: int = 100
    border_color: str = "#CBD5E1"
    border_width: int = 1
    border_radius: int = 8
    padding: int = 8
    shadow_enabled: bool = False
    shadow_opacity: int = 18
    grid_color: str = "#E5E7EB"
    grid_width: int = 1
    grid_opacity: int = 100
    show_axis_labels: bool = True
    axis_label_color: str = "#4B5563"
    axis_label_size: int = 0
    show_zero_line: bool = True
    zero_line_color: str = "#CBD5E1"
    title_color: str = "#1F2937"
    title_size: int = 0
    label_color: str = "#4B5563"
    label_size: int = 0
    data_label_position: str = "outside"
    text_align: str = "left"
    number_prefix: str = ""
    number_suffix: str = ""
    decimal_places: int = 2
    display_units: str = "none"
    null_value: str = "-"
    primary_color: str = "#5A3FE6"
    category_palette: List[str] = field(default_factory=list)
    bar_width_percent: int = 62
    line_width: int = 2
    show_markers: bool = True
    marker_size: int = 4
    value_color: str = "#111827"
    value_size: int = 0
    value_align: str = "left"
    card_density: str = "normal"
    show_card_accent: bool = True
    show_card_sparkline: bool = True
    alt_text: str = ""


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
