from __future__ import annotations

from typing import List

from .pivot_models import PivotCell


class PivotSelectionBridge:
    def __init__(self, iface):
        self.iface = iface

    def select_feature_ids(self, layer, feature_ids: List[int], zoom: bool = True):
        ids = self._merge_feature_ids_from_lists([feature_ids or []])
        if layer is None or not ids:
            return
        try:
            layer.selectByIds(ids)
            if zoom and self.iface is not None and hasattr(self.iface, "mapCanvas"):
                canvas = self.iface.mapCanvas()
                if canvas is not None and hasattr(canvas, "zoomToSelected"):
                    canvas.zoomToSelected(layer)
        except Exception:
            return

    def select_cell(self, layer, cell: PivotCell, zoom: bool = True):
        if cell is None:
            return
        self.select_feature_ids(layer, list(cell.feature_ids or []), zoom=zoom)

    def select_row(self, layer, row_cells: List[PivotCell], zoom: bool = True):
        self.select_feature_ids(layer, self._merge_feature_ids(row_cells), zoom=zoom)

    def select_column(self, layer, column_cells: List[PivotCell], zoom: bool = True):
        self.select_feature_ids(layer, self._merge_feature_ids(column_cells), zoom=zoom)

    def _merge_feature_ids(self, cells: List[PivotCell]) -> List[int]:
        return self._merge_feature_ids_from_lists(
            [list(cell.feature_ids or []) for cell in (cells or []) if cell is not None]
        )

    def _merge_feature_ids_from_lists(self, groups: List[List[int]]) -> List[int]:
        merged = []
        seen = set()
        for group in groups or []:
            for feature_id in group or []:
                if feature_id in seen:
                    continue
                seen.add(feature_id)
                merged.append(int(feature_id))
        return merged
