"""LIBERO injection hook placeholders.

Operators are registered in :mod:`evaltriage.injection.registry`. Actual LIBERO
fault activation is driven by case config and runner overlays; unsupported
operators must fail before writing run outputs.
"""

from __future__ import annotations

from .registry import get_operator_spec

__all__ = ["get_operator_spec"]
