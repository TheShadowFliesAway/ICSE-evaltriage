"""Rerun-k baseline over existing run pool."""

from __future__ import annotations

from ..schemas import BaselineMethodResult, DiagnosisStatus, RunSummary, ThresholdsConfig


def rerun_k(summaries: list[RunSummary], thresholds: ThresholdsConfig) -> BaselineMethodResult:
    rates = [s.metrics.success_rate for s in summaries if s.metrics.success_rate is not None]
    if len(rates) < 2:
        return BaselineMethodResult(method="rerun_k", not_applicable_reason="requires at least two runs")
    spread = max(rates) - min(rates)
    status = DiagnosisStatus.likely_flaky_evaluation if spread >= thresholds.flaky_success_rate_std else None
    return BaselineMethodResult(method="rerun_k", status=status, confidence=0.5, evidence=[f"success_rate_spread={spread}"])
