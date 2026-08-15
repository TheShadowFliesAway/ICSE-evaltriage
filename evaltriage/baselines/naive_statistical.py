"""Naive statistical gate baseline."""

from __future__ import annotations

from ..schemas import BaselineMethodResult, DiagnosisStatus, RunSummary, ThresholdsConfig


def naive_statistical_gate(summaries: list[RunSummary], thresholds: ThresholdsConfig) -> BaselineMethodResult:
    rates = [s.metrics.success_rate for s in summaries if s.metrics.success_rate is not None]
    if len(rates) < 2:
        return BaselineMethodResult(method="naive_statistical_gate", not_applicable_reason="requires at least two runs")
    spread = max(rates) - min(rates)
    status = DiagnosisStatus.likely_flaky_evaluation if spread >= thresholds.flaky_success_rate_std else None
    return BaselineMethodResult(
        method="naive_statistical_gate",
        status=status,
        confidence=0.4,
        evidence=[f"success_rate_spread={spread}", f"threshold={thresholds.flaky_success_rate_std}"],
    )
