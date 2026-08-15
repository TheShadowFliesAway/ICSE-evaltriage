"""Diagnosis report serialization helpers."""

from __future__ import annotations

from pathlib import Path

from ..io import write_json
from ..schemas import Diagnosis


def write_diagnosis(path: Path, diagnosis: Diagnosis) -> None:
    write_json(path, diagnosis)
