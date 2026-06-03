# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
import sys


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
