from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pivot_theme_has_explicit_alternate_row_rule():
    theme_source = (
        ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_theme.py"
    ).read_text(encoding="utf-8")
    assert "QTableView::item:alternate" in theme_source
    assert "alternate-background-color: #fcfcfd" in theme_source
    assert "alternate-background-color: #0F172A" in theme_source


def test_pivot_table_widget_applies_alternate_palette():
    widget_source = (
        ROOT / "plugin" / "Summarizer" / "pivot_table_widget.py"
    ).read_text(encoding="utf-8")
    assert "QPalette.AlternateBase" in widget_source
    assert "setAlternatingRowColors(True)" in widget_source
    assert "item.setBackground(alternate_row_color)" not in widget_source
