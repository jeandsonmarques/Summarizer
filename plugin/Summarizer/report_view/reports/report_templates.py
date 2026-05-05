from __future__ import annotations

from string import Template
from typing import Dict

from .report_data import REPORTS_FONT_SCALE
from .report_models import ReportStyleContext

try:
    from ...palette import COLORS, TYPOGRAPHY
except Exception:  # pragma: no cover - fallback for pure-python tests without QGIS
    COLORS = {
        "color_surface": "#FFFFFF",
        "color_secondary": "#2B7DE9",
    }
    TYPOGRAPHY = {
        "font_ui_stack": '"Inter", sans-serif',
        "font_page_title_px": 24,
        "font_section_title_px": 16,
        "font_body_px": 13,
        "font_secondary_px": 12,
        "font_caption_px": 11,
        "font_button_px": 13,
        "font_chip_px": 12,
        "font_weight_regular": 400,
        "font_weight_medium": 500,
        "font_weight_semibold": 600,
    }

REPORTS_STYLE_TEMPLATE = Template(
    """
    QWidget#reportsRoot,
    QWidget#reportsWorkspace {
        background: transparent;
    }
    QWidget#chatColumn,
    QWidget#conversationViewportHost,
    QWidget#conversationViewport,
    QWidget#footerSuggestions,
    QFrame#promptDock {
        background: transparent;
    }
    QWidget#reportsRoot,
    QWidget#reportsRoot * {
        font-family: ${font_ui_stack};
    }
    QFrame#reportsHeader {
        background: transparent;
        border: none;
    }
    QToolButton#contextButton {
        background: transparent;
        border: none;
        color: ${text_primary};
        font-size: ${font_section_title_px}px;
        font-weight: ${font_weight_semibold};
        padding: 6px 8px;
        border-radius: 10px;
    }
    QToolButton#contextButton:hover {
        background: ${hover_tint};
    }
    QLabel#reportsStatusLabel {
        color: ${text_muted};
        font-size: ${font_secondary_px}px;
        font-weight: ${font_weight_regular};
        padding-right: 4px;
    }
    QLabel#reportsTitle {
        color: ${text_primary};
        font-size: ${font_page_title_px}px;
        font-weight: ${font_weight_semibold};
    }
    QLabel#reportsSubtitle {
        color: ${text_secondary};
        font-size: ${font_secondary_px}px;
        font-weight: ${font_weight_regular};
    }
    QFrame#chatShell {
        background: transparent;
        border: none;
    }
    QFrame#visualShell {
        background: ${surface};
        border: 1px solid ${border_subtle};
        border-radius: 28px;
    }
    QFrame#visualTopBar {
        background: transparent;
        border-bottom: 1px solid ${border_soft};
    }
    QLabel#visualPanelBadge {
        color: ${text_muted};
        font-size: ${font_caption_px}px;
        font-weight: ${font_weight_semibold};
    }
    QLabel#assistantBadge {
        color: ${text_muted};
        font-size: ${font_caption_px}px;
        font-weight: ${font_weight_regular};
    }
    QLabel#visualPanelTitle {
        color: ${text_primary};
        font-size: ${font_section_title_px}px;
        font-weight: ${font_weight_semibold};
    }
    QLabel#assistantSummary {
        color: ${text_primary};
        font-size: ${font_section_title_px}px;
        font-weight: ${font_weight_regular};
    }
    QLabel#visualPanelSummary,
    QLabel#assistantText,
    QLabel#assistantStatus,
    QLabel#userBubbleText {
        color: ${text_primary};
        font-size: ${font_body_px}px;
        font-weight: ${font_weight_regular};
    }
    QLabel#visualPanelText,
    QLabel#assistantHelper,
    QLabel#reportsSubtitle {
        color: ${text_secondary};
        font-size: ${font_secondary_px}px;
        font-weight: ${font_weight_regular};
    }
    QLabel#visualPanelMeta,
    QLabel#chatToolbarLabel {
        color: ${text_muted};
        font-size: ${font_caption_px}px;
        font-weight: ${font_weight_medium};
    }
    QFrame#visualPanelChartShell,
    QFrame#assistantChartShell {
        background: ${surface};
        border: 1px solid ${border_soft};
        border-radius: 18px;
    }
    QTableWidget#visualPanelTable,
    QTableWidget#assistantTable {
        background: transparent;
        border: none;
        color: ${text_primary};
        font-size: ${font_body_px}px;
        gridline-color: transparent;
        selection-background-color: transparent;
        alternate-background-color: transparent;
    }
    QTableWidget#visualPanelTable::item,
    QTableWidget#assistantTable::item {
        padding: 7px 8px;
        border-bottom: 1px solid ${border_soft};
    }
    QHeaderView::section {
        background: transparent;
        color: ${text_muted};
        border: none;
        border-bottom: 1px solid ${border_soft};
        padding: 8px 8px;
        font-size: ${font_secondary_px}px;
        font-weight: ${font_weight_semibold};
    }
    QFrame#chatToolbar {
        background: transparent;
        border: none;
    }
    QPushButton#visualPanelButton,
    QPushButton[optionButton="true"] {
        background: ${surface};
        border: 1px solid ${border_soft};
        color: ${text_primary};
        min-height: 30px;
        padding: 0 12px;
        border-radius: 14px;
        font-size: ${font_button_px}px;
        font-weight: ${font_weight_regular};
    }
    QPushButton#clearChatButton {
        background: ${surface};
        border: 1px solid ${border_soft};
        color: ${text_primary};
        min-height: 30px;
        padding: 0 12px;
        border-radius: 14px;
        font-size: ${font_button_px}px;
        font-weight: ${font_weight_semibold};
    }
    QPushButton[actionButton="true"] {
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid rgba(15, 23, 42, 0.07);
        color: ${text_secondary};
        min-height: 29px;
        padding: 0 11px;
        border-radius: 14px;
        font-size: ${font_button_px}px;
        font-weight: ${font_weight_regular};
    }
    QPushButton#visualPanelButton:hover,
    QPushButton#clearChatButton:hover,
    QPushButton[optionButton="true"]:hover {
        background: ${surface_hover};
        border-color: ${border_hover};
    }
    QPushButton[actionButton="true"]:hover {
        background: ${surface_hover};
        border-color: ${border_hover};
        color: ${text_primary};
    }
    QPushButton#clearChatButton:disabled {
        color: ${text_disabled};
        border-color: ${border_soft};
    }
    QScrollArea#conversationScroll {
        background: transparent;
        border: none;
    }
    QFrame#emptyConversation {
        background: transparent;
        border: none;
    }
    QWidget#emptyContent {
        background: transparent;
    }
    QLabel#emptyIcon {
        padding-bottom: 8px;
    }
    QLabel#emptyTitle {
        color: ${text_primary};
        font-size: 24px;
        font-weight: ${font_weight_semibold};
    }
    QLabel#emptySubtitle {
        color: ${text_muted};
        font-size: 14px;
        font-weight: ${font_weight_regular};
    }
    QPushButton[chip="true"],
    QPushButton[filterChip="true"] {
        background: ${surface};
        border: 1px solid ${border_soft};
        color: ${text_secondary};
        min-height: 30px;
        padding: 0 12px;
        border-radius: 15px;
        font-size: ${font_chip_px}px;
        font-weight: ${font_weight_regular};
    }
    QPushButton[chip="true"]:hover,
    QPushButton[filterChip="true"]:hover {
        background: ${surface_hover};
        border-color: ${border_hover};
        color: ${text_primary};
    }
    QFrame#userBubble {
        background: ${user_bubble};
        border: 1px solid ${border_soft};
        border-radius: 18px;
    }
    QLabel#userBubbleText {
        color: ${text_primary};
    }
    QFrame#assistantCard {
        background: transparent;
        border: none;
        border-radius: 0px;
    }
    QFrame#promptShell {
        background: ${surface};
        border: 1px solid ${border_subtle};
        border-radius: 22px;
    }
    QTextEdit#promptInput {
        background: transparent;
        border: none;
        padding: 8px 4px 8px 4px;
        min-height: 36px;
        font-size: ${font_input_px}px;
        font-weight: ${font_weight_regular};
        color: #1E293B;
        selection-background-color: ${selection_bg};
    }
    QTextEdit#promptInput:focus {
        border: none;
    }
    QToolButton#plusButton,
    QToolButton#engineButton {
        background: ${surface};
        border: 1px solid ${border_soft};
        color: ${text_primary};
        border-radius: 16px;
        padding: 6px 12px;
        font-size: ${font_chip_px}px;
        min-height: 18px;
    }
    QToolButton#plusButton {
        min-width: 32px;
        max-width: 32px;
        min-height: 32px;
        max-height: 32px;
        padding: 0;
        border-radius: 16px;
    }
    QToolButton#plusButton:hover,
    QToolButton#engineButton:hover {
        background: ${surface_hover};
        border-color: ${border_hover};
    }
    QPushButton#sendButton {
        background: ${send_bg};
        color: #FFFFFF;
        border: none;
        border-radius: 18px;
        min-width: 92px;
        min-height: 40px;
        padding: 0 16px;
        font-size: ${font_button_px}px;
        font-weight: ${font_weight_semibold};
    }
    QPushButton#sendButton:hover {
        background: ${send_bg_hover};
    }
    QPushButton#sendButton[stopMode="true"] {
        background: ${send_bg};
        border-radius: 20px;
        min-width: 40px;
        max-width: 40px;
        min-height: 40px;
        max-height: 40px;
        padding: 0px;
        font-size: 13px;
        font-weight: ${font_weight_semibold};
    }
    QPushButton#sendButton[stopMode="true"]:hover {
        background: ${send_bg_hover};
    }
    QMenu {
        background: ${surface};
        border: 1px solid ${border_subtle};
        border-radius: 12px;
        padding: 8px;
    }
    QMenu::item {
        padding: 8px 12px;
        border-radius: 8px;
        color: ${text_primary};
    }
    QMenu::item:selected {
        background: ${surface_hover};
    }
    QWidget#reportsRoot QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 2px 0 2px 0;
    }
    QWidget#reportsRoot QScrollBar::handle:vertical {
        background: ${scrollbar_handle};
        border-radius: 5px;
        min-height: 30px;
    }
    QWidget#reportsRoot QScrollBar::add-line:vertical,
    QWidget#reportsRoot QScrollBar::sub-line:vertical {
        height: 0;
    }
    """
)


