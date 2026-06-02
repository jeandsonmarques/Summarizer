# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from typing import Sequence


def toolbar_visuals_should_be_visible(
    *,
    has_project: bool,
    edit_enabled: bool,
    create_chart_checked: bool,
    builder_panel_open: bool,
    visual_panel_open: bool,
) -> bool:
    return bool(
        has_project and
        edit_enabled and
        (create_chart_checked or builder_panel_open or visual_panel_open)
    )


def toolbar_visuals_visible_count(
    available_width: int,
    button_widths: Sequence[int],
    *,
    spacing: int = 1,
    padding: int = 8,
) -> int:
    width_budget = max(0, int(available_width or 0))
    if width_budget <= 0:
        return 0
    used = max(0, int(padding or 0))
    visible = 0
    for raw_width in list(button_widths or []):
        button_width = max(0, int(raw_width or 0))
        next_width = button_width
        if visible > 0:
            next_width += max(0, int(spacing or 0))
        if used + next_width > width_budget:
            break
        used += next_width
        visible += 1
    return visible


__all__ = [
    "toolbar_visuals_should_be_visible",
    "toolbar_visuals_visible_count",
]
