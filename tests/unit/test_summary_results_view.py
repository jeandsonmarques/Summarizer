from __future__ import annotations

from Summarizer.summary_view.summary_results_view import (
    build_summary_block,
    build_summary_unavailable_html,
    build_summary_welcome_html,
    display_advanced_summary,
    escape_html,
    set_results_view,
    show_results_message,
    show_summary_welcome,
)


class DummyWidget:
    def __init__(self, *, fail_set_html: bool = False):
        self.visible = None
        self.html = None
        self.fail_set_html = fail_set_html
        self.welcome_called = False
        self.summary_data = None

    def setVisible(self, visible):
        self.visible = visible

    def setHtml(self, html):
        if self.fail_set_html:
            raise RuntimeError("fail html")
        self.html = html

    def show_welcome_message(self):
        self.welcome_called = True

    def set_summary_data(self, summary_data):
        self.summary_data = summary_data


def test_escape_html_and_summary_block_keep_current_text():
    assert escape_html(None) == ""
    assert escape_html("<&\"'>") == "&lt;&amp;&quot;&#39;&gt;"

    block = build_summary_block("Resumo pronto")
    assert block == "<p style='margin:8px 0;'>Resumo pronto</p>"
    assert "Resumo pronto" in build_summary_welcome_html("Resumo pronto")
    assert "Sem dados" in build_summary_unavailable_html("Sem dados")


def test_show_results_message_sets_styled_html_and_falls_back(monkeypatch):
    widget = DummyWidget()
    monkeypatch.setattr(
        "Summarizer.summary_view.summary_results_view.apply_result_style",
        lambda html: f"styled:{html}",
    )

    assert show_results_message(widget, "conteudo", set_results_view=lambda mode: None) is True
    assert widget.html == "styled:conteudo"

    monkeypatch.setattr(
        "Summarizer.summary_view.summary_results_view.apply_result_style",
        lambda html: (_ for _ in ()).throw(RuntimeError("style fail")),
    )
    fallback_widget = DummyWidget()
    assert (
        show_results_message(
            fallback_widget,
            "conteudo",
            set_results_view=lambda mode: None,
        )
        is True
    )
    assert fallback_widget.html == "conteudo"


def test_show_summary_welcome_and_fallback_message():
    pivot = DummyWidget()
    message_widget = DummyWidget()
    visible_modes = []
    ribbon_states = []

    assert (
        show_summary_welcome(
            pivot,
            message_widget,
            set_results_view=visible_modes.append,
            set_ribbon_visible=ribbon_states.append,
            welcome_html="bem-vindo",
        )
        is True
    )
    assert pivot.welcome_called is True
    assert visible_modes == ["pivot"]
    assert ribbon_states == [False]

    fallback_visible_modes = []
    fallback_message_widget = DummyWidget()
    assert (
        show_summary_welcome(
            None,
            fallback_message_widget,
            set_results_view=fallback_visible_modes.append,
            set_ribbon_visible=lambda visible: None,
            welcome_html="sem dados",
        )
        is True
    )
    assert fallback_message_widget.html is not None
    assert "sem dados" in fallback_message_widget.html
    assert fallback_visible_modes == ["message"]


def test_display_advanced_summary_switches_to_pivot():
    pivot = DummyWidget()
    visible_modes = []
    summary_data = {"basic_stats": {"total": 1}}

    assert (
        display_advanced_summary(
            pivot,
            summary_data,
            set_results_view=visible_modes.append,
        )
        is True
    )
    assert pivot.summary_data == summary_data
    assert visible_modes == ["pivot"]


def test_set_results_view_updates_visible_widgets():
    pivot = DummyWidget()
    message = DummyWidget()
    table = DummyWidget()

    set_results_view(pivot, message, table, "message")

    assert pivot.visible is False
    assert message.visible is True
    assert table.visible is False
