"""Case-level orchestration over real run outputs."""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from .baselines.manifest_diff import manifest_diff_heuristic
from .baselines.naive_statistical import naive_statistical_gate
from .baselines.no_episode_evidence import no_episode_evidence_judgment
from .baselines.no_replay import no_replay_judgment
from .baselines.logs_only_failure_regex import logs_only_failure_regex
from .baselines.rerun_k import rerun_k
from .baselines.single_run import single_run_judgment
from .config import load_config, load_thresholds
from .detection.deviation import detect_deviation, detect_failure_deviation, detect_repeated_run_instability
from .diagnosis.attribution import diagnose_case
from .io import read_json, read_jsonl, write_json
from .manifest.diff import diff_manifests
from .paths import RunPaths, ensure_output_root, case_paths, run_paths
from .replay.planner import plan_replay
from .runners.executor import execute_run
from .schemas import (
    ArtifactSplit,
    BaselinesReport,
    CaseConfig,
    CaseRecord,
    CostRecord,
    CaseFamily,
    DeviationSymptom,
    EpisodeRecord,
    ExecutionStatus,
    FailureRecord,
    Manifest,
    RunSummary,
)


def _load_summary(run_id: str, output_root: Path) -> RunSummary:
    path = run_paths(run_id, output_root).summary
    return RunSummary.model_validate(read_json(path))


def _load_manifest(run_id: str, output_root: Path) -> dict:
    return read_json(run_paths(run_id, output_root).manifest)


def _load_episodes(run_id: str, output_root: Path) -> list[EpisodeRecord]:
    return [EpisodeRecord.model_validate(row) for row in read_jsonl(run_paths(run_id, output_root).episodes)]


def _load_failure(run_id: str, output_root: Path) -> FailureRecord | None:
    path = run_paths(run_id, output_root).failure
    if not path.exists():
        return None
    return FailureRecord.model_validate(read_json(path))


def _unsafe_run_paths(run_id: str, output_root: Path) -> RunPaths:
    run_dir = output_root / "runs" / run_id
    return RunPaths(
        run_dir=run_dir,
        manifest=run_dir / "manifest.json",
        episodes=run_dir / "episodes.jsonl",
        summary=run_dir / "summary.json",
        logs=run_dir / "logs.txt",
        failure=run_dir / "failure.json",
        raw_output_dir=run_dir / "raw",
    )


def _load_existing_run(run_id: str, output_root: Path, *, enforce_root: bool = True) -> RunSummary:
    paths = run_paths(run_id, output_root) if enforce_root else _unsafe_run_paths(run_id, output_root)
    missing = [
        path
        for path in [paths.manifest, paths.episodes, paths.summary, paths.logs]
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"existing run {run_id} is missing required outputs: {', '.join(str(p) for p in missing)}")
    Manifest.model_validate(read_json(paths.manifest))
    summary = RunSummary.model_validate(read_json(paths.summary))
    episodes = [EpisodeRecord.model_validate(row) for row in read_jsonl(paths.episodes)]
    if summary.execution_status == ExecutionStatus.completed and not episodes:
        raise RuntimeError(f"existing run {run_id} has no episode records")
    if summary.execution_status == ExecutionStatus.failed:
        if not paths.failure.exists():
            raise RuntimeError(f"existing failed run {run_id} is missing failure.json")
        FailureRecord.model_validate(read_json(paths.failure))
    return summary


