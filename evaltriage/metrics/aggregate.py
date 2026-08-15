"""Aggregate real case outputs into RQ CSV files."""

from __future__ import annotations

import csv
from pathlib import Path

from ..io import read_json, read_jsonl
from ..schemas import MetricsCaseRow
from .rq2 import status_metrics
from .rq3 import factor_metrics
from .rq4 import cost_metrics


CSV_NAMES = [
    "cases.csv",
    "runs.csv",
    "rq1_factor_matrix.csv",
    "rq2_status_metrics.csv",
    "rq3_factor_metrics.csv",
    "rq4_cost_metrics.csv",
    "failures.csv",
]


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _conclusion(row: dict) -> str:
    if row.get("matrix_bucket") == "failed_run":
        if row.get("deviation_detected") and row.get("expected_factor") == row.get("evaltriage_top1_factor"):
            return "failure-supported"
        if row.get("deviation_detected"):
            return "failure-detected-unknown"
        return "failure-not-detected"
    if row.get("deviation_detected") and row.get("expected_factor") == row.get("evaltriage_top1_factor"):
        return "success candidate"
    if row.get("deviation_detected"):
        return "detected-unknown-or-misclassified"
    return "negative calibration"


def _first_seed(run_rows: list[dict], run_ids: list[str]) -> int | None:
    wanted = set(run_ids)
    for row in run_rows:
        if row.get("run_id") in wanted:
            return row.get("seed")
    return None


def _first_task_set(run_rows: list[dict], run_ids: list[str]) -> str | None:
    wanted = set(run_ids)
    for row in run_rows:
        if row.get("run_id") in wanted:
            return ",".join(str(item) for item in row.get("task_ids", []))
    return None


def aggregate_cases(cases_root: str | Path, output_dir: str | Path) -> Path:
    cases_root = Path(cases_root)
    output_dir = Path(output_dir)
    case_rows: list[dict] = []
    matrix_rows: list[dict] = []
    run_rows: list[dict] = []
    failures: list[dict] = []
    for case_dir in sorted(p for p in cases_root.iterdir() if p.is_dir()):
        try:
            case = read_json(case_dir / "case.json")
            deviation = read_json(case_dir / "deviation.json") if (case_dir / "deviation.json").exists() else {}
            diagnosis = read_json(case_dir / "diagnosis.json")
            cost = read_json(case_dir / "cost.json") if (case_dir / "cost.json").exists() else {}
            top = diagnosis.get("top_factors") or []
            top_factors = [item["factor"] for item in top[:3]]
            expected_factor = case.get("expected_factor")
            factor_rank = None
            if expected_factor and expected_factor in top_factors:
                factor_rank = top_factors.index(expected_factor) + 1
            reciprocal_rank = (1.0 / factor_rank) if factor_rank else None
            episode_count = 0
            failed_run_count = 0
            run_statuses: list[str] = []
            row = {
                "case_id": case["case_id"],
                "config_path": str(case_dir),
                "run_path": str(case_dir),
                "split": case.get("artifact_split"),
                "selected_by_validation": False,
                "platform": case.get("platform"),
                "case_family": case.get("case_family"),
                "deviation_symptom": case.get("deviation_symptom"),
                "deviation_detected": deviation.get("detected"),
                "matrix_bucket": (
                    "failed_run"
                    if case.get("deviation_symptom") == "evaluation_crash_or_failure"
                    else "completed_rollout"
                ),
                "expected_status": case.get("expected_status"),
                "evaltriage_status": diagnosis.get("status"),
                "expected_factor": expected_factor,
                "evaltriage_top1_factor": top[0]["factor"] if top else None,
                "evaltriage_top3_factors": top_factors,
                "factor_rank": factor_rank,
                "reciprocal_rank": reciprocal_rank,
                "status_confidence": diagnosis.get("status_confidence"),
                "gpu_minutes": cost.get("gpu_minutes"),
                "wall_clock_minutes": (cost.get("wall_clock_s") / 60.0) if cost.get("wall_clock_s") else None,
                "rerun_count": len(case.get("replay_run_ids", [])),
            }
            row["unknown_abstention_correct"] = (
                row["expected_status"] == "unknown_engineering_factor"
                and row["evaltriage_status"] == "unknown_engineering_factor"
            )
            row["over_attribution_error"] = (
                row["expected_status"] == "unknown_engineering_factor" and bool(row["evaltriage_top1_factor"])
            )
            for rid in case.get("baseline_run_ids", []) + case.get("current_run_ids", []) + case.get("replay_run_ids", []):
                try:
                    summary_path = cases_root.parent / "runs" / rid / "summary.json"
                    summary = read_json(summary_path)
                    run_rows.append(summary)
                    status = summary.get("execution_status", "completed")
                    run_statuses.append(status)
                    if status == "failed":
                        failed_run_count += 1
                        failure_path = cases_root.parent / "runs" / rid / "failure.json"
                        if failure_path.exists():
                            failures.append({"case_id": case["case_id"], "run_id": rid, **read_json(failure_path)})
                    episodes_path = cases_root.parent / "runs" / rid / "episodes.jsonl"
                    if episodes_path.exists() and status != "failed":
                        episode_count += len(read_jsonl(episodes_path))
                except Exception as exc:
                    failures.append({"case_id": case["case_id"], "run_id": rid, "error": str(exc)})
            row["episode_count"] = episode_count
            row["failed_run_count"] = failed_run_count
            row = MetricsCaseRow.model_validate(row).model_dump(mode="json")
            case_rows.append(row)
            matrix_rows.append(
                {
                    "case_id": row["case_id"],
                    "factor": row.get("expected_factor"),
                    "platform": row.get("platform"),
                    "bucket": row.get("matrix_bucket"),
                    "symptom": row.get("deviation_symptom"),
                    "detected": row.get("deviation_detected"),
                    "diagnosis": row.get("evaltriage_status"),
                    "top1_factor": row.get("evaltriage_top1_factor"),
                    "conclusion": _conclusion(row),
                    "seed": _first_seed(run_rows, case.get("current_run_ids", [])),
                    "task_set": _first_task_set(run_rows, case.get("current_run_ids", [])),
                    "case_path": str(case_dir),
                    "run_statuses": run_statuses,
                }
            )
        except Exception as exc:
            failures.append({"case_id": case_dir.name, "error": str(exc)})
    _write_csv(output_dir / "cases.csv", case_rows)
    _write_csv(output_dir / "runs.csv", run_rows)
    _write_csv(output_dir / "rq1_factor_matrix.csv", matrix_rows)
    _write_csv(output_dir / "rq2_status_metrics.csv", status_metrics(case_rows))
    _write_csv(output_dir / "rq3_factor_metrics.csv", factor_metrics(case_rows))
    _write_csv(output_dir / "rq4_cost_metrics.csv", cost_metrics(case_rows))
    _write_csv(output_dir / "failures.csv", failures)
    return output_dir
