"""Formal paper-only ablation aggregation from existing real artifacts."""

from __future__ import annotations

import csv
from pathlib import Path

from ..baselines.logs_only_failure_regex import logs_only_failure_regex
from ..baselines.manifest_diff import manifest_diff_heuristic
from ..baselines.naive_statistical import naive_statistical_gate
from ..baselines.no_episode_evidence import no_episode_evidence_judgment
from ..baselines.no_replay import no_replay_judgment
from ..baselines.rerun_k import rerun_k
from ..baselines.single_run import single_run_judgment
from ..config import load_thresholds
from ..io import read_json
from ..schemas import (
    BaselineMethodResult,
    CaseRecord,
    DeviationRecord,
    Diagnosis,
    ExecutionStatus,
    FailureRecord,
    ManifestDiff,
    RunSummary,
    ThresholdsConfig,
)


METHODS = [
    "evaltriage_full",
    "no_replay",
    "no_episode_evidence",
    "manifest_diff_heuristic",
    "single_run_judgment",
    "rerun_k",
    "naive_statistical_gate",
    "logs_only_failure_regex",
]


CASE_MATRIX_FIELDS = [
    "bucket",
    "case_id",
    "factor",
    "method",
    "applicable",
    "evaltriage_detected",
    "negative_calibration",
    "status",
    "top1_factor",
    "top3_factors",
    "top1_hit",
    "top3_hit",
    "false_attribution_on_negative",
    "not_applicable_reason",
    "evidence_summary",
    "case_path",
]

SUMMARY_FIELDS = [
    "bucket",
    "method",
    "n_cases",
    "n_evaltriage_detected",
    "n_detected_applicable",
    "n_negative_calibration",
    "n_applicable",
    "n_not_applicable",
    "not_applicable_rate",
    "top1_hits_detected",
    "top1_among_detected",
    "top3_hits_detected",
    "top3_among_detected",
    "top1_hits_all_cases",
    "top1_over_all_cases",
    "false_attribution_on_negative",
    "false_attribution_rate_on_negative",
]

MISS_FIELDS = [
    "bucket",
    "case_id",
    "factor",
    "method",
    "reason",
    "status",
    "top1_factor",
    "top3_factors",
    "not_applicable_reason",
    "evidence_summary",
    "case_path",
]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _selected_case_dirs(cases_root: Path, include_prefixes: list[str]) -> list[Path]:
    if not cases_root.exists():
        raise FileNotFoundError(f"cases root not found: {cases_root}")
    prefixes = tuple(include_prefixes)
    case_dirs = sorted(path for path in cases_root.iterdir() if path.is_dir())
    if not prefixes:
        return case_dirs
    return [path for path in case_dirs if path.name.startswith(prefixes)]


def _load_run_summary(cases_root: Path, run_id: str) -> RunSummary:
    summary_path = cases_root.parent / "runs" / run_id / "summary.json"
    return RunSummary.model_validate(read_json(summary_path))


def _load_failure(cases_root: Path, run_id: str) -> FailureRecord | None:
    failure_path = cases_root.parent / "runs" / run_id / "failure.json"
    if not failure_path.exists():
        return None
    return FailureRecord.model_validate(read_json(failure_path))


def _full_result(diagnosis: Diagnosis) -> BaselineMethodResult:
    return BaselineMethodResult(
        method="evaltriage_full",
        status=diagnosis.status,
        top_factors=[item.factor for item in diagnosis.top_factors],
        confidence=diagnosis.status_confidence,
        evidence=[*diagnosis.decision_rules_fired, *(diagnosis.unknown_reason and [diagnosis.unknown_reason] or [])],
    )


def _recompute_results(
    case: CaseRecord,
    deviation: DeviationRecord,
    diff: ManifestDiff,
    diagnosis: Diagnosis,
    baseline: RunSummary,
    current: RunSummary,
    replays: list[RunSummary],
    current_failure: FailureRecord | None,
    thresholds: ThresholdsConfig,
) -> list[BaselineMethodResult]:
    return [
        _full_result(diagnosis),
        no_replay_judgment(case, deviation, diff, baseline, current, thresholds),
        no_episode_evidence_judgment(case, baseline, current, replays, diff, thresholds),
        manifest_diff_heuristic(diff),
        single_run_judgment(baseline, current, thresholds),
        rerun_k([baseline, current], thresholds),
        naive_statistical_gate([baseline, current], thresholds),
        logs_only_failure_regex(current_failure, thresholds),
    ]


def _bucket(case: CaseRecord) -> str:
    return "failed_run" if case.deviation_symptom.value == "evaluation_crash_or_failure" else "completed_rollout"


def _evidence_summary(result: BaselineMethodResult) -> str:
    text = " | ".join(result.evidence[:3])
    return text[:500]


def _case_method_row(
    case_dir: Path,
    case: CaseRecord,
    deviation: DeviationRecord,
    result: BaselineMethodResult,
) -> dict:
    expected = case.expected_factor.value if case.expected_factor else None
    factors = [factor.value for factor in (result.top_factors or [])]
    detected = bool(deviation.detected)
    applicable = result.not_applicable_reason is None
    negative = not detected
    return {
        "bucket": _bucket(case),
        "case_id": case.case_id,
        "factor": expected,
        "method": result.method,
        "applicable": applicable,
        "evaltriage_detected": detected,
        "negative_calibration": negative,
        "status": result.status.value if result.status else "",
        "top1_factor": factors[0] if factors else "",
        "top3_factors": ";".join(factors[:3]),
        "top1_hit": bool(detected and factors and factors[0] == expected),
        "top3_hit": bool(detected and expected in factors[:3]),
        "false_attribution_on_negative": bool(negative and factors),
        "not_applicable_reason": result.not_applicable_reason or "",
        "evidence_summary": _evidence_summary(result),
        "case_path": str(case_dir),
    }


