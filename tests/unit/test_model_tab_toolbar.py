from pathlib import Path

from plugin.Summarizer.model_view.model_toolbar import toolbar_visuals_visible_count


ROOT = Path(__file__).resolve().parents[2]


def test_toolbar_visuals_visible_count_keeps_all_buttons_when_space_is_sufficient():
    assert (
        toolbar_visuals_visible_count(220, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 5
    )


def test_toolbar_visuals_visible_count_hides_one_button_at_a_time():
    assert (
        toolbar_visuals_visible_count(170, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 4
    )
    assert (
        toolbar_visuals_visible_count(136, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 3
    )


def test_model_builder_panel_open_is_preserved_until_canvas_page_is_active():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert (
        "pending_open = requested and can_edit_project and not in_canvas_page"
        in source
    )
    assert "self._builder_panel_open = bool(active or pending_open)" in source
    assert (
        "if self.create_chart_btn.isChecked() != self._builder_panel_open:"
        in source
    )


def test_model_side_panels_start_collapsed_for_new_and_opened_projects():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "self._visual_side_collapsed = True" in source
    assert "self._data_panel_collapsed = True" in source
    assert "def _reset_model_side_panels_collapsed(self):" in source
    assert "self._reset_model_side_panels_collapsed()\n        page = DashboardPage" in source
    assert "project = self._normalize_loaded_project(project)\n        self._reset_model_side_panels_collapsed()" in source


def test_fields_panel_expands_when_new_chart_is_triggered():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "def _expand_data_panel_for_new_chart(self):" in source
    assert "self._data_panel_collapsed = False" in source
    assert "if checked:\n            self._expand_data_panel_for_new_chart()" in source


def test_clear_filters_button_is_available_in_preview_mode():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _update_filters_bar")
    end = source.index("def _clear_model_filters", start)
    body = source[start:end]

    assert "if not items:" in body
    assert "if not self.edit_mode_btn.isChecked() or not items:" not in body
    assert "self.clear_filters_btn.setVisible(True)" in body


def test_model_toolbar_keeps_edit_mode_height_in_preview_mode():
    source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")

    assert "toolbar_strip.setMinimumHeight(44)" in source
    assert "build_visual_type_buttons(toolbar_visuals_strip, toolbar_visuals_layout, button_size=32" in source


def test_fields_toolbar_button_sits_next_to_format_visual_and_toggles_panel():
    header_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "data_fields_btn: QPushButton" in header_source
    assert "data_fields_btn = QPushButton(_rt(\"Campos\"))" in header_source
    assert "data_fields_btn.setToolTip(_rt(\"Campos\"))" in header_source
    assert "Mostrar ou recolher campos" not in header_source
    assert "for button in (create_chart_btn, format_visual_btn, data_fields_btn, edit_mode_btn):" in header_source
    assert "self.data_fields_btn.toggled.connect(self._handle_data_fields_toggle)" in model_source
    assert "def _handle_data_fields_toggle(self, checked: bool):" in model_source
    assert "self._set_data_panel_collapsed(not bool(checked))" in model_source


def test_model_fields_panel_uses_summary_like_compact_scale():
    data_panel_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_data_panel.py"
    ).read_text(encoding="utf-8")
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "font.setPixelSize(11)" in data_panel_source
    assert "QFrame#ModelBuilderDataPanel QLabel#ModelBuilderTitle" in model_source
    assert "QFrame#ModelBuilderDataPanel QComboBox#ModelBuilderCombo" in model_source
    assert "font-size: 11px;" in data_panel_source
    assert "min-height: 28px;" in data_panel_source
    assert "min-height: 22px;" in data_panel_source
    assert "QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList::item" in model_source
