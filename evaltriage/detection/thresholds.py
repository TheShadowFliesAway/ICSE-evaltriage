"""Threshold loading helpers."""

from __future__ import annotations

from pathlib import Path

from ..config import load_thresholds
from ..schemas import ThresholdsConfig


def get_thresholds(path: str | Path | None = None) -> ThresholdsConfig:
    return load_thresholds(path)
