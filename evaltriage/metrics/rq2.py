"""RQ2 status classification metrics over real case artifacts."""

from __future__ import annotations

import csv
from collections import Counter
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
    AttributionFactor,
    BaselineMethodResult,
    CaseFamily,
    CaseRecord,
    DeviationRecord,
    Diagnosis,
    DiagnosisStatus,
    ExecutionStatus,
    FailureRecord,
    ManifestDiff,
    RunSummary,
    ThresholdsConfig,
)


STATUS_CLASSES = [
    DiagnosisStatus.likely_setup_sensitive_deviation.value,
    DiagnosisStatus.likely_flaky_evaluation.value,
    DiagnosisStatus.likely_true_regression.value,
    DiagnosisStatus.unknown_engineering_factor.value,
]

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

CASE_FIELDS = [
    "bucket",
    "case_id",
    "case_family",
    "method",
    "applicable",
    "expected_status",
    "predicted_status",
    "status_correct",
    "deviation_detected",
    "expected_factor",
    "top_factors",
    "false_setup_attribution_on_unknown",
    "flaky_missed",
    "true_regression_missed",
    "not_applicable_reason",
    "evidence_summary",
    "case_path",
]

SUMMARY_FIELDS = [
    "bucket",
    "method",
    "n_cases",
    "n_applicable",
    "n_not_applicable",
    "not_applicable_rate",
    "accuracy",
    "macro_precision",
    "macro_recall",
    "macro_f1",
    "false_setup_attribution_on_unknown",
    "false_setup_attribution_rate_on_unknown",
    "flaky_missed",
    "flaky_miss_rate",
    "true_regression_missed",
    "true_regression_miss_rate",
]

CONFUSION_FIELDS = ["bucket", "method", "expected_status", "predicted_status", "count"]

MISS_FIELDS = [
    "bucket",
    "case_id",
    "case_family",
    "method",
    "reason",
    "expected_status",
    "predicted_status",
    "top_factors",
    "not_applicable_reason",
    "evidence_summary",
    "case_path",
]


def status_metrics(rows: list[dict]) -> list[dict]:
    pairs = [(r.get("expected_status"), r.get("evaltriage_status")) for r in rows if r.get("evaltriage_status")]
    total = len(pairs)
    correct = sum(1 for expected, got in pairs if expected == got)
    unknown = sum(1 for _, got in pairs if got == "unknown_engineering_factor")
    return [
        {"metric": "accuracy", "value": correct / total if total else None, "n": total},
        {"metric": "unknown_rate", "value": unknown / total if total else None, "n": total},
        *[
            {"metric": "confusion", "expected": expected, "predicted": got, "count": count}
            for (expected, got), count in Counter(pairs).items()
        ],
    ]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _selected_case_dirs(cases_root: Path, include_prefixes: list[str]) -> list[Path]:
    prefixes = tuple(include_prefixes)
    return sorted(path for path in cases_root.iterdir() if path.is_dir() and path.name.startswith(prefixes))


def _load_run_summary(cases_root: Path, run_id: str) -> RunSummary:
    return RunSummary.model_validate(read_json(cases_root.parent / "runs" / run_id / "summary.json"))


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


def _manifest_status(diff: ManifestDiff) -> BaselineMethodResult:
    result = manifest_diff_heuristic(diff)
    factors = list(result.top_factors or [])
    status = DiagnosisStatus.unknown_engineering_factor
    if factors:
        status = (
            DiagnosisStatus.likely_true_regression
            if factors[0] == AttributionFactor.semantic_code_regression
            else DiagnosisStatus.likely_setup_sensitive_deviation
        )
    return result.model_copy(
        update={
            "method": "manifest_diff_heuristic",
            "status": status,
            "not_applicable_reason": None,
            "evidence": [*result.evidence, "status inferred from attributable manifest diff"],
        }
    )


def _normalize_status(result: BaselineMethodResult) -> str:
    if result.status is not None:
        return result.status.value
    if result.not_applicable_reason is not None:
        return ""
    return DiagnosisStatus.unknown_engineering_factor.value


def _expected_status(case: CaseRecord, deviation: DeviationRecord) -> str:
    if not deviation.detected and case.case_family == CaseFamily.setup_sensitive_factor:
        return DiagnosisStatus.unknown_engineering_factor.value
    return case.expected_status.value


def _bucket(case: CaseRecord) -> str:
    if case.deviation_symptom.value == "evaluation_crash_or_failure":
        return "failed_run"
    return "completed_rollout"