def _summarize_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for bucket in ["all", "completed_rollout", "failed_run"]:
        bucket_rows = rows if bucket == "all" else [row for row in rows if row["bucket"] == bucket]
        for method in METHODS:
            method_rows = [row for row in bucket_rows if row["method"] == method]
            if not method_rows:
                continue
            detected_rows = [row for row in method_rows if row["evaltriage_detected"]]
            detected_applicable_rows = [row for row in detected_rows if row["applicable"]]
            negative_rows = [row for row in method_rows if row["negative_calibration"]]
            top1_hits_detected = sum(1 for row in detected_applicable_rows if row["top1_hit"])
            top3_hits_detected = sum(1 for row in detected_applicable_rows if row["top3_hit"])
            top1_hits_all = sum(1 for row in method_rows if row["top1_hit"])
            false_attr = sum(1 for row in negative_rows if row["false_attribution_on_negative"])
            not_app = sum(1 for row in method_rows if not row["applicable"])
            out.append(
                {
                    "bucket": bucket,
                    "method": method,
                    "n_cases": len(method_rows),
                    "n_evaltriage_detected": len(detected_rows),
                    "n_detected_applicable": len(detected_applicable_rows),
                    "n_negative_calibration": len(negative_rows),
                    "n_applicable": len(method_rows) - not_app,
                    "n_not_applicable": not_app,
                    "not_applicable_rate": not_app / len(method_rows) if method_rows else None,
                    "top1_hits_detected": top1_hits_detected,
                    "top1_among_detected": top1_hits_detected / len(detected_applicable_rows) if detected_applicable_rows else None,
                    "top3_hits_detected": top3_hits_detected,
                    "top3_among_detected": top3_hits_detected / len(detected_applicable_rows) if detected_applicable_rows else None,
                    "top1_hits_all_cases": top1_hits_all,
                    "top1_over_all_cases": top1_hits_all / len(method_rows) if method_rows else None,
                    "false_attribution_on_negative": false_attr,
                    "false_attribution_rate_on_negative": false_attr / len(negative_rows) if negative_rows else None,
                }
            )
    return out


def _miss_rows(rows: list[dict]) -> list[dict]:
    misses: list[dict] = []
    for row in rows:
        reason = ""
        if not row["applicable"]:
            reason = "not_applicable"
        elif row["evaltriage_detected"] and not row["top1_hit"] and not row["top1_factor"]:
            reason = "missed_detected_case_no_top_factor"
        elif row["evaltriage_detected"] and not row["top1_hit"]:
            reason = "wrong_top1_factor"
        elif row["false_attribution_on_negative"]:
            reason = "false_attribution_on_negative"
        if not reason:
            continue
        misses.append(
            {
                "bucket": row["bucket"],
                "case_id": row["case_id"],
                "factor": row["factor"],
                "method": row["method"],
                "reason": reason,
                "status": row["status"],
                "top1_factor": row["top1_factor"],
                "top3_factors": row["top3_factors"],
                "not_applicable_reason": row["not_applicable_reason"],
                "evidence_summary": row["evidence_summary"],
                "case_path": row["case_path"],
            }
        )
    return misses


def aggregate_ablation(
    cases_root: str | Path,
    output_dir: str | Path,
    include_prefixes: list[str],
    thresholds_path: str | Path | None = "configs/thresholds/validation_lerobot_libero.yaml",
) -> Path:
    cases_root = Path(cases_root)
    output_dir = Path(output_dir)
    thresholds = load_thresholds(thresholds_path)
    rows: list[dict] = []
    for case_dir in _selected_case_dirs(cases_root, include_prefixes):
        case = CaseRecord.model_validate(read_json(case_dir / "case.json"))
        deviation = DeviationRecord.model_validate(read_json(case_dir / "deviation.json"))
        diff = ManifestDiff.model_validate(read_json(case_dir / "manifest_diff.json"))
        diagnosis = Diagnosis.model_validate(read_json(case_dir / "diagnosis.json"))
        baseline = _load_run_summary(cases_root, case.baseline_run_ids[0])
        current = _load_run_summary(cases_root, case.current_run_ids[0])
        replays = [_load_run_summary(cases_root, run_id) for run_id in case.replay_run_ids]
        current_failure = _load_failure(cases_root, current.run_id) if current.execution_status == ExecutionStatus.failed else None
        for result in _recompute_results(
            case,
            deviation,
            diff,
            diagnosis,
            baseline,
            current,
            replays,
            current_failure,
            thresholds,
        ):
            rows.append(_case_method_row(case_dir, case, deviation, result))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = _summarize_rows(rows)
    miss_rows = _miss_rows(rows)
    _write_csv(output_dir / "ablation_case_matrix.csv", rows, CASE_MATRIX_FIELDS)
    _write_csv(output_dir / "ablation_summary.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(output_dir / "ablation_miss_analysis.csv", miss_rows, MISS_FIELDS)
    return output_dir