def _load_or_execute_run(request, output_root: Path) -> RunSummary:
    paths = run_paths(request.run_id, output_root)
    if not paths.run_dir.exists():
        return execute_run(request.model_copy(update={"output_root": output_root}))
    summary = _load_existing_run(request.run_id, output_root)
    manifest = Manifest.model_validate(_load_manifest(request.run_id, output_root))
    if summary.role != request.role:
        raise RuntimeError(f"existing run {request.run_id} role={summary.role.value}, expected {request.role.value}")
    if summary.platform != request.platform:
        raise RuntimeError(f"existing run {request.run_id} platform={summary.platform.value}, expected {request.platform.value}")
    if summary.task_suite != request.suite:
        raise RuntimeError(f"existing run {request.run_id} suite={summary.task_suite}, expected {request.suite}")
    if summary.task_ids != request.task_ids:
        raise RuntimeError(f"existing run {request.run_id} task_ids={summary.task_ids}, expected {request.task_ids}")
    if summary.seed != request.seed:
        raise RuntimeError(f"existing run {request.run_id} seed={summary.seed}, expected {request.seed}")
    if manifest.injection != request.injection:
        raise RuntimeError(f"existing run {request.run_id} injection does not match requested injection")
    if summary.execution_status == ExecutionStatus.failed and not request.allow_failure:
        raise RuntimeError(f"existing run {request.run_id} failed but request does not allow failure")
    return summary


def _resolve_summaries(run_requests, run_ids: list[str], output_root: Path) -> list[RunSummary]:
    if run_ids:
        return [_load_existing_run(run_id, output_root) for run_id in run_ids]
    return [_load_or_execute_run(r.model_copy(update={"output_root": output_root}), output_root) for r in run_requests]


def validate_case_existing_runs(cfg: CaseConfig, output_root: str | Path, *, enforce_root: bool = True) -> None:
    root = ensure_output_root(output_root) if enforce_root else Path(output_root)
    is_failure_case = cfg.case.deviation_symptom == DeviationSymptom.evaluation_crash_or_failure
    split_ids = [
        ("baseline", cfg.baseline_run_ids),
        ("current", cfg.current_run_ids),
        ("replay", cfg.replay_run_ids),
    ]
    for split, run_ids in split_ids:
        for run_id in run_ids:
            summary = _load_existing_run(run_id, root, enforce_root=enforce_root)
            allowed_roles = {split}
            if cfg.case.artifact_split == ArtifactSplit.smoke:
                if split == "baseline":
                    allowed_roles.update({"smoke", "replay"})
                elif split == "replay":
                    allowed_roles.update({"smoke", "baseline"})
            if summary.role.value not in allowed_roles:
                raise RuntimeError(f"{split}_run_ids contains run {run_id} with role={summary.role.value}")
            if summary.platform != cfg.case.platform:
                raise RuntimeError(
                    f"{split}_run_ids contains run {run_id} with platform={summary.platform.value}, "
                    f"expected {cfg.case.platform.value}"
                )
            if is_failure_case:
                if split == "current" and summary.execution_status != ExecutionStatus.failed:
                    raise RuntimeError(f"failure case current run {run_id} must have execution_status=failed")
                if split in {"baseline", "replay"} and summary.execution_status != ExecutionStatus.completed:
                    raise RuntimeError(f"failure case {split} run {run_id} must have execution_status=completed")
            elif summary.execution_status != ExecutionStatus.completed:
                raise RuntimeError(f"non-failure case {split} run {run_id} must have execution_status=completed")
    if cfg.case.injection_operator is not None and cfg.current_run_ids:
        matched = False
        for run_id in cfg.current_run_ids:
            manifest = Manifest.model_validate(_load_manifest(run_id, root))
            if (
                manifest.injection.enabled
                and manifest.injection.operator == cfg.case.injection_operator
                and manifest.injection.factor == cfg.case.injected_factor
            ):
                matched = True
        if not matched:
            raise RuntimeError(
                f"case {cfg.case.case_id} current_run_ids do not contain a manifest matching "
                f"{cfg.case.injection_operator.value}"
            )


