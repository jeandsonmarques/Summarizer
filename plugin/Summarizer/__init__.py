# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
import sys


def _install_qt_compat_aliases():
    def alias(container, name, enum_container, enum_name=None):
        if hasattr(container, name):
            return
        try:
            setattr(container, name, getattr(enum_container, enum_name or name))
        except Exception:
            return

    def alias_method(container, old_name, new_name):
        if not hasattr(container, new_name):
            return
        try:
            def wrapper(self, *args, **kwargs):
                return getattr(self, new_name)(*args, **kwargs)

            wrapper.__name__ = old_name
            setattr(container, old_name, wrapper)
        except Exception:
            return

    def alias_point_method(container, old_name, new_name):
        if hasattr(container, old_name) or not hasattr(container, new_name):
            return
        try:
            def wrapper(self):
                point = getattr(self, new_name)()
                try:
                    return point.toPoint()
                except Exception:
                    return point

            wrapper.__name__ = old_name
            setattr(container, old_name, wrapper)
        except Exception:
            return

    try:
        from qgis.PyQt.QtCore import (
            QBuffer,
            QEvent,
            QEventLoop,
            QIODevice,
            QItemSelectionModel,
            QEasingCurve,
            QVariantAnimation,
            Qt,
        )
    except Exception:
        return

    for name in ("InOutCubic", "OutCubic", "OutQuart"):
        alias(QEasingCurve, name, getattr(QEasingCurve, "Type", None))

    for name in (
        "ChildAdded",
        "Close",
        "DragEnter",
        "DragMove",
        "Drop",
        "Enter",
        "FocusIn",
        "FocusOut",
        "Hide",
        "KeyPress",
        "KeyRelease",
        "Leave",
        "MouseButtonDblClick",
        "MouseButtonPress",
        "MouseButtonRelease",
        "MouseMove",
        "Move",
        "ParentChange",
        "Polish",
        "Resize",
        "Show",
        "ToolTip",
        "Wheel",
    ):
        alias(QEvent, name, getattr(QEvent, "Type", None))

    for name in ("ExcludeUserInputEvents",):
        alias(QEventLoop, name, getattr(QEventLoop, "ProcessEventsFlag", None))

    for name in ("ClearAndSelect", "Select"):
        alias(QItemSelectionModel, name, getattr(QItemSelectionModel, "SelectionFlag", None))

    for name in ("ReadOnly", "WriteOnly", "ReadWrite", "Append", "Truncate", "Text", "Unbuffered"):
        alias(QBuffer, name, getattr(QIODevice, "OpenModeFlag", None))

    for name in ("Running", "Stopped"):
        alias(QVariantAnimation, name, getattr(QVariantAnimation, "State", None))

    qt_groups = {
        "AlignmentFlag": (
            "AlignBottom",
            "AlignCenter",
            "AlignHCenter",
            "AlignLeft",
            "AlignRight",
            "AlignTop",
            "AlignVCenter",
        ),
        "ArrowType": ("DownArrow", "LeftArrow", "NoArrow", "RightArrow"),
        "AspectRatioMode": ("KeepAspectRatio",),
        "BrushStyle": ("NoBrush",),
        "CaseSensitivity": ("CaseInsensitive", "CaseSensitive"),
        "CheckState": ("Checked", "Unchecked"),
        "ContextMenuPolicy": ("CustomContextMenu", "DefaultContextMenu"),
        "CursorShape": (
            "ArrowCursor",
            "ClosedHandCursor",
            "CrossCursor",
            "OpenHandCursor",
            "PointingHandCursor",
            "SizeBDiagCursor",
            "SizeFDiagCursor",
            "SizeHorCursor",
            "SizeVerCursor",
            "WaitCursor",
        ),
        "DateFormat": ("ISODate",),
        "DropAction": ("CopyAction", "MoveAction"),
        "FocusPolicy": ("NoFocus", "StrongFocus"),
        "FocusReason": ("MouseFocusReason", "TabFocusReason"),
        "GlobalColor": ("transparent", "yellow"),
        "ItemDataRole": ("DisplayRole", "TextAlignmentRole", "UserRole"),
        "ItemFlag": (
            "ItemIsDragEnabled",
            "ItemIsEnabled",
            "ItemIsSelectable",
            "ItemIsUserCheckable",
            "NoItemFlags",
        ),
        "Key": ("Key_Backspace", "Key_Delete", "Key_Enter", "Key_Escape", "Key_Return", "Key_Space"),
        "KeyboardModifier": ("ControlModifier", "NoModifier", "ShiftModifier"),
        "LayoutDirection": ("RightToLeft",),
        "MatchFlag": ("MatchFixedString",),
        "MouseButton": ("LeftButton", "MiddleButton", "NoButton", "RightButton"),
        "Orientation": ("Horizontal", "Vertical"),
        "PenCapStyle": ("RoundCap",),
        "PenJoinStyle": ("RoundJoin",),
        "PenStyle": ("DashLine", "DotLine", "NoPen", "SolidLine"),
        "ScrollBarPolicy": ("ScrollBarAlwaysOff", "ScrollBarAsNeeded"),
        "TextElideMode": ("ElideRight",),
        "TextFlag": ("TextWordWrap",),
        "TextInteractionFlag": ("NoTextInteraction", "TextSelectableByMouse"),
        "ToolButtonStyle": (
            "ToolButtonIconOnly",
            "ToolButtonTextBesideIcon",
            "ToolButtonTextOnly",
            "ToolButtonTextUnderIcon",
        ),
        "WidgetAttribute": (
            "WA_NoSystemBackground",
            "WA_StyledBackground",
            "WA_TranslucentBackground",
            "WA_TransparentForMouseEvents",
        ),
        "WindowType": (
            "Dialog",
            "FramelessWindowHint",
            "NoDropShadowWindowHint",
            "ToolTip",
            "Window",
            "WindowCloseButtonHint",
            "WindowContextHelpButtonHint",
            "WindowMaximizeButtonHint",
            "WindowMinimizeButtonHint",
            "WindowSystemMenuHint",
            "WindowTitleHint",
        ),
    }
    for group_name, names in qt_groups.items():
        enum_container = getattr(Qt, group_name, None)
        if enum_container is None:
            continue
        for name in names:
            alias(Qt, name, enum_container)

    try:
        from qgis.PyQt.QtGui import (
            QDrag,
            QIcon,
            QImage,
            QKeySequence,
            QMouseEvent,
            QPageSize,
            QPainter,
            QPalette,
            QWheelEvent,
        )
        from qgis.PyQt.QtWidgets import (
            QAbstractItemView,
            QAbstractScrollArea,
            QAbstractSpinBox,
            QColorDialog,
            QDialog,
            QDialogButtonBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGraphicsScene,
            QHeaderView,
            QLayout,
            QLineEdit,
            QListView,
            QMenu,
            QMessageBox,
            QScrollArea,
            QSizePolicy,
            QStyle,
            QToolButton,
        )
    except Exception:
        return

    for cls in (QColorDialog, QDialog, QFileDialog, QMenu, QMessageBox, QDrag):
        alias_method(cls, "exec_", "exec")

    alias_point_method(QMouseEvent, "globalPos", "globalPosition")
    alias_point_method(QWheelEvent, "globalPos", "globalPosition")
    alias_point_method(QWheelEvent, "pos", "position")

    try:
        from qgis.PyQt.QtSql import QSqlQuery

        alias_method(QSqlQuery, "exec_", "exec")
    except Exception:
        pass

    for name in ("Active", "Disabled", "Normal", "Selected"):
        alias(QIcon, name, getattr(QIcon, "Mode", None))
    for name in ("Off", "On"):
        alias(QIcon, name, getattr(QIcon, "State", None))

    for name in ("Format_ARGB32", "Format_ARGB32_Premultiplied"):
        alias(QImage, name, getattr(QImage, "Format", None))

    for name in ("Copy",):
        alias(QKeySequence, name, getattr(QKeySequence, "StandardKey", None))

    for name in ("A4",):
        alias(QPageSize, name, getattr(QPageSize, "PageSizeId", None))

    for name in (
        "AlternateBase",
        "Base",
        "Button",
        "ButtonText",
        "HighlightedText",
        "Text",
        "Window",
        "WindowText",
    ):
        alias(QPalette, name, getattr(QPalette, "ColorRole", None))

    for name in ("Antialiasing", "SmoothPixmapTransform", "TextAntialiasing"):
        alias(QPainter, name, getattr(QPainter, "RenderHint", None))
    alias(QPainter, "HighQualityAntialiasing", getattr(QPainter, "RenderHint", None), "Antialiasing")
    for name in ("CompositionMode_SourceIn",):
        alias(QPainter, name, getattr(QPainter, "CompositionMode", None))

    for name in ("ExtendedSelection", "NoSelection", "SingleSelection"):
        alias(QAbstractItemView, name, getattr(QAbstractItemView, "SelectionMode", None))
    for name in ("SelectItems", "SelectRows"):
        alias(QAbstractItemView, name, getattr(QAbstractItemView, "SelectionBehavior", None))
    for name in ("DragDrop", "DragOnly"):
        alias(QAbstractItemView, name, getattr(QAbstractItemView, "DragDropMode", None))
    for name in ("NoEditTriggers",):
        alias(QAbstractItemView, name, getattr(QAbstractItemView, "EditTrigger", None))
    for name in ("ScrollPerPixel",):
        alias(QAbstractItemView, name, getattr(QAbstractItemView, "ScrollMode", None))

    for name in ("AdjustIgnored", "AdjustToContents", "AdjustToContentsOnFirstShow"):
        alias(QAbstractScrollArea, name, getattr(QAbstractScrollArea, "SizeAdjustPolicy", None))

    for name in ("NoButtons", "PlusMinus", "UpDownArrows"):
        alias(QAbstractSpinBox, name, getattr(QAbstractSpinBox, "ButtonSymbols", None))

    for name in ("ResizeToContents", "Stretch"):
        alias(QHeaderView, name, getattr(QHeaderView, "ResizeMode", None))

    for name in ("NoIndex",):
        alias(QGraphicsScene, name, getattr(QGraphicsScene, "ItemIndexMethod", None))

    for name in ("Adjust", "Fixed"):
        alias(QListView, name, getattr(QListView, "ResizeMode", None))
    for name in ("IconMode", "ListMode"):
        alias(QListView, name, getattr(QListView, "ViewMode", None))
    for name in ("LeftToRight", "TopToBottom"):
        alias(QListView, name, getattr(QListView, "Flow", None))
    for name in ("Free", "Snap", "Static"):
        alias(QListView, name, getattr(QListView, "Movement", None))

    for name in ("LeadingPosition", "TrailingPosition"):
        alias(QLineEdit, name, getattr(QLineEdit, "ActionPosition", None))
    for name in ("NoEcho", "Normal", "Password", "PasswordEchoOnEdit"):
        alias(QLineEdit, name, getattr(QLineEdit, "EchoMode", None))

    for name in ("Expanding", "Fixed", "Ignored", "Maximum", "Minimum", "Preferred"):
        alias(QSizePolicy, name, getattr(QSizePolicy, "Policy", None))

    for name in ("Accepted", "Rejected"):
        alias(QDialog, name, getattr(QDialog, "DialogCode", None))

    for name in ("Box", "HLine", "NoFrame", "Panel", "StyledPanel", "VLine", "WinPanel"):
        alias(QFrame, name, getattr(QFrame, "Shape", None))
    for name in ("Plain", "Raised", "Sunken"):
        alias(QFrame, name, getattr(QFrame, "Shadow", None))

    for name in ("SetDefaultConstraint", "SetFixedSize", "SetMinimumSize", "SetNoConstraint"):
        alias(QLayout, name, getattr(QLayout, "SizeConstraint", None))

    for name in ("NoFrame",):
        alias(QScrollArea, name, getattr(QFrame, "Shape", None))

    for name in ("ShowDirsOnly", "DontResolveSymlinks"):
        alias(QFileDialog, name, getattr(QFileDialog, "Option", None))

    for name in (
        "AllNonFixedFieldsGrow",
        "ExpandingFieldsGrow",
        "FieldsStayAtSizeHint",
    ):
        alias(QFormLayout, name, getattr(QFormLayout, "FieldGrowthPolicy", None))

    standard_buttons = ("Apply", "Cancel", "Close", "Ok")
    roles = ("AcceptRole", "ActionRole", "RejectRole")
    for name in standard_buttons:
        alias(QDialogButtonBox, name, getattr(QDialogButtonBox, "StandardButton", None))
    for name in roles:
        alias(QDialogButtonBox, name, getattr(QDialogButtonBox, "ButtonRole", None))

    for name in ("Cancel", "No", "Ok", "Yes"):
        alias(QMessageBox, name, getattr(QMessageBox, "StandardButton", None))

    for name in ("InstantPopup", "MenuButtonPopup", "DelayedPopup"):
        alias(QToolButton, name, getattr(QToolButton, "ToolButtonPopupMode", None))

    for name in (
        "CE_ItemViewItem",
        "SP_MessageBoxCritical",
        "SP_MessageBoxInformation",
        "SP_MessageBoxQuestion",
        "SP_MessageBoxWarning",
    ):
        alias(QStyle, name, getattr(QStyle, "ControlElement", None))
        alias(QStyle, name, getattr(QStyle, "StandardPixmap", None))
    for name in ("State_HasFocus", "State_Selected"):
        alias(QStyle, name, getattr(QStyle, "StateFlag", None))


