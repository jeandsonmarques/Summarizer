# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from .model_canvas_scene import ModelCanvasScene
from .model_canvas_view import ModelCanvasView

ModelCanvas = ModelCanvasView

__all__ = ["ModelCanvas", "ModelCanvasScene", "ModelCanvasView"]