def _evidence_summary(result: BaselineMethodResult) -> str:
    return " | ".join(result.evidence[:4])[:600]


def _method_results(
    case: CaseRecord,
    deviation: DeviationRecord,
    diff: ManifestDiff,
    diagnosis: Diagnosis,
    baseline_runs: list[RunSummary],
    current_runs: list[RunSummary],
    replay_runs: list[RunSummary],
    current_failure: FailureRecord | None,
    thresholds: ThresholdsConfig,
) -> list[BaselineMethodResult]:
    baseline = baseline_runs[0]
    current = current_runs[0]
    repeated = [*baseline_runs, *current_runs, *replay_runs]
    return [
        _full_result(diagnosis),
        no_replay_judgment(case, deviation, diff, baseline, current, thresholds),
        no_episode_evidence_judgment(case, baseline, current, replay_runs, diff, thresholds),
        _manifest_status(diff),
        single_run_judgment(baseline, current, thresholds),
        rerun_k(repeated, thresholds),
        naive_statistical_gate(repeated, thresholds),
        logs_only_failure_regex(current_failure, thresholds),
    ]


def _case_method_row(
    case_dir: Path,
    case: CaseRecord,
    deviation: DeviationRecord,
    result: BaselineMethodResult,
) -> dict:
    expected = _expected_status(case, deviation)
    predicted = _normalize_status(result)
    applicable = result.not_applicable_reason is None
    top_factors = [factor.value for factor in (result.top_factors or [])]
    false_setup = expected == DiagnosisStatus.unknown_engineering_factor.value and predicted == (
        DiagnosisStatus.likely_setup_sensitive_deviation.value
    )
    flaky_missed = expected == DiagnosisStatus.likely_flaky_evaluation.value and predicted != expected
    true_missed = expected == DiagnosisStatus.likely_true_regression.value and predicted != expected
    return {
        "bucket": _bucket(case),
        "case_id": case.case_id,
        "case_family": case.case_family.value,
        "method": result.method,
        "applicable": applicable,
        "expected_status": expected,
        "predicted_status": predicted,
        "status_correct": bool(applicable and predicted == expected),
        "deviation_detected": deviation.detected,
        "expected_factor": case.expected_factor.value if case.expected_factor else "",
        "top_factors": ";".join(top_factors[:3]),
        "false_setup_attribution_on_unknown": bool(applicable and false_setup),
        "flaky_missed": bool(applicable and flaky_missed),
        "true_regression_missed": bool(applicable and true_missed),
        "not_applicable_reason": result.not_applicable_reason or "",
        "evidence_summary": _evidence_summary(result),
        "case_path": str(case_dir),
    }


