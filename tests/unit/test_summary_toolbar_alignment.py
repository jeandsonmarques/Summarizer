from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_summary_toolbar_uses_model_position_and_size_tokens():
    pivot_source = (ROOT / "plugin" / "Summarizer" / "pivot_table_widget.py").read_text(
        encoding="utf-8"
    )
    toolbar_source = (ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_toolbar.py").read_text(
        encoding="utf-8"
    )
    theme_source = (ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_theme.py").read_text(
        encoding="utf-8"
    )
    model_header_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")

    assert "root.setContentsMargins(0, 2, 4, 3)" in pivot_source
    assert "toolbar_strip.setMinimumHeight(44)" in model_header_source
    assert "self.toolbar_strip.setMinimumHeight(44)" in toolbar_source
    assert "button.setFixedSize(28, 28)" in toolbar_source
    assert "button.setFixedSize(28, 28)" in pivot_source
    assert "self._external_dashboard_button.setFixedSize(28, 28)" in theme_source
    assert "min-width: 28px;" in toolbar_source
    assert "min-width: 28px;" in theme_source
    assert "setFixedSize(30, 30)" not in toolbar_source


def test_summary_undo_redo_icons_match_model_icons_after_theme_refresh():
    toolbar_source = (ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_toolbar.py").read_text(
        encoding="utf-8"
    )
    theme_source = (ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_theme.py").read_text(
        encoding="utf-8"
    )
    model_header_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")

    assert 'configure_toolbar_icon_button(self.undo_btn, "Walker-Undo.svg"' in toolbar_source
    assert 'configure_toolbar_icon_button(self.redo_btn, "Walker-Redo.svg"' in toolbar_source
    assert 'configure_toolbar_icon_button(undo_btn, "Walker-Undo.svg"' in model_header_source
    assert 'configure_toolbar_icon_button(redo_btn, "Walker-Redo.svg"' in model_header_source
    assert 'undo_icon = svg_icon("Walker-Undo.svg")' in theme_source
    assert 'redo_icon = svg_icon("Walker-Redo.svg")' in theme_source
    assert '_TOOLBAR_SVG_ICONS["undo"]' not in theme_source
    assert '_TOOLBAR_SVG_ICONS["redo"]' not in theme_source
