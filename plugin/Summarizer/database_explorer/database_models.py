# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DatabaseObject:
    schema: str
    name: str
    object_type: str = "unknown"
    geometry_column: str = ""
    comment: str = ""
    is_vector: bool = False
    provider_key: str = ""
    uri: str = ""


@dataclass
class DatabaseGroup:
    name: str
    objects: List[DatabaseObject] = field(default_factory=list)


@dataclass
class DatabaseConnectionSnapshot:
    connection_meta: Dict
    provider_key: str = ""
    groups: List[DatabaseGroup] = field(default_factory=list)
    connected: bool = False
    error_message: str = ""

