from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.i18n_runtime import tr_text as _rt
from .model_cards import _ModelModeToggle


@dataclass
class ModelHeaderParts:
    header: QFrame
    new_btn: QPushButton
    open_btn: QPushButton
    save_btn: QPushButton
    save_as_btn: QPushButton
    export_btn: QPushButton
    undo_btn: QPushButton
    redo_btn: QPushButton
    create_chart_btn: QPushButton
    format_visual_btn: QPushButton
    edit_mode_btn: QPushButton
    settings_btn: QPushButton
    close_project_btn: QToolButton
    toolbar_strip: QFrame
    toolbar_visuals_strip: QFrame
    visual_types_leading_separator: QFrame
    visual_types_trailing_separator: QFrame
    mode_switch_wrap: QWidget
    mode_state_label: QLabel
    mode_toggle: _ModelModeToggle
    clear_filters_btn: QPushButton
    project_hint_label: QLabel
    filters_bar: QFrame
    filters_label: QLabel


def _create_toolbar_separator(parent: QWidget) -> QFrame:
    separator = QFrame(parent)
    separator.setObjectName("ModelToolbarSeparator")
    separator.setFrameShape(QFrame.VLine)
    separator.setFrameShadow(QFrame.Plain)
    return separator


def build_model_header(
    parent: QWidget,
    *,
    configure_toolbar_icon_button: Callable[..., None],
    build_visual_type_buttons: Callable[..., None],
) -> ModelHeaderParts:
    header = QFrame(parent)
    header.setObjectName("ModelHeader")
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(10)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(0)

    new_btn = QPushButton(_rt("Novo"))
    open_btn = QPushButton(_rt("Abrir"))
    save_btn = QPushButton(_rt("Salvar"))
    save_as_btn = QPushButton(_rt("Salvar como"))
    export_btn = QPushButton(_rt("Exportar"))
    undo_btn = QPushButton(_rt("Desfazer"))
    redo_btn = QPushButton(_rt("Refazer"))
    create_chart_btn = QPushButton(_rt("Criar grafico"))
    format_visual_btn = QPushButton(_rt("Formatar visual"))
    edit_mode_btn = QPushButton(_rt("Edicao"))
    settings_btn = QPushButton(_rt("Configuracoes"))
    create_chart_btn.setCheckable(True)
    create_chart_btn.setChecked(False)
    format_visual_btn.setCheckable(True)
    format_visual_btn.setChecked(False)
    edit_mode_btn.setCheckable(True)
    edit_mode_btn.setChecked(True)
    close_project_btn = QToolButton()
    close_project_btn.setObjectName("ModelCloseProjectButton")

    configure_toolbar_icon_button(undo_btn, "Walker-Undo.svg", _rt("Desfazer (Ctrl+Z)"))
    configure_toolbar_icon_button(redo_btn, "Walker-Redo.svg", _rt("Refazer (Ctrl+Shift+Z)"))
    configure_toolbar_icon_button(new_btn, "Walker-New.svg", _rt("Novo"))
    configure_toolbar_icon_button(open_btn, "Walker-Open.svg", _rt("Abrir"))
    configure_toolbar_icon_button(save_btn, "Walker-Save.svg", _rt("Salvar"))
    configure_toolbar_icon_button(save_as_btn, "Walker-SaveAs.svg", _rt("Salvar como"))
    configure_toolbar_icon_button(export_btn, "Walker-Image.svg", _rt("Exportar imagem"))
    configure_toolbar_icon_button(create_chart_btn, "ModelVisual-Pie.svg", _rt("Criar grafico"))
    configure_toolbar_icon_button(format_visual_btn, "Walker-Format.svg", _rt("Formatar visual"))
    configure_toolbar_icon_button(edit_mode_btn, "Walker-Edit.svg", _rt("Edicao"))
    configure_toolbar_icon_button(
        settings_btn,
        "Walker-Settings.svg",
        _rt("Configurar fundo e grade do canvas"),
        icon_color="#F97316",
    )
    configure_toolbar_icon_button(
        close_project_btn,
        "Close.svg",
        _rt("Fechar projeto e voltar para a tela inicial"),
        icon_size=16,
    )
    close_project_btn.setVisible(False)
    for button in (
        undo_btn,
        redo_btn,
        new_btn,
        open_btn,
        save_btn,
        save_as_btn,
        export_btn,
        create_chart_btn,
        format_visual_btn,
        edit_mode_btn,
        settings_btn,
        close_project_btn,
    ):
        button.setObjectName("ModelToolbarButton")

    toolbar_strip = QFrame(header)
    toolbar_strip.setObjectName("ModelToolbarStrip")
    toolbar_strip.setAttribute(Qt.WA_StyledBackground, True)
    toolbar_layout = QHBoxLayout(toolbar_strip)
    toolbar_layout.setContentsMargins(8, 5, 8, 5)
    toolbar_layout.setSpacing(2)
    for button in (undo_btn, redo_btn):
        toolbar_layout.addWidget(button, 0)
    toolbar_layout.addWidget(_create_toolbar_separator(toolbar_strip), 0)
    for button in (new_btn, open_btn, save_btn, save_as_btn, export_btn):
        toolbar_layout.addWidget(button, 0)
    toolbar_layout.addWidget(_create_toolbar_separator(toolbar_strip), 0)
    for button in (create_chart_btn, format_visual_btn, edit_mode_btn):
        toolbar_layout.addWidget(button, 0)
    visual_types_leading_separator = _create_toolbar_separator(toolbar_strip)
    toolbar_layout.addWidget(visual_types_leading_separator, 0)

    toolbar_visuals_strip = QFrame(toolbar_strip)
    toolbar_visuals_strip.setObjectName("ModelToolbarVisualTypes")
    toolbar_visuals_layout = QHBoxLayout(toolbar_visuals_strip)
    toolbar_visuals_layout.setContentsMargins(4, 0, 4, 0)
    toolbar_visuals_layout.setSpacing(1)
    build_visual_type_buttons(toolbar_visuals_strip, toolbar_visuals_layout, button_size=32, icon_size=20)
    toolbar_visuals_strip.setVisible(False)
    toolbar_layout.addWidget(toolbar_visuals_strip, 0)

    visual_types_trailing_separator = _create_toolbar_separator(toolbar_strip)
    toolbar_layout.addWidget(visual_types_trailing_separator, 0)
    toolbar_layout.addStretch(1)

    mode_switch_wrap = QWidget(toolbar_strip)
    mode_switch_wrap.setObjectName("ModelModeSwitchWrap")
    mode_layout = QHBoxLayout(mode_switch_wrap)
    mode_layout.setContentsMargins(0, 0, 0, 0)
    mode_layout.setSpacing(6)
    mode_state_label = QLabel(_rt("Edição"), mode_switch_wrap)
    mode_state_label.setObjectName("ModelModeStateLabel")
    mode_toggle = _ModelModeToggle(mode_switch_wrap)
    mode_toggle.setObjectName("ModelModeToggle")
    mode_toggle.setChecked(True, animated=False)
    mode_toggle.setToolTip(_rt("Alternar entre modo de edição e pré-visualização"))
    mode_layout.addWidget(mode_state_label, 0)
    mode_layout.addWidget(mode_toggle, 0)

    clear_filters_btn = QPushButton(_rt("Limpar filtros"))
    clear_filters_btn.setObjectName("ModelActionButton")
    clear_filters_btn.setVisible(False)
    toolbar_layout.addWidget(clear_filters_btn, 0)
    toolbar_layout.addSpacing(8)
    toolbar_layout.addWidget(settings_btn, 0)
    toolbar_layout.addSpacing(8)
    toolbar_layout.addWidget(mode_switch_wrap, 0)
    toolbar_layout.addSpacing(8)
    toolbar_layout.addWidget(close_project_btn, 0)

    top_row.addWidget(toolbar_strip, 1)
    header_layout.addLayout(top_row)

    project_hint_label = QLabel(
        _rt("Monte painéis com os graficos da aba Resumo e da aba Relatorios. O painel salvo continua editavel.")
    )
    project_hint_label.setObjectName("ModelHint")
    project_hint_label.setWordWrap(True)
    project_hint_label.setVisible(False)
    header_layout.addWidget(project_hint_label)

    filters_bar = QFrame(parent)
    filters_bar.setObjectName("ModelFiltersBar")
    filters_bar.setAttribute(Qt.WA_StyledBackground, True)
    filters_layout = QHBoxLayout(filters_bar)
    filters_layout.setContentsMargins(14, 10, 14, 10)
    filters_layout.setSpacing(10)
    filters_label = QLabel(_rt("Filtros ativos: nenhum"))
    filters_label.setObjectName("ModelFiltersLabel")
    filters_label.setWordWrap(True)
    filters_layout.addWidget(filters_label, 1)
    filters_bar.setVisible(False)

    return ModelHeaderParts(
        header=header,
        new_btn=new_btn,
        open_btn=open_btn,
        save_btn=save_btn,
        save_as_btn=save_as_btn,
        export_btn=export_btn,
        undo_btn=undo_btn,
        redo_btn=redo_btn,
        create_chart_btn=create_chart_btn,
        format_visual_btn=format_visual_btn,
        edit_mode_btn=edit_mode_btn,
        settings_btn=settings_btn,
        close_project_btn=close_project_btn,
        toolbar_strip=toolbar_strip,
        toolbar_visuals_strip=toolbar_visuals_strip,
        visual_types_leading_separator=visual_types_leading_separator,
        visual_types_trailing_separator=visual_types_trailing_separator,
        mode_switch_wrap=mode_switch_wrap,
        mode_state_label=mode_state_label,
        mode_toggle=mode_toggle,
        clear_filters_btn=clear_filters_btn,
        project_hint_label=project_hint_label,
        filters_bar=filters_bar,
        filters_label=filters_label,
    )


__all__ = ["ModelHeaderParts", "build_model_header"]
