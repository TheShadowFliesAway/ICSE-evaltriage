"""Manifest-diff heuristic baseline."""

from __future__ import annotations

from ..schemas import BaselineMethodResult, ManifestDiff


def manifest_diff_heuristic(diff: ManifestDiff) -> BaselineMethodResult:
    factors = []
    for entry in diff.entries:
        if entry.factor and entry.factor not in factors:
            factors.append(entry.factor)
    return BaselineMethodResult(
        method="manifest_diff_heuristic",
        top_factors=factors[:3] or None,
        confidence=0.5 if factors else 0.0,
        evidence=[entry.path for entry in diff.entries[:10]],
        not_applicable_reason=None if factors else "no attributable manifest diff",
    )
