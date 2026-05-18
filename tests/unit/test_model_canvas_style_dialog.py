from plugin.Summarizer.model_view.model_canvas_style_dialog import (
    apply_canvas_style_to_source_meta,
    default_canvas_style,
    normalize_canvas_style,
    normalize_hex_color,
    set_color_preview_chip,
)


class FakeLabel:
    def __init__(self):
        self.text = None
        self.stylesheet = None

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, stylesheet):
        self.stylesheet = stylesheet


def test_normalize_hex_color_expands_short_and_falls_back_when_invalid():
    assert normalize_hex_color("#abc", "#000000") == "#AABBCC"
    assert normalize_hex_color("123456", "#000000") == "#123456"
    assert normalize_hex_color("not-a-color", "#f0f0f0") == "#F0F0F0"


def test_normalize_canvas_style_merges_defaults_and_keeps_legacy_keys():
    style = normalize_canvas_style(
        {
            "background": "#abc",
            "grid_color": "123456",
            "show_grid": 0,
            "grid_size": 2,
            "grid_opacity": 3,
            "snap": True,
        }
    )

    assert style["background"] == "#AABBCC"
    assert style["grid_color"] == "#123456"
    assert style["show_grid"] is False
    assert style["grid_size"] == 4
    assert style["grid_opacity"] == 1.0
    assert style["snap"] is True


def test_normalize_canvas_style_keeps_default_shape():
    style = normalize_canvas_style()
    defaults = default_canvas_style()

    assert set(defaults).issubset(set(style))
    assert style["background"] == defaults["background"]
    assert style["grid_color"] == defaults["grid_color"]


def test_apply_canvas_style_to_source_meta_preserves_other_keys():
    source_meta = {
        "canvas_style": {"background": "#111111", "legacy_snap": False},
        "project_name": "demo",
    }

    updated = apply_canvas_style_to_source_meta(
        source_meta,
        {"background": "#222222", "grid_color": "#333333", "legacy_snap": True},
    )

    assert updated["project_name"] == "demo"
    assert updated["canvas_style"]["background"] == "#222222"
    assert updated["canvas_style"]["grid_color"] == "#333333"
    assert updated["canvas_style"]["legacy_snap"] is True
    assert source_meta["canvas_style"]["background"] == "#111111"


def test_set_color_preview_chip_updates_text_and_stylesheet():
    label = FakeLabel()

    set_color_preview_chip(label, "#abc", "#000000")

    assert label.text == " "
    assert "#AABBCC" in label.stylesheet
