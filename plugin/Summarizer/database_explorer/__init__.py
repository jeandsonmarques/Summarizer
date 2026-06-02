# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

"""Shared database metadata exploration helpers for Summarizer."""

from .database_metadata_service import DatabaseMetadataService, is_supported_driver, provider_key_for_driver
from .database_models import DatabaseConnectionSnapshot, DatabaseGroup, DatabaseObject
__all__ = [
    "DatabaseConnectionSnapshot",
    "DatabaseGroup",
    "DatabaseMetadataService",
    "DatabaseObject",
    "is_supported_driver",
    "provider_key_for_driver",
]
