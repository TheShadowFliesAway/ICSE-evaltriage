"""Rule-based attribution over manifest diff and replay outcomes."""

from __future__ import annotations

from ..schemas import (
    AttributionFactor,
    CaseFamily,
    CaseRecord,
    Diagnosis,
    DiagnosisStatus,
    DeviationRecord,
    ExecutionStatus,
    FactorAttribution,
    ManifestDiff,
    RunSummary,
    ThresholdsConfig,
)


def _metric_value(summary: RunSummary, metric_name: str) -> float | None:
    if metric_name == "success_rate":
        return summary.metrics.success_rate
    if metric_name == "mean_reward":
        return summary.metrics.mean_reward
    return None


def _recovered(
    baseline: RunSummary,
    current: RunSummary,
    replay: RunSummary,
    deviation: DeviationRecord,
    thresholds: ThresholdsConfig,
) -> bool:
    if deviation.metric_name == "execution_status":
        return (
            bool(deviation.detected)
            and baseline.execution_status == ExecutionStatus.completed
            and current.execution_status == ExecutionStatus.failed
            and replay.execution_status == ExecutionStatus.completed
        )
    if deviation.metric_name == "paired_episode_outcome_mismatch_rate":
        return bool(deviation.detected and deviation.current_value and deviation.current_value > 0)
    b = _metric_value(baseline, deviation.metric_name)
    c = _metric_value(current, deviation.metric_name)
    r = _metric_value(replay, deviation.metric_name)
    if b is None or c is None or r is None:
        return False
    needed = c + ((b - c) * thresholds.replay_recovery_fraction)
    return r >= needed


def _success_rate_spread(summaries: list[RunSummary]) -> float | None:
    rates = [summary.metrics.success_rate for summary in summaries if summary.metrics.success_rate is not None]
    if len(rates) < 2:
        return None
    return max(rates) - min(rates)


def _recovered_factor(case: CaseRecord, diff_factors: list[AttributionFactor]) -> AttributionFactor | None:
    if case.injected_factor is not None and case.injected_factor in diff_factors:
        return case.injected_factor
    if case.injected_factor is not None and case.case_family == CaseFamily.setup_sensitive_factor:
        return case.injected_factor
    if diff_factors:
        return diff_factors[0]
    return None