_install_qt_compat_aliases()


def _normalized_path(path):
    return os.path.normcase(os.path.normpath(path or ""))


def _is_shadowing_vendor_path(path):
    if not path or not os.path.isdir(path):
        return False

    normalized = _normalized_path(path)
    plugin_marker = os.path.sep + "plugins" + os.path.sep
    has_plugin_path = plugin_marker in normalized
    has_vendor_marker = "vendor_py" in normalized
    has_numpy = os.path.isdir(os.path.join(path, "numpy"))
    has_pandas = os.path.isdir(os.path.join(path, "pandas"))
    has_vendor_package = any((has_numpy, has_pandas))
    return all((has_plugin_path, has_vendor_marker, has_vendor_package))


def _prioritize_qgis_binary_packages():
    """
    Keep vendored numpy/pandas from other plugins behind QGIS site-packages.

    Some plugins inject a vendor directory at the front of sys.path. If that
    vendor folder bundles numpy/pandas, pandas from the QGIS Python runtime can
    crash with a binary incompatibility error.
    """
    shadow_keys = {
        _normalized_path(path)
        for path in sys.path
        if _is_shadowing_vendor_path(path)
    }
    if not shadow_keys:
        return

    preferred_paths = [
        path for path in sys.path if _normalized_path(path) not in shadow_keys
    ]
    deferred_paths = [
        path for path in sys.path if _normalized_path(path) in shadow_keys
    ]
    sys.path[:] = preferred_paths + deferred_paths


def classFactory(iface):
    _prioritize_qgis_binary_packages()
    from .utils.fonts import ensure_ui_fonts_registered

    ensure_ui_fonts_registered()
    from .data_summarizer import Summarizer

    return Summarizer(iface)
