from pathlib import Path

from plugin.Summarizer.model_view.model_toolbar import (
    toolbar_visuals_should_be_visible,
    toolbar_visuals_visible_count,
)


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


def test_toolbar_visuals_stay_available_while_format_panel_is_open():
    assert toolbar_visuals_should_be_visible(
        has_project=True,
        edit_enabled=True,
        create_chart_checked=False,
        builder_panel_open=False,
        visual_panel_open=True,
    )


def test_toolbar_visuals_hide_when_no_visual_panel_context_is_open():
    assert not toolbar_visuals_should_be_visible(
        has_project=True,
        edit_enabled=True,
        create_chart_checked=False,
        builder_panel_open=False,
        visual_panel_open=False,
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


def test_model_toolbar_uses_white_selected_and_black_hover_states():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )
    header_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")
    theme_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_theme.py"
    ).read_text(encoding="utf-8")

    assert "QPushButton#ModelToolbarButton:checked:hover" in source
    assert "background: #111827;" in source
    assert "color: #FFFFFF;" in source
    assert "QPushButton#ModelToolbarButton:pressed" in source
    assert "background: #F3F4F6;" in source
    assert "min-width: 30px;" in source
    assert "icon_size: int = 20" in source
    assert "_toolbar_button_icon" in source
    assert "button.toggled.connect" in source
    assert "QToolButton#ModelVisualTypeButton:checked:hover" in source
    assert "data_fields_btn.setProperty(\"modelIconSize\", 20)" in header_source
    assert "QIcon.On" in theme_source


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


def test_clear_filters_button_floats_over_canvas_and_uses_squarer_corners():
    header_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py"
    ).read_text(encoding="utf-8")
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "toolbar_layout.addWidget(clear_filters_btn, 0)" not in header_source
    assert "self.clear_filters_btn.setParent(self.canvas_page)" in model_source
    assert "def _position_clear_filters_button(self):" in model_source
    assert "def _schedule_clear_filters_button_position(self):" in model_source
    assert "QPushButton#ModelActionButton {" in model_source
    assert "border-radius: 4px;" in model_source
    assert "self._schedule_clear_filters_button_position()" in model_source
    assert "for delay in (0, 40, 120):" in model_source
    assert "self._schedule_clear_filters_button_position()" in model_source


def test_builder_visual_selection_uses_cached_icons_during_programmatic_sync():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )
    builder_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_builder_panel.py"
    ).read_text(encoding="utf-8")

    assert "def _sync_visual_type_button_states(self, buttons, active_chart_type: str = \"\"):" in model_source
    assert "button._model_icon_normal = normal_icon" in builder_source
    assert "button._model_icon_checked = checked_icon" in builder_source
    assert "parent._model_visual_button_group = group" in builder_source
    assert "self._sync_visual_type_button_states(buttons, active_chart_type)" in model_source
    assert "QButtonGroup(parent)" in builder_source
    assert "button_containers = [container for container in (buttons_container, toolbar_container) if container is not None]" in model_source
    assert "container.setUpdatesEnabled(False)" in model_source
    assert "group.setExclusive(False)" in model_source
    assert "self._sync_visual_type_button_states(toolbar_buttons, \"\")" in model_source
    assert "self._sync_visual_type_button_states(toolbar_buttons, active_chart_type)" in model_source


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


def test_presentation_button_icon_is_neutral_not_purple():
    icon_source = (
        ROOT / "plugin" / "Summarizer" / "resources" / "SVG" / "PresentationMap.svg"
    ).read_text(encoding="utf-8")

    assert "#6C4CF1" not in icon_source
    assert "#7C6CFF" not in icon_source
    assert "#F5F1FF" not in icon_source
    assert "#F3F4F6" in icon_source
    assert "#374151" in icon_source