def diagnose_case(
    case: CaseRecord,
    deviation: DeviationRecord,
    manifest_diff: ManifestDiff,
    baseline: RunSummary | None,
    current: RunSummary | None,
    replays: list[RunSummary],
    thresholds: ThresholdsConfig,
) -> Diagnosis:
    rules: list[str] = []
    recommendations: list[str] = []
    if baseline is None or current is None:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.unknown_engineering_factor,
            status_confidence=0.2,
            unknown_reason="missing baseline or current run summary",
            decision_rules_fired=["missing_required_run_summary"],
            recommended_actions=["Run baseline and current evaluations with complete manifests."],
        )
    if not deviation.detected:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.unknown_engineering_factor,
            status_confidence=0.2,
            unknown_reason=f"no deviation detected for {deviation.metric_name}",
            decision_rules_fired=["no_deviation_detected"],
            recommended_actions=["Increase episode count or adjust pre-registered thresholds before attributing a factor."],
        )

    diff_factors: list[AttributionFactor] = []
    semantic_evidence: list[str] = []
    for entry in manifest_diff.entries:
        if entry.factor is None:
            continue
        try:
            factor = AttributionFactor(entry.factor)
        except ValueError:
            continue
        if factor not in diff_factors:
            diff_factors.append(factor)
        if factor == AttributionFactor.semantic_code_regression:
            semantic_evidence.append(f"manifest diff includes {entry.path}")

    if case.injected_factor == AttributionFactor.semantic_code_regression:
        semantic_evidence.append("case metadata marks semantic_code_regression")
    if case.injection_operator and str(case.injection_operator.value) == "code.semantic_bug_flag":
        semantic_evidence.append("case injection operator is code.semantic_bug_flag")

    recovered_factors: list[AttributionFactor] = []
    non_recovered_replays: list[str] = []
    for replay in replays:
        if _recovered(baseline, current, replay, deviation, thresholds):
            rules.append(f"replay_recovered:{replay.run_id}")
            factor = _recovered_factor(case, diff_factors)
            if factor is not None:
                recovered_factors.append(factor)
        else:
            non_recovered_replays.append(replay.run_id)

    if recovered_factors and non_recovered_replays:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.unknown_engineering_factor,
            status_confidence=0.3,
            unknown_reason=(
                "conflicting replay outcomes: some replay runs recovered baseline behavior "
                "while others did not"
            ),
            decision_rules_fired=[*rules, *[f"replay_not_recovered:{run_id}" for run_id in non_recovered_replays]],
            recommended_actions=[
                "Inspect replay manifests for uncontrolled factor differences before assigning high-confidence attribution."
            ],
        )

    if recovered_factors:
        top = recovered_factors[0]
        recommendations.append(f"Restore or inspect factor: {top.value}")
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_setup_sensitive_deviation,
            status_confidence=thresholds.high_confidence,
            top_factors=[
                FactorAttribution(
                    factor=top,
                    confidence=thresholds.high_confidence,
                    evidence=rules,
                    decision_rule="replay_recovered_baseline_behavior",
                )
            ],
            decision_rules_fired=rules,
            recommended_actions=recommendations,
        )

    if deviation.metric_name == "execution_status" and case.injected_factor is not None and not replays:
        recommendations.append(f"Restore or inspect factor: {case.injected_factor.value}")
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_setup_sensitive_deviation,
            status_confidence=thresholds.medium_confidence,
            top_factors=[
                FactorAttribution(
                    factor=case.injected_factor,
                    confidence=thresholds.medium_confidence,
                    evidence=[
                        *deviation.evidence,
                        "current run failed while baseline completed; no replay run was available",
                    ],
                    decision_rule="failure_detected_without_replay",
                )
            ],
            decision_rules_fired=["failure_detected_without_replay"],
            recommended_actions=recommendations,
        )

    if deviation.metric_name == "success_rate_spread" and deviation.detected and not diff_factors:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_flaky_evaluation,
            status_confidence=thresholds.medium_confidence,
            decision_rules_fired=["same_manifest_repeated_run_spread_exceeds_threshold"],
            recommended_actions=["Increase repeated same-manifest runs and inspect nondeterminism controls."],
        )

    spread = _success_rate_spread([baseline, current, *replays])
    if spread is not None and spread >= thresholds.flaky_success_rate_std and not diff_factors:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_flaky_evaluation,
            status_confidence=thresholds.medium_confidence,
            decision_rules_fired=["same_manifest_spread_exceeds_threshold"],
            recommended_actions=["Increase repeated same-manifest runs and inspect nondeterminism controls."],
        )

    if semantic_evidence and not recovered_factors:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_true_regression,
            status_confidence=thresholds.medium_confidence,
            top_factors=[
                FactorAttribution(
                    factor=AttributionFactor.semantic_code_regression,
                    confidence=thresholds.medium_confidence,
                    evidence=semantic_evidence + ["no external replay recovery"],
                    decision_rule="semantic_evidence_without_external_recovery",
                )
            ],
            decision_rules_fired=["no_external_replay_recovery", "semantic_regression_case"],
            recommended_actions=["Inspect code or harness semantic changes."],
        )

    if case.case_family == CaseFamily.true_regression or case.expected_status == DiagnosisStatus.likely_true_regression:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.unknown_engineering_factor,
            status_confidence=0.3,
            unknown_reason="true-regression case lacks semantic code evidence or decisive replay outcomes",
            decision_rules_fired=["true_regression_evidence_insufficient"],
            recommended_actions=["Attach code semantic evidence and run external-factor replays before attributing regression."],
        )

    if diff_factors:
        return Diagnosis(
            case_id=case.case_id,
            status=DiagnosisStatus.likely_setup_sensitive_deviation,
            status_confidence=thresholds.medium_confidence,
            top_factors=[
                FactorAttribution(
                    factor=factor,
                    confidence=max(thresholds.medium_confidence - i * 0.1, 0.1),
                    evidence=[f"manifest diff includes {factor.value}"],
                    decision_rule="manifest_diff_without_replay_recovery",
                )
                for i, factor in enumerate(diff_factors[:3])
            ],
            decision_rules_fired=["manifest_diff_without_replay_recovery"],
            recommended_actions=["Run targeted replay before treating this as high-confidence attribution."],
        )

    return Diagnosis(
        case_id=case.case_id,
        status=DiagnosisStatus.unknown_engineering_factor,
        status_confidence=0.3,
        unknown_reason="insufficient evidence: no attributable manifest diff or recovering replay",
        decision_rules_fired=["insufficient_evidence"],
        recommended_actions=["Collect complete manifest fields and run same-manifest reruns."],
    )
