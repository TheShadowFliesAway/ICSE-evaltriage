"""Run and summarize the RQ4 GPU1 affected-task replay supplement.

This script keeps the paper matrix fixed and adds measured cost calibration runs
for affected-task replay. It is intentionally experiment-scoped rather than a
general EvalTriage API.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaltriage.config import load_config
from evaltriage.io import read_json, read_jsonl
from evaltriage.paths import DEFAULT_OUTPUT_ROOT, PROJECT_ROOT, run_paths
from evaltriage.runners.executor import execute_run
from evaltriage.schemas import CaseConfig, ExecutionStatus, RunRequest


PAPER_PREFIXES = ("paper_lerobot_full_", "paper_failure_")
OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "metrics" / "rq4_cost_supplement_20260630"
RERUN_K = 3


@dataclass(frozen=True)
class ScheduledRun:
    order: int
    run_id: str
    source_case_id: str
    stage: str


SCHEDULE = [
    ScheduledRun(
        1,
        "rq4_gpu1_aff_action_seed1000",
        "paper_lerobot_full_action_control_mode_goal_tasks0to9_seed1000",
        "pilot",
    ),
    ScheduledRun(
        2,
        "rq4_gpu1_aff_eval_protocol_seed1000",
        "paper_lerobot_full_eval_protocol_episode_length_goal_tasks0to9_seed1000",
        "pilot",
    ),
    ScheduledRun(
        3,
        "rq4_gpu1_aff_harness_seed1000",
        "paper_lerobot_full_harness_batch_size_goal_tasks0to9_seed1000",
        "pilot",
    ),
    ScheduledRun(
        4,
        "rq4_gpu1_aff_reset_seed1000",
        "paper_lerobot_full_reset_disable_init_states_goal_tasks0to9_seed1000",
        "pilot",
    ),
    ScheduledRun(
        5,
        "rq4_gpu1_aff_action_seed2000",
        "paper_lerobot_full_action_control_mode_goal_tasks0to9_seed2000",
        "extension",
    ),
    ScheduledRun(
        6,
        "rq4_gpu1_aff_checkpoint_seed1000",
        "paper_lerobot_full_checkpoint_feature_mismatch_goal_tasks0to9_seed1000",
        "extension",
    ),
    ScheduledRun(
        7,
        "rq4_gpu1_aff_checkpoint_seed2000",
        "paper_lerobot_full_checkpoint_feature_mismatch_goal_tasks0to9_seed2000",
        "extension",
    ),
    ScheduledRun(
        8,
        "rq4_gpu1_aff_eval_protocol_seed2000",
        "paper_lerobot_full_eval_protocol_episode_length_goal_tasks0to9_seed2000",
        "extension",
    ),
    ScheduledRun(
        9,
        "rq4_gpu1_aff_harness_seed2000",
        "paper_lerobot_full_harness_batch_size_goal_tasks0to9_seed2000",
        "extension",
    ),
    ScheduledRun(
        10,
        "rq4_gpu1_aff_observation_seed1000",
        "paper_lerobot_full_observation_state_blackout_goal_tasks0to9_seed1000",
        "extension",
    ),
    ScheduledRun(
        11,
        "rq4_gpu1_aff_observation_seed2000",
        "paper_lerobot_full_observation_state_blackout_goal_tasks0to9_seed2000",
        "extension",
    ),
    ScheduledRun(
        12,
        "rq4_gpu1_aff_reset_seed2000",
        "paper_lerobot_full_reset_disable_init_states_goal_tasks0to9_seed2000",
        "extension",
    ),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def run_summary(output_root: Path, run_id: str) -> dict[str, Any] | None:
    path = run_paths(run_id, output_root).summary
    if not path.exists():
        return None
    return read_json(path)


def artifact_complete(output_root: Path, run_id: str) -> bool:
    paths = run_paths(run_id, output_root)
    if not all(path.exists() for path in [paths.manifest, paths.episodes, paths.summary, paths.logs]):
        return False
    summary = read_json(paths.summary)
    status = summary.get("execution_status")
    if status == ExecutionStatus.failed.value:
        return paths.failure.exists()
    if status != ExecutionStatus.completed.value:
        return False
    return len(read_jsonl(paths.episodes)) > 0


def case_config_path(case_id: str) -> Path:
    return PROJECT_ROOT / "configs" / "cases" / f"{case_id}.yaml"


def load_case_config(case_id: str) -> CaseConfig:
    cfg = load_config(case_config_path(case_id))
    if not isinstance(cfg, CaseConfig):
        raise RuntimeError(f"expected case config for {case_id}")
    return cfg


def case_dir(output_root: Path, case_id: str) -> Path:
    return output_root / "cases" / case_id


def paper_case_ids(output_root: Path) -> list[str]:
    root = output_root / "cases"
    return sorted(path.name for path in root.iterdir() if path.is_dir() and path.name.startswith(PAPER_PREFIXES))


def read_episodes_by_pair(output_root: Path, run_id: str) -> dict[tuple[int, int], dict[str, Any]]:
    rows = read_jsonl(run_paths(run_id, output_root).episodes)
    return {(int(row["task_id"]), int(row["seed"])): row for row in rows if row.get("seed") is not None}


def parse_shifted_pairs(evidence: list[str]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in evidence:
        for task, seed in re.findall(r"task=(\d+)/seed=(\d+)", item):
            out.append((int(task), int(seed)))
    return out


def affected_pairs(output_root: Path, source_case_id: str) -> tuple[list[tuple[int, int]], str]:
    cdir = case_dir(output_root, source_case_id)
    case = read_json(cdir / "case.json")
    deviation = read_json(cdir / "deviation.json")
    baseline_ids = case.get("baseline_run_ids") or []
    current_ids = case.get("current_run_ids") or []
    replay_ids = case.get("replay_run_ids") or []
    if not (baseline_ids and current_ids and replay_ids):
        return [], "missing_run_ids"

    baseline = read_episodes_by_pair(output_root, baseline_ids[0])
    current = read_episodes_by_pair(output_root, current_ids[0])
    replay = read_episodes_by_pair(output_root, replay_ids[0])
    keys = sorted(set(baseline) & set(current) & set(replay))

    success_recovered_current_failed: list[tuple[int, int]] = []
    paired_shift: list[tuple[int, int]] = []
    for key in keys:
        b_success = bool(baseline[key]["success"])
        c_success = bool(current[key]["success"])
        r_success = bool(replay[key]["success"])
        if b_success and r_success and not c_success:
            success_recovered_current_failed.append(key)
        if b_success == r_success and c_success != b_success:
            paired_shift.append(key)

    metric_name = deviation.get("metric_name")
    if metric_name == "paired_episode_outcome_mismatch_rate":
        pairs = paired_shift or parse_shifted_pairs(deviation.get("evidence") or [])
        return sorted(set(pairs)), "paired_outcome_shift"

    if success_recovered_current_failed:
        return sorted(set(success_recovered_current_failed)), "success_recovered_current_failed"
    if paired_shift:
        return sorted(set(paired_shift)), "paired_outcome_shift_fallback"
    parsed = parse_shifted_pairs(deviation.get("evidence") or [])
    if parsed:
        return sorted(set(parsed)), "evidence_parsed_shift"
    return [], "no_affected_pairs_detected"


def affected_tasks(output_root: Path, source_case_id: str) -> tuple[list[int], list[tuple[int, int]], str]:
    pairs, method = affected_pairs(output_root, source_case_id)
    tasks = sorted({task for task, _seed in pairs})
    if tasks:
        return tasks, pairs, method

    cfg = load_case_config(source_case_id)
    replay = cfg.replay_runs[0]
    return list(replay.task_ids), [], "fallback_full_replay_tasks"


def request_for_schedule(output_root: Path, spec: ScheduledRun) -> tuple[RunRequest, dict[str, Any]]:
    cfg = load_case_config(spec.source_case_id)
    if not cfg.replay_runs:
        raise RuntimeError(f"case {spec.source_case_id} has no replay run template")
    tasks, pairs, method = affected_tasks(output_root, spec.source_case_id)
    template = cfg.replay_runs[0]
    request = template.model_copy(
        update={
            "run_id": spec.run_id,
            "task_ids": tasks,
            "case_id": spec.source_case_id,
            "output_root": output_root,
        }
    )
    metadata = {
        "affected_task_ids": tasks,
        "affected_pairs": pairs,
        "affected_task_derivation": method,
        "planned_affected_episode_count": len(tasks) * template.episodes,
    }
    return request, metadata


def case_observed_episode_counts(output_root: Path, case: dict[str, Any]) -> tuple[int, int]:
    episodes = 0
    failed = 0
    for run_id in case.get("baseline_run_ids", []) + case.get("current_run_ids", []) + case.get("replay_run_ids", []):
        summary = run_summary(output_root, run_id)
        if not summary:
            continue
        if summary.get("execution_status") == ExecutionStatus.failed.value:
            failed += 1
            continue
        episodes_path = run_paths(run_id, output_root).episodes
        if episodes_path.exists():
            episodes += len(read_jsonl(episodes_path))
    return episodes, failed


def calibration_rows(output_root: Path, scheduled: list[ScheduledRun]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in scheduled:
        cfg = load_case_config(spec.source_case_id)
        case = read_json(case_dir(output_root, spec.source_case_id) / "case.json")
        diagnosis = read_json(case_dir(output_root, spec.source_case_id) / "diagnosis.json")
        request, metadata = request_for_schedule(output_root, spec)
        full_replay_id = cfg.replay_runs[0].run_id
        full_summary = run_summary(output_root, full_replay_id) or {}
        summary = run_summary(output_root, spec.run_id) or {}
        status = summary.get("execution_status", "not_run")
        full_gpu = num((full_summary.get("cost") or {}).get("gpu_minutes"))
        aff_gpu = num((summary.get("cost") or {}).get("gpu_minutes"))
        ratio = (aff_gpu / full_gpu) if aff_gpu is not None and full_gpu else None
        top = diagnosis.get("top_factors") or []
        rows.append(
            {
                "order": spec.order,
                "stage": spec.stage,
                "run_id": spec.run_id,
                "source_case_id": spec.source_case_id,
                "case_id": spec.run_id,
                "factor_bucket": case.get("expected_factor"),
                "seed": request.seed,
                "selected_by_validation": case.get("selected_by_validation", False),
                "evaltriage_top1_factor": top[0]["factor"] if top else None,
                "affected_task_ids": metadata["affected_task_ids"],
                "affected_pairs": metadata["affected_pairs"],
                "affected_task_derivation": metadata["affected_task_derivation"],
                "full_task_count": len(full_summary.get("task_ids") or request.task_ids),
                "affected_task_count": len(metadata["affected_task_ids"]),
                "planned_affected_episode_count": metadata["planned_affected_episode_count"],
                "affected_episode_count": (summary.get("metrics") or {}).get("num_episodes"),
                "full_replay_episode_count": (full_summary.get("metrics") or {}).get("num_episodes"),
                "affected_gpu_minutes": aff_gpu,
                "full_replay_gpu_minutes": full_gpu,
                "affected_task_replay_cost_ratio": ratio,
                "wall_clock_minutes": (
                    num((summary.get("cost") or {}).get("wall_clock_s")) / 60.0
                    if (summary.get("cost") or {}).get("wall_clock_s") is not None
                    else None
                ),
                "execution_status": status,
                "artifact_complete": artifact_complete(output_root, spec.run_id),
                "calibration_note": "subset_reseeded_cost_calibration",
            }
        )
    return rows


def source_case_to_calibration(scheduled: list[ScheduledRun]) -> dict[str, ScheduledRun]:
    return {spec.source_case_id: spec for spec in scheduled}


def case_matrix_rows(output_root: Path, scheduled: list[ScheduledRun]) -> list[dict[str, Any]]:
    scheduled_by_case = source_case_to_calibration(scheduled)
    rows: list[dict[str, Any]] = []
    for cid in paper_case_ids(output_root):
        cdir = case_dir(output_root, cid)
        case = read_json(cdir / "case.json")
        deviation = read_json(cdir / "deviation.json") if (cdir / "deviation.json").exists() else {}
        diagnosis = read_json(cdir / "diagnosis.json") if (cdir / "diagnosis.json").exists() else {}
        cost = read_json(cdir / "cost.json") if (cdir / "cost.json").exists() else {}
        top = diagnosis.get("top_factors") or []
        matrix_bucket = (
            "failed_run"
            if case.get("deviation_symptom") == "evaluation_crash_or_failure"
            else "completed_rollout"
        )
        detected = bool(deviation.get("detected"))
        completed_positive = matrix_bucket == "completed_rollout" and detected and bool(top)
        completed_negative = matrix_bucket == "completed_rollout" and not completed_positive
        group = "failed_run" if matrix_bucket == "failed_run" else ("completed_positive" if completed_positive else "completed_negative")

        full_replay_id = (case.get("replay_run_ids") or [None])[0]
        full_summary = run_summary(output_root, full_replay_id) if full_replay_id else None
        full_gpu = num(((full_summary or {}).get("cost") or {}).get("gpu_minutes"))
        full_wall_s = num(((full_summary or {}).get("cost") or {}).get("wall_clock_s"))
        full_replay_episodes = ((full_summary or {}).get("metrics") or {}).get("num_episodes")
        full_task_count = len((full_summary or {}).get("task_ids") or [])

        spec = scheduled_by_case.get(cid)
        affected_task_ids: list[int] = []
        affected_derivation = None
        affected_pairs_value: list[tuple[int, int]] = []
        calibration_run_id = None
        affected_gpu = None
        affected_wall_s = None
        affected_episode_count = None
        cost_source = "not_applicable"
        if completed_positive:
            affected_task_ids, affected_pairs_value, affected_derivation = affected_tasks(output_root, cid)
            calibration_run_id = spec.run_id if spec else None
            if spec:
                summary = run_summary(output_root, spec.run_id)
                if summary and summary.get("execution_status") == ExecutionStatus.completed.value:
                    affected_gpu = num((summary.get("cost") or {}).get("gpu_minutes"))
                    affected_wall_s = num((summary.get("cost") or {}).get("wall_clock_s"))
                    affected_episode_count = (summary.get("metrics") or {}).get("num_episodes")
                    cost_source = "measured_gpu1_subset"
            if affected_gpu is None and full_gpu is not None and full_task_count:
                affected_gpu = full_gpu * (len(affected_task_ids) / full_task_count)
                affected_wall_s = (full_wall_s * (len(affected_task_ids) / full_task_count)) if full_wall_s is not None else None
                affected_episode_count = (
                    int(full_replay_episodes * (len(affected_task_ids) / full_task_count))
                    if full_replay_episodes is not None
                    else None
                )
                cost_source = "estimated_task_fraction"

        ratio = (affected_gpu / full_gpu) if affected_gpu is not None and full_gpu else None
        full_rerun_gpu = RERUN_K * full_gpu if full_gpu is not None else None
        full_rerun_wall_s = RERUN_K * full_wall_s if full_wall_s is not None else None
        observed_episodes, failed_runs = case_observed_episode_counts(output_root, case)
        rows.append(
            {
                "case_id": cid,
                "source_case_id": cid,
                "group": group,
                "matrix_bucket": matrix_bucket,
                "split": case.get("artifact_split"),
                "platform": case.get("platform"),
                "case_family": case.get("case_family"),
                "deviation_symptom": case.get("deviation_symptom"),
                "deviation_detected": detected,
                "expected_status": case.get("expected_status"),
                "evaltriage_status": diagnosis.get("status"),
                "factor_bucket": case.get("expected_factor"),
                "expected_factor": case.get("expected_factor"),
                "evaltriage_top1_factor": top[0]["factor"] if top else None,
                "selected_by_validation": case.get("selected_by_validation", False),
                "seed": (full_summary or {}).get("seed"),
                "observed_episode_count": observed_episodes,
                "observed_failed_run_count": failed_runs,
                "observed_gpu_minutes": cost.get("gpu_minutes"),
                "observed_wall_clock_minutes": (
                    cost.get("wall_clock_s") / 60.0 if cost.get("wall_clock_s") is not None else None
                ),
                "replay_run_id": full_replay_id,
                "full_task_count": full_task_count or None,
                "full_replay_episode_count": full_replay_episodes,
                "full_replay_gpu_minutes": full_gpu,
                "full_replay_wall_clock_minutes": (full_wall_s / 60.0 if full_wall_s is not None else None),
                "full_rerun_k": RERUN_K if full_gpu is not None else None,
                "full_rerun_baseline_gpu_minutes_k3": full_rerun_gpu,
                "full_rerun_baseline_wall_clock_minutes_k3": (
                    full_rerun_wall_s / 60.0 if full_rerun_wall_s is not None else None
                ),
                "calibration_run_id": calibration_run_id,
                "affected_task_ids": affected_task_ids,
                "affected_pairs": affected_pairs_value,
                "affected_task_derivation": affected_derivation,
                "affected_task_count": len(affected_task_ids) if affected_task_ids else None,
                "affected_episode_count": affected_episode_count,
                "affected_gpu_minutes": affected_gpu,
                "affected_wall_clock_minutes": (affected_wall_s / 60.0 if affected_wall_s is not None else None),
                "affected_task_replay_cost_ratio": ratio,
                "savings_vs_full_replay": (1.0 - ratio) if ratio is not None else None,
                "savings_vs_rerun_k3": (
                    1.0 - (affected_gpu / full_rerun_gpu)
                    if affected_gpu is not None and full_rerun_gpu
                    else None
                ),
                "cost_source": cost_source,
            }
        )
    return rows


def summarize_group(rows: list[dict[str, Any]], group: str) -> dict[str, Any]:
    subset = rows if group == "all_paper" else [row for row in rows if row["group"] == group]
    ratios = [num(row.get("affected_task_replay_cost_ratio")) for row in subset]
    ratios = [value for value in ratios if value is not None]
    observed_gpu = [num(row.get("observed_gpu_minutes")) for row in subset]
    observed_gpu = [value for value in observed_gpu if value is not None]
    observed_wall = [num(row.get("observed_wall_clock_minutes")) for row in subset]
    observed_wall = [value for value in observed_wall if value is not None]
    affected_gpu = [num(row.get("affected_gpu_minutes")) for row in subset]
    affected_gpu = [value for value in affected_gpu if value is not None]
    return {
        "group": group,
        "n_cases": len(subset),
        "n_measured_affected_replay": sum(1 for row in subset if row.get("cost_source") == "measured_gpu1_subset"),
        "n_estimated_affected_replay": sum(1 for row in subset if row.get("cost_source") == "estimated_task_fraction"),
        "observed_gpu_minutes_mean": mean(observed_gpu),
        "observed_gpu_minutes_median": median(observed_gpu),
        "observed_wall_clock_minutes_mean": mean(observed_wall),
        "observed_wall_clock_minutes_median": median(observed_wall),
        "affected_gpu_minutes_mean": mean(affected_gpu),
        "affected_gpu_minutes_median": median(affected_gpu),
        "affected_task_replay_cost_ratio_mean": mean(ratios),
        "affected_task_replay_cost_ratio_median": median(ratios),
    }


def summary_rows(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [summarize_group(matrix_rows, group) for group in ["completed_positive", "completed_negative", "failed_run", "all_paper"]]


def ratio_by_bucket_rows(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in matrix_rows:
        if row["group"] != "completed_positive":
            continue
        if row.get("affected_task_replay_cost_ratio") is None:
            continue
        groups.setdefault(row.get("factor_bucket") or "unknown", []).append(row)
    out: list[dict[str, Any]] = []
    for bucket, rows in sorted(groups.items()):
        ratios = [num(row.get("affected_task_replay_cost_ratio")) for row in rows]
        ratios = [value for value in ratios if value is not None]
        affected_counts = [num(row.get("affected_task_count")) for row in rows]
        affected_counts = [value for value in affected_counts if value is not None]
        out.append(
            {
                "factor_bucket": bucket,
                "n_cases": len(rows),
                "n_measured_affected_replay": sum(1 for row in rows if row.get("cost_source") == "measured_gpu1_subset"),
                "n_estimated_affected_replay": sum(1 for row in rows if row.get("cost_source") == "estimated_task_fraction"),
                "affected_task_count_mean": mean(affected_counts),
                "affected_task_replay_cost_ratio_mean": mean(ratios),
                "affected_task_replay_cost_ratio_median": median(ratios),
            }
        )
    return out


CALIBRATION_FIELDS = [
    "order",
    "stage",
    "run_id",
    "source_case_id",
    "case_id",
    "factor_bucket",
    "seed",
    "selected_by_validation",
    "evaltriage_top1_factor",
    "affected_task_ids",
    "affected_pairs",
    "affected_task_derivation",
    "full_task_count",
    "affected_task_count",
    "planned_affected_episode_count",
    "affected_episode_count",
    "full_replay_episode_count",
    "affected_gpu_minutes",
    "full_replay_gpu_minutes",
    "affected_task_replay_cost_ratio",
    "wall_clock_minutes",
    "execution_status",
    "artifact_complete",
    "calibration_note",
]


CASE_MATRIX_FIELDS = [
    "case_id",
    "source_case_id",
    "group",
    "matrix_bucket",
    "split",
    "platform",
    "case_family",
    "deviation_symptom",
    "deviation_detected",
    "expected_status",
    "evaltriage_status",
    "factor_bucket",
    "expected_factor",
    "evaltriage_top1_factor",
    "selected_by_validation",
    "seed",
    "observed_episode_count",
    "observed_failed_run_count",
    "observed_gpu_minutes",
    "observed_wall_clock_minutes",
    "replay_run_id",
    "full_task_count",
    "full_replay_episode_count",
    "full_replay_gpu_minutes",
    "full_replay_wall_clock_minutes",
    "full_rerun_k",
    "full_rerun_baseline_gpu_minutes_k3",
    "full_rerun_baseline_wall_clock_minutes_k3",
    "calibration_run_id",
    "affected_task_ids",
    "affected_pairs",
    "affected_task_derivation",
    "affected_task_count",
    "affected_episode_count",
    "affected_gpu_minutes",
    "affected_wall_clock_minutes",
    "affected_task_replay_cost_ratio",
    "savings_vs_full_replay",
    "savings_vs_rerun_k3",
    "cost_source",
]


def write_outputs(output_root: Path, output_dir: Path, scheduled: list[ScheduledRun], status: dict[str, Any]) -> None:
    calibration = calibration_rows(output_root, scheduled)
    matrix = case_matrix_rows(output_root, scheduled)
    write_csv(output_dir / "rq4_affected_task_replay_calibration.csv", calibration, CALIBRATION_FIELDS)
    write_csv(output_dir / "rq4_cost_case_matrix.csv", matrix, CASE_MATRIX_FIELDS)
    write_csv(output_dir / "rq4_cost_summary.csv", summary_rows(matrix))
    write_csv(output_dir / "rq4_cost_ratio_by_bucket.csv", ratio_by_bucket_rows(matrix))
    write_json(output_dir / "rq4_gpu1_supplement_status.json", status)


def capture_nvidia_smi(output_dir: Path, label: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / f"nvidia_smi_{label}.txt").open("w") as f:
        subprocess.run(["nvidia-smi"], stdout=f, stderr=subprocess.STDOUT, text=True, check=False)


def ensure_no_existing_dirty_collision(output_root: Path, scheduled: list[ScheduledRun]) -> None:
    bad: list[str] = []
    for spec in scheduled:
        paths = run_paths(spec.run_id, output_root)
        if paths.run_dir.exists() and not artifact_complete(output_root, spec.run_id):
            bad.append(str(paths.run_dir))
    if bad:
        raise RuntimeError("existing incomplete RQ4 run directories would block execution: " + ", ".join(bad))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--gpu", default="1", help="physical CUDA device id for RQ4 runs")
    parser.add_argument("--max-pilot-seconds", type=float, default=3600.0)
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force-extension", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    output_dir = args.output_dir.resolve()
    os.environ["EVALTRIAGE_CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)

    scheduled = SCHEDULE
    ensure_no_existing_dirty_collision(output_root, scheduled)
    status: dict[str, Any] = {
        "output_root": str(output_root),
        "output_dir": str(output_dir),
        "gpu": str(args.gpu),
        "max_pilot_seconds": args.max_pilot_seconds,
        "pilot_only": args.pilot_only,
        "plan_only": args.plan_only,
        "force_extension": args.force_extension,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "events": [],
    }

    write_outputs(output_root, output_dir, scheduled, status)
    if args.plan_only:
        print(f"wrote plan/estimated outputs to {output_dir}")
        return

    capture_nvidia_smi(output_dir, "before")

    pilot_specs = [spec for spec in scheduled if spec.stage == "pilot"]
    extension_specs = [spec for spec in scheduled if spec.stage == "extension"]
    executed_specs: list[ScheduledRun] = []

    for spec in pilot_specs:
        run_one(output_root, output_dir, scheduled, status, spec)
        executed_specs.append(spec)

    pilot_rows = calibration_rows(output_root, pilot_specs)
    pilot_seconds = sum(
        (num(row.get("wall_clock_minutes")) or 0.0) * 60.0
        for row in pilot_rows
        if row.get("execution_status") == ExecutionStatus.completed.value
    )
    pilot_complete = all(bool(row.get("artifact_complete")) for row in pilot_rows)
    status["pilot_wall_clock_seconds"] = pilot_seconds
    status["pilot_artifacts_complete"] = pilot_complete

    should_extend = args.force_extension or (not args.pilot_only and pilot_complete and pilot_seconds <= args.max_pilot_seconds)
    status["extension_enabled"] = should_extend
    if should_extend:
        for spec in extension_specs:
            run_one(output_root, output_dir, scheduled, status, spec)
            executed_specs.append(spec)
    else:
        status["events"].append(
            {
                "event": "extension_skipped",
                "reason": "pilot_only_or_gate_not_satisfied",
                "pilot_wall_clock_seconds": pilot_seconds,
                "pilot_artifacts_complete": pilot_complete,
            }
        )
        write_outputs(output_root, output_dir, scheduled, status)

    capture_nvidia_smi(output_dir, "after")
    status["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    status["executed_or_reused_runs"] = [spec.run_id for spec in executed_specs]
    write_outputs(output_root, output_dir, scheduled, status)
    print(f"RQ4 GPU1 supplement complete; outputs: {output_dir}")


def run_one(
    output_root: Path,
    output_dir: Path,
    scheduled: list[ScheduledRun],
    status: dict[str, Any],
    spec: ScheduledRun,
) -> None:
    if artifact_complete(output_root, spec.run_id):
        summary = run_summary(output_root, spec.run_id) or {}
        status["events"].append(
            {
                "event": "reuse_existing_run",
                "run_id": spec.run_id,
                "execution_status": summary.get("execution_status"),
            }
        )
        write_outputs(output_root, output_dir, scheduled, status)
        print(f"[reuse] {spec.run_id}")
        return

    request, metadata = request_for_schedule(output_root, spec)
    status["events"].append(
        {
            "event": "start_run",
            "run_id": spec.run_id,
            "source_case_id": spec.source_case_id,
            "affected_task_ids": metadata["affected_task_ids"],
        }
    )
    write_outputs(output_root, output_dir, scheduled, status)
    print(f"[run] {spec.run_id} tasks={metadata['affected_task_ids']}")
    start = time.time()
    try:
        summary = execute_run(request)
    except Exception as exc:
        status["events"].append(
            {
                "event": "run_failed",
                "run_id": spec.run_id,
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "elapsed_seconds": time.time() - start,
            }
        )
        write_outputs(output_root, output_dir, scheduled, status)
        raise
    status["events"].append(
        {
            "event": "finish_run",
            "run_id": spec.run_id,
            "execution_status": summary.execution_status.value,
            "elapsed_seconds": time.time() - start,
            "wall_clock_s": summary.cost.wall_clock_s,
            "gpu_minutes": summary.cost.gpu_minutes,
        }
    )
    write_outputs(output_root, output_dir, scheduled, status)
    print(f"[done] {spec.run_id} wall={summary.cost.wall_clock_s:.1f}s gpu={summary.cost.gpu_minutes:.2f}m")


if __name__ == "__main__":
    main()
