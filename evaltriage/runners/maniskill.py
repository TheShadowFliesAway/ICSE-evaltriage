"""ManiSkill runner using real environments and policies."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from ..runtime import base_env
from ..schemas import CostRecord, EpisodeRecord, InjectionOperator, RunMetrics, RunRequest, RuntimeEnvManifest
from .base import RunnerExecutionError, RunnerResult


SUPPORTED_TASKS = {"PickCube-v1", "StackCube-v1", "PegInsertionSide-v1", "PushCube-v1"}


def run_maniskill(request: RunRequest, raw_dir: Path, logs_path: Path) -> RunnerResult:
    if request.suite not in SUPPORTED_TASKS:
        raise RuntimeError(f"unsupported ManiSkill task: {request.suite}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    worker_output = raw_dir / "maniskill_result.json"
    worker = Path(__file__).with_name("maniskill_worker.py")
    command = [
        "conda",
        "run",
        "-n",
        request.maniskill_env,
        "python",
        str(worker),
        "--task",
        request.suite,
        "--obs-mode",
        str(request.obs_mode),
        "--control-policy",
        str(request.control_policy),
        "--seed",
        str(request.seed),
        "--episodes",
        str(request.episodes),
        "--output",
        str(worker_output),
    ]
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_scale_multiplier:
        command.extend(["--action-scale-multiplier", str(request.injection.params["multiplier"])])
    if request.injection.enabled and request.injection.operator == InjectionOperator.reset_disable_fixed_init_state:
        command.extend(["--reset-seed-offset", str(request.injection.params["seed_offset"])])
    start = time.time()
    env = base_env("0")
    with logs_path.open("w") as logs:
        proc = subprocess.run(command, env=env, stdout=logs, stderr=subprocess.STDOUT, text=True)
    wall = time.time() - start
    if proc.returncode != 0:
        raise RunnerExecutionError(
            f"ManiSkill worker failed with exit code {proc.returncode}; see {logs_path}",
            command=command,
            exit_code=proc.returncode,
            stage="evaluation",
            failure_kind="process_exit",
            cost=CostRecord(wall_clock_s=wall, gpu_minutes=wall / 60.0),
        )
    if not worker_output.exists():
        raise RuntimeError(f"ManiSkill worker did not produce {worker_output}")
    payload = json.loads(worker_output.read_text())
    episodes = [
        EpisodeRecord(
            episode_id=ep["episode_id"],
            task_suite=request.suite,
            task_id=request.task_ids[0],
            seed=ep["seed"],
            success=ep["success"],
            reward=ep["reward"],
            num_steps=ep["num_steps"],
            termination_reason=ep["termination_reason"],
            behavior_tags=ep.get("behavior_tags", []),
        )
        for ep in payload["episodes"]
    ]
    if len(episodes) != request.episodes:
        raise RuntimeError(f"expected {request.episodes} ManiSkill episodes, got {len(episodes)}")
    num_success = sum(1 for ep in episodes if ep.success)
    metrics = RunMetrics(
        success_rate=num_success / len(episodes) if episodes else None,
        mean_reward=sum(ep.reward or 0.0 for ep in episodes) / len(episodes) if episodes else None,
        num_episodes=len(episodes),
        num_success=num_success,
        num_failure=len(episodes) - num_success,
    )
    return RunnerResult(
        command=command,
        raw_output_path=str(worker_output),
        episodes=episodes,
        metrics=metrics,
        cost=CostRecord(wall_clock_s=wall, gpu_minutes=wall / 60.0),
        benchmark="maniskill",
        runtime_env=RuntimeEnvManifest.model_validate(payload.get("runtime_env", {})),
    )