def _prf(rows: list[dict], cls: str) -> tuple[float | None, float | None, float | None]:
    applicable = [row for row in rows if row["applicable"]]
    tp = sum(1 for row in applicable if row["expected_status"] == cls and row["predicted_status"] == cls)
    fp = sum(1 for row in applicable if row["expected_status"] != cls and row["predicted_status"] == cls)
    fn = sum(1 for row in applicable if row["expected_status"] == cls and row["predicted_status"] != cls)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _mean(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None


def _summary_rows(rows: list[dict]) -> list[dict]:
    out = []
    for bucket in ["all", "completed_rollout", "failed_run"]:
        bucket_rows = rows if bucket == "all" else [row for row in rows if row["bucket"] == bucket]
        for method in METHODS:
            method_rows = [row for row in bucket_rows if row["method"] == method]
            if not method_rows:
                continue
            applicable = [row for row in method_rows if row["applicable"]]
            class_scores = [_prf(method_rows, cls) for cls in STATUS_CLASSES]
            unknown_rows = [row for row in applicable if row["expected_status"] == DiagnosisStatus.unknown_engineering_factor.value]
            flaky_rows = [row for row in applicable if row["expected_status"] == DiagnosisStatus.likely_flaky_evaluation.value]
            true_rows = [row for row in applicable if row["expected_status"] == DiagnosisStatus.likely_true_regression.value]
            false_setup = sum(1 for row in unknown_rows if row["false_setup_attribution_on_unknown"])
            flaky_missed = sum(1 for row in flaky_rows if row["flaky_missed"])
            true_missed = sum(1 for row in true_rows if row["true_regression_missed"])
            out.append(
                {
                    "bucket": bucket,
                    "method": method,
                    "n_cases": len(method_rows),
                    "n_applicable": len(applicable),
                    "n_not_applicable": len(method_rows) - len(applicable),
                    "not_applicable_rate": (len(method_rows) - len(applicable)) / len(method_rows)
                    if method_rows
                    else None,
                    "accuracy": sum(1 for row in applicable if row["status_correct"]) / len(applicable)
                    if applicable
                    else None,
                    "macro_precision": _mean([score[0] for score in class_scores]),
                    "macro_recall": _mean([score[1] for score in class_scores]),
                    "macro_f1": _mean([score[2] for score in class_scores]),
                    "false_setup_attribution_on_unknown": false_setup,
                    "false_setup_attribution_rate_on_unknown": false_setup / len(unknown_rows)
                    if unknown_rows
                    else None,
                    "flaky_missed": flaky_missed,
                    "flaky_miss_rate": flaky_missed / len(flaky_rows) if flaky_rows else None,
                    "true_regression_missed": true_missed,
                    "true_regression_miss_rate": true_missed / len(true_rows) if true_rows else None,
                }
            )
    return out


def _confusion_rows(rows: list[dict]) -> list[dict]:
    out = []
    for bucket in ["all", "completed_rollout", "failed_run"]:
        bucket_rows = rows if bucket == "all" else [row for row in rows if row["bucket"] == bucket]
        for method in METHODS:
            method_rows = [row for row in bucket_rows if row["method"] == method and row["applicable"]]
            counts = Counter((row["expected_status"], row["predicted_status"]) for row in method_rows)
            for (expected, predicted), count in sorted(counts.items()):
                out.append(
                    {
                        "bucket": bucket,
                        "method": method,
                        "expected_status": expected,
                        "predicted_status": predicted,
                        "count": count,
                    }
                )
    return out


def _miss_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        reason = ""
        if not row["applicable"]:
            reason = "not_applicable"
        elif row["false_setup_attribution_on_unknown"]:
            reason = "false_setup_attribution_on_unknown"
        elif row["flaky_missed"]:
            reason = "flaky_missed"
        elif row["true_regression_missed"]:
            reason = "true_regression_missed"
        elif not row["status_correct"]:
            reason = "wrong_status"
        if not reason:
            continue
        out.append(
            {
                "bucket": row["bucket"],
                "case_id": row["case_id"],
                "case_family": row["case_family"],
                "method": row["method"],
                "reason": reason,
                "expected_status": row["expected_status"],
                "predicted_status": row["predicted_status"],
                "top_factors": row["top_factors"],
                "not_applicable_reason": row["not_applicable_reason"],
                "evidence_summary": row["evidence_summary"],
                "case_path": row["case_path"],
            }
        )
    return out


def aggregate_rq2_status(
    cases_root: str | Path,
    output_dir: str | Path,
    include_prefixes: list[str],
    thresholds_path: str | Path | None = "configs/thresholds/validation_lerobot_libero.yaml",
) -> Path:
    cases_root = Path(cases_root)
    output_dir = Path(output_dir)
    thresholds = load_thresholds(thresholds_path)
    rows = []
    for case_dir in _selected_case_dirs(cases_root, include_prefixes):
        case = CaseRecord.model_validate(read_json(case_dir / "case.json"))
        deviation = DeviationRecord.model_validate(read_json(case_dir / "deviation.json"))
        diff = ManifestDiff.model_validate(read_json(case_dir / "manifest_diff.json"))
        diagnosis = Diagnosis.model_validate(read_json(case_dir / "diagnosis.json"))
        baseline_runs = [_load_run_summary(cases_root, run_id) for run_id in case.baseline_run_ids]
        current_runs = [_load_run_summary(cases_root, run_id) for run_id in case.current_run_ids]
        replay_runs = [_load_run_summary(cases_root, run_id) for run_id in case.replay_run_ids]
        current_failure = None
        for current in current_runs:
            if current.execution_status == ExecutionStatus.failed:
                current_failure = _load_failure(cases_root, current.run_id)
                break
        for result in _method_results(
            case,
            deviation,
            diff,
            diagnosis,
            baseline_runs,
            current_runs,
            replay_runs,
            current_failure,
            thresholds,
        ):
            rows.append(_case_method_row(case_dir, case, deviation, result))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "rq2_status_case_matrix.csv", rows, CASE_FIELDS)
    _write_csv(output_dir / "rq2_status_summary.csv", _summary_rows(rows), SUMMARY_FIELDS)
    _write_csv(output_dir / "rq2_status_confusion.csv", _confusion_rows(rows), CONFUSION_FIELDS)
    _write_csv(output_dir / "rq2_status_miss_analysis.csv", _miss_rows(rows), MISS_FIELDS)
    return output_dir
