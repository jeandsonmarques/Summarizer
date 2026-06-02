from pathlib import Path

from plugin.Summarizer.dashboard_models import ROLE_VALUES, ROLE_X_AXIS, ROLE_Y_AXIS
from plugin.Summarizer.model_view.model_builder_panel import (
    binding_slot_label,
    builder_has_selection,
    chart_type_label,
    is_valid_binding_slot,
    selected_builder_chart_type_from_buttons,
    visual_type_labels,
)


class FakeButton:
    def __init__(self, checked=False):
        self._checked = bool(checked)

    def isChecked(self):
        return self._checked


def test_selected_builder_chart_type_normalizes_checked_button():
    buttons = {"columns": FakeButton(True), "line": FakeButton(False)}

    assert selected_builder_chart_type_from_buttons(buttons) == "bar"


def test_selected_builder_chart_type_falls_back_to_bar_when_empty():
    assert selected_builder_chart_type_from_buttons({}) == "bar"


def test_binding_slot_validation_accepts_compatible_slots_only():
    assert is_valid_binding_slot("scatter", ROLE_X_AXIS, "measure") is True
    assert is_valid_binding_slot("scatter", ROLE_Y_AXIS, "dimension") is False
    assert is_valid_binding_slot("bar", "", "measure") is False
    assert is_valid_binding_slot("bar", "auto", "measure") is False


def test_builder_selection_state_is_explicit():
    assert builder_has_selection(object(), object()) is True
    assert builder_has_selection(None, object()) is False
    assert builder_has_selection(object(), None) is False


def test_visual_type_labels_and_slot_labels_match_existing_texts():
    labels = visual_type_labels()

    assert labels["bar"] == "Colunas"
    assert labels["matrix"] == "Matriz"
    assert chart_type_label("missing") == "Grafico"
    assert binding_slot_label("matrix", ROLE_X_AXIS) == "Linhas"
    assert binding_slot_label("bar", ROLE_VALUES) == "Valores"


def test_builder_empty_state_uses_top_guidance_card_style():
    root = Path(__file__).resolve().parents[2]
    builder_source = (
        root / "plugin" / "Summarizer" / "model_view" / "model_builder_panel.py"
    ).read_text(encoding="utf-8")
    model_source = (root / "plugin" / "Summarizer" / "model_tab.py").read_text(
        encoding="utf-8"
    )

    assert "ModelBuilderEmptyStateTitle" not in builder_source
    assert 'QLabel(_rt("Adicionar dados")' not in builder_source
    assert "_BUILDER_GUIDANCE_CARD = \"#F3F4F6\"" in builder_source
    assert "_BUILDER_GUIDANCE_CARD_TEXT = \"#334155\"" in builder_source
    assert "Selecione um visual para adicionar dados aos campos." in builder_source
    assert "Selecione um visual para formatar suas propriedades." not in builder_source
    assert "#0F8B74" not in builder_source
    assert "ModelBuilderEmptyStateNotch" not in builder_source
    assert "ModelBuilderEmptyStateClose" in builder_source
    assert "_BuilderGuidanceNotch" not in builder_source
    assert "QFrame#ModelBuilderEmptyStateCard" in model_source
    assert (
        "QFrame#ModelVisualSidePanel {\n"
        "                background: __SURFACE__;\n"
        "                border: 1px solid __BORDER__;\n"
        "                border-radius: 2px;"
        in model_source
    )
    assert (
        "QFrame#ModelBuilderDataPanel {\n"
        "                background: #FFFFFF;\n"
        "                border: 1px solid rgba(15, 23, 42, 0.06);\n"
        "                border-radius: 2px;"
        in model_source
    )
    assert "QPushButton#ModelVisualPanelTabButton" in model_source
    assert "border-radius: 2px;" in model_source
    assert "background-color: #F3F4F6;" in model_source
    assert '("ModelBuilderEmptyStateLabel", label_style)' not in model_source