def run_case(config_path: str | Path, output_root: str | Path, rerun_k_value: int, replay_budget: str) -> CaseRecord:
    cfg = load_config(config_path)
    if not isinstance(cfg, CaseConfig):
        raise RuntimeError(f"expected case config: {config_path}")
    output_root = ensure_output_root(output_root)
    paths = case_paths(cfg.case.case_id, output_root)
    if paths.case_dir.exists():
        raise RuntimeError(f"case directory already exists: {paths.case_dir}")
    staging_case_id = f".staging_{cfg.case.case_id}_{uuid.uuid4().hex}"
    staging_paths = case_paths(staging_case_id, output_root)
    staging_paths.case_dir.mkdir(parents=True)
    start = time.time()
    try:
        baseline_summaries = _resolve_summaries(cfg.baseline_runs, cfg.baseline_run_ids, output_root)
        current_summaries = _resolve_summaries(cfg.current_runs, cfg.current_run_ids, output_root)
        replay_summaries = _resolve_summaries(cfg.replay_runs, cfg.replay_run_ids, output_root)

        case = cfg.case.model_copy(
            update={
                "baseline_run_ids": [s.run_id for s in baseline_summaries],
                "current_run_ids": [s.run_id for s in current_summaries],
                "replay_run_ids": [s.run_id for s in replay_summaries],
            }
        )
        thresholds = load_thresholds(cfg.thresholds_path)

        baseline = baseline_summaries[0] if baseline_summaries else None
        current = current_summaries[0] if current_summaries else None
        if baseline and current:
            baseline_episodes = (
                _load_episodes(baseline.run_id, output_root)
                if baseline.execution_status == ExecutionStatus.completed
                else []
            )
            current_episodes = (
                _load_episodes(current.run_id, output_root)
                if current.execution_status == ExecutionStatus.completed
                else []
            )
            first_replay = replay_summaries[0] if replay_summaries else None
            replay_episodes = (
                _load_episodes(first_replay.run_id, output_root)
                if first_replay and first_replay.execution_status == ExecutionStatus.completed
                else None
            )
            if case.case_family == CaseFamily.flaky:
                deviation = detect_repeated_run_instability(
                    case.case_id,
                    baseline_summaries,
                    current_summaries,
                    replay_summaries,
                    thresholds,
                )
            elif case.deviation_symptom == DeviationSymptom.evaluation_crash_or_failure:
                deviation = detect_failure_deviation(case.case_id, baseline, current, first_replay)
            else:
                deviation = detect_deviation(
                    case.case_id,
                    baseline,
                    current,
                    thresholds,
                    baseline_episodes=baseline_episodes,
                    current_episodes=current_episodes,
                    replay_episodes=replay_episodes,
                )
            diff = diff_manifests(
                case.case_id,
                _load_manifest(baseline.run_id, output_root),
                _load_manifest(current.run_id, output_root),
            )
        else:
            raise RuntimeError("case execution requires at least one baseline and one current run")
        plan = plan_replay(case.case_id, deviation, diff, replay_budget)
        diagnosis = diagnose_case(case, deviation, diff, baseline, current, replay_summaries, thresholds)
        current_failure = _load_failure(current.run_id, output_root) if current.execution_status == ExecutionStatus.failed else None
        baseline_results = [
            single_run_judgment(baseline, current, thresholds),
            rerun_k(baseline_summaries + current_summaries, thresholds),
            naive_statistical_gate(baseline_summaries + current_summaries, thresholds),
            manifest_diff_heuristic(diff),
            no_replay_judgment(case, deviation, diff, baseline, current, thresholds),
            no_episode_evidence_judgment(case, baseline, current, replay_summaries, diff, thresholds),
            logs_only_failure_regex(current_failure, thresholds),
        ]
        write_json(staging_paths.case_json, case)
        write_json(staging_paths.deviation, deviation)
        write_json(staging_paths.manifest_diff, diff)
        write_json(staging_paths.replay_plan, plan)
        write_json(staging_paths.diagnosis, diagnosis)
        write_json(staging_paths.baselines, BaselinesReport(case_id=case.case_id, results=baseline_results))
        total_wall = sum((s.cost.wall_clock_s or 0.0) for s in [*baseline_summaries, *current_summaries, *replay_summaries])
        total_gpu = sum((s.cost.gpu_minutes or 0.0) for s in [*baseline_summaries, *current_summaries, *replay_summaries])
        elapsed = time.time() - start
        write_json(
            staging_paths.cost,
            CostRecord(wall_clock_s=total_wall + elapsed, gpu_minutes=total_gpu),
        )
        staging_paths.case_dir.rename(paths.case_dir)
        return case
    except Exception:
        shutil.rmtree(staging_paths.case_dir, ignore_errors=True)
        raise
