"""Single-run baseline judgment."""

from __future__ import annotations

from ..schemas import BaselineMethodResult, DiagnosisStatus, RunSummary, ThresholdsConfig


def single_run_judgment(baseline: RunSummary, current: RunSummary, thresholds: ThresholdsConfig) -> BaselineMethodResult:
    b = baseline.metrics.success_rate
    c = current.metrics.success_rate
    if b is None or c is None:
        return BaselineMethodResult(method="single_run_judgment", not_applicable_reason="missing success_rate")
    status = (
        DiagnosisStatus.likely_setup_sensitive_deviation
        if b - c >= thresholds.success_rate_drop_abs
        else DiagnosisStatus.unknown_engineering_factor
    )
    return BaselineMethodResult(
        method="single_run_judgment",
        status=status,
        confidence=0.5,
        evidence=[f"baseline={b} current={c}"],
    )
