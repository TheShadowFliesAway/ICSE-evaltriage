"""Aggregate-only ablation using formal detection and diagnosis without episode evidence."""

from __future__ import annotations

from ..detection.deviation import detect_success_rate_deviation
from ..diagnosis.attribution import diagnose_case
from ..schemas import BaselineMethodResult, CaseRecord, ExecutionStatus, ManifestDiff, RunSummary, ThresholdsConfig


def no_episode_evidence_judgment(
    case: CaseRecord,
    baseline: RunSummary,
    current: RunSummary,
    replays: list[RunSummary],
    manifest_diff: ManifestDiff,
    thresholds: ThresholdsConfig,
) -> BaselineMethodResult:
    if baseline.execution_status != ExecutionStatus.completed or current.execution_status != ExecutionStatus.completed:
        return BaselineMethodResult(
            method="no_episode_evidence",
            not_applicable_reason="aggregate rollout ablation requires completed baseline and current runs",
        )
    deviation = detect_success_rate_deviation(case.case_id, baseline, current, thresholds)
    diagnosis = diagnose_case(case, deviation, manifest_diff, baseline, current, replays, thresholds)
    return BaselineMethodResult(
        method="no_episode_evidence",
        status=diagnosis.status,
        top_factors=[item.factor for item in diagnosis.top_factors],
        confidence=diagnosis.status_confidence,
        evidence=[
            "success-rate-only detection; paired episode evidence omitted",
            *deviation.evidence,
            *diagnosis.decision_rules_fired,
            *(diagnosis.unknown_reason and [diagnosis.unknown_reason] or []),
        ],
    )
