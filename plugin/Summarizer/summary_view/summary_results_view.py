# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any, Callable, Optional

from ..utils.logging_utils import log_exception

try:
    from ..result_style import apply_result_style
except Exception:  # pragma: no cover - fallback for non-QGIS test environments

    def apply_result_style(html: str) -> str:
        return html


SUMMARY_WELCOME_TEXT = "Selecione uma camada e clique em Gerar Resumo."
SUMMARY_UNAVAILABLE_TEXT = "Não foi possível exibir a tabela dinâmica para estes dados."


def escape_html(text: Any) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def build_summary_block(message: str) -> str:
    return f"<p style='margin:8px 0;'>{escape_html(message)}</p>"


def build_summary_welcome_html(message: str = SUMMARY_WELCOME_TEXT) -> str:
    return build_summary_block(message)


def build_summary_unavailable_html(message: str = SUMMARY_UNAVAILABLE_TEXT) -> str:
    return build_summary_block(message)


def set_results_view(pivot_widget, summary_message_widget, table_widget, mode: str) -> None:
    pivot_visible = mode == "pivot"
    message_visible = mode == "message"
    table_visible = mode == "table"

    if pivot_widget is not None:
        pivot_widget.setVisible(pivot_visible)

    if summary_message_widget is not None:
        summary_message_widget.setVisible(message_visible)

    if table_widget is not None:
        table_widget.setVisible(table_visible)


def show_results_message(
    summary_message_widget,
    html: str,
    *,
    set_results_view: Optional[Callable[[str], None]] = None,
) -> bool:
    if summary_message_widget is None:
        return False
    try:
        summary_message_widget.setHtml(apply_result_style(html))
    except Exception:
        summary_message_widget.setHtml(html)
    if set_results_view is not None:
        set_results_view("message")
    return True


def show_summary_welcome(
    pivot_widget,
    summary_message_widget,
    *,
    set_results_view: Optional[Callable[[str], None]] = None,
    set_ribbon_visible: Optional[Callable[[bool], None]] = None,
    welcome_html: str = build_summary_welcome_html(),
) -> bool:
    if set_ribbon_visible is not None:
        set_ribbon_visible(False)

    if pivot_widget is not None:
        try:
            pivot_widget.show_welcome_message()
            if set_results_view is not None:
                set_results_view("pivot")
            return True
        except Exception:
            log_exception("falha opcional ignorada")

    return show_results_message(
        summary_message_widget,
        welcome_html,
        set_results_view=set_results_view,
    )


def display_advanced_summary(
    pivot_widget,
    summary_data,
    *,
    set_results_view: Optional[Callable[[str], None]] = None,
    summary_message_widget=None,
    fallback_html: Optional[str] = None,
) -> bool:
    if pivot_widget is not None:
        pivot_widget.set_summary_data(summary_data)
        if set_results_view is not None:
            set_results_view("pivot")
        return True

    if fallback_html is None:
        return False

    return show_results_message(
        summary_message_widget,
        fallback_html,
        set_results_view=set_results_view,
    )
