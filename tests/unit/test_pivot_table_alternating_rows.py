from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pivot_theme_has_explicit_alternate_row_rule():
    theme_source = (ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_theme.py").read_text(
        encoding="utf-8"
    )
    light_alternate_rule = (
        "QTableView::item:alternate {\n"
        "            background: #fcfcfd;\n"
        "            padding: 6px 9px;\n"
        "            border: none;"
    )
    dark_alternate_rule = (
        "QTableView::item:alternate {\n"
        "            background: #0F172A;\n"
        "            padding: 6px 9px;\n"
        "            border: none;"
    )

    assert "QTableView::item:alternate" in theme_source
    assert "alternate-background-color: #fcfcfd" in theme_source
    assert "alternate-background-color: #0F172A" in theme_source
    assert theme_source.count("QTableView::item:alternate") == 3
    assert theme_source.count("padding: 6px 9px;") >= 3
    assert theme_source.count(light_alternate_rule) == 1
    assert theme_source.count(dark_alternate_rule) == 1


def test_pivot_table_widget_applies_alternate_palette():
    widget_source = (ROOT / "plugin" / "Summarizer" / "pivot_table_widget.py").read_text(
        encoding="utf-8"
    )
    assert "QPalette.AlternateBase" in widget_source
    assert "setAlternatingRowColors(True)" in widget_source
    assert "item.setBackground(alternate_row_color)" not in widget_source


def test_pivot_table_widget_uses_stable_cell_delegate_for_zebra_rows():
    widget_source = (ROOT / "plugin" / "Summarizer" / "pivot_table_widget.py").read_text(
        encoding="utf-8"
    )
    assert "class _PivotTableCellDelegate(QStyledItemDelegate)" in widget_source
    assert "HORIZONTAL_PADDING = 9" in widget_source
    assert 'opt.text = ""' in widget_source
    assert (
        "self.table_view.setItemDelegate(_PivotTableCellDelegate(self.table_view))" in widget_source
    )