def _scaled_font(value: int) -> str:
    return str(int(round(float(value) * REPORTS_FONT_SCALE)))


def build_reports_style_context() -> ReportStyleContext:
    values: Dict[str, str] = {
        "page_bg": "#F7F7F8",
        "surface": COLORS.get("color_surface", "#FFFFFF"),
        "surface_hover": "#F8FAFC",
        "border_soft": "rgba(15, 23, 42, 0.08)",
        "border_subtle": "rgba(15, 23, 42, 0.10)",
        "border_hover": "#D7DEE8",
        "hover_tint": "rgba(17, 24, 39, 0.06)",
        "user_bubble": "#ECECF1",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "text_muted": "#64748B",
        "text_disabled": "#94A3B8",
        "accent": COLORS.get("color_secondary", "#2B7DE9"),
        "accent_hover": "#3B82F6",
        "send_bg": "#10182B",
        "send_bg_hover": "#1A2740",
        "selection_bg": "#DBEAFE",
        "scrollbar_handle": "rgba(100, 116, 139, 0.28)",
        "font_ui_stack": TYPOGRAPHY.get("font_ui_stack", '"Inter", sans-serif'),
        "font_page_title_px": _scaled_font(TYPOGRAPHY.get("font_page_title_px", 24)),
        "font_section_title_px": _scaled_font(TYPOGRAPHY.get("font_section_title_px", 16)),
        "font_body_px": _scaled_font(TYPOGRAPHY.get("font_body_px", 13)),
        "font_secondary_px": _scaled_font(TYPOGRAPHY.get("font_secondary_px", 12)),
        "font_caption_px": _scaled_font(TYPOGRAPHY.get("font_caption_px", 11)),
        "font_button_px": _scaled_font(TYPOGRAPHY.get("font_button_px", 13)),
        "font_chip_px": _scaled_font(TYPOGRAPHY.get("font_chip_px", 12)),
        "font_input_px": _scaled_font(13),
        "font_weight_regular": str(TYPOGRAPHY.get("font_weight_regular", 400)),
        "font_weight_medium": str(TYPOGRAPHY.get("font_weight_medium", 500)),
        "font_weight_semibold": str(TYPOGRAPHY.get("font_weight_semibold", 600)),
    }
    return ReportStyleContext(values=values)


def build_reports_stylesheet() -> str:
    return REPORTS_STYLE_TEMPLATE.safe_substitute(build_reports_style_context().to_dict())
