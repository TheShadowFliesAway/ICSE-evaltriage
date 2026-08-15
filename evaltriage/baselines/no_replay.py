"""No-replay ablation using the same diagnosis rules with replay evidence removed."""

from __future__ import annotations

from ..diagnosis.attribution import diagnose_case
from ..schemas import BaselineMethodResult, CaseRecord, DeviationRecord, ManifestDiff, RunSummary, ThresholdsConfig


def no_replay_judgment(
    case: CaseRecord,
    deviation: DeviationRecord,
    manifest_diff: ManifestDiff,
    baseline: RunSummary,
    current: RunSummary,
    thresholds: ThresholdsConfig,
) -> BaselineMethodResult:
    diagnosis = diagnose_case(case, deviation, manifest_diff, baseline, current, [], thresholds)
    return BaselineMethodResult(
        method="no_replay",
        status=diagnosis.status,
        top_factors=[item.factor for item in diagnosis.top_factors],
        confidence=diagnosis.status_confidence,
        evidence=[
            "same diagnosis rules as EvalTriage with replay summaries removed",
            *diagnosis.decision_rules_fired,
            *(diagnosis.unknown_reason and [diagnosis.unknown_reason] or []),
        ],
    )
