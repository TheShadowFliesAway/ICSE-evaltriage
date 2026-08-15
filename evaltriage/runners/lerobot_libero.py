"""LeRobot + LIBERO runner backed by the real lerobot-eval command."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..paths import LIBERO_CONFIG_PATH, PROJECT_ROOT
from ..runtime import base_env
from ..schemas import CostRecord, EpisodeRecord, InjectionOperator, RunMetrics, RunRequest, RuntimeEnvManifest
from .base import RunnerExecutionError, RunnerResult


def _copy_or_link_checkpoint_file(src: Path, dst: Path) -> None:
    if src.name == "model.safetensors":
        os.symlink(src, dst)
    else:
        shutil.copy2(src, dst)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _set_norm_map_identity(config: dict) -> None:
    steps = config.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError("checkpoint processor config has no steps list")
    for step in steps:
        step_config = step.get("config")
        if isinstance(step_config, dict) and isinstance(step_config.get("norm_map"), dict):
            if "ACTION" in step_config["norm_map"]:
                step_config["norm_map"]["ACTION"] = "IDENTITY"
                return
    raise RuntimeError("checkpoint processor config has no ACTION norm_map")


def _prepare_checkpoint_overlay(request: RunRequest, raw_dir: Path) -> Path:
    if request.policy_path is None:
        raise RuntimeError("checkpoint overlay requires policy_path")
    if request.checkpoint_overlay_mode not in {"postprocessor_action_norm_identity", "remove_processor_stats"}:
        raise RuntimeError(f"unsupported checkpoint overlay mode: {request.checkpoint_overlay_mode}")

    overlay_dir = raw_dir / "checkpoint_overlay"
    overlay_dir.mkdir(parents=True, exist_ok=False)
    for src in request.policy_path.iterdir():
        dst = overlay_dir / src.name
        if src.is_file():
            _copy_or_link_checkpoint_file(src, dst)

    if request.checkpoint_overlay_mode == "remove_processor_stats":
        stats_path = overlay_dir / "policy_postprocessor_step_0_unnormalizer_processor.safetensors"
        if not stats_path.exists():
            raise RuntimeError("checkpoint overlay has no postprocessor stats file to remove")
        stats_path.unlink()
        return overlay_dir

    postprocessor_path = overlay_dir / "policy_postprocessor.json"
    postprocessor = json.loads(postprocessor_path.read_text())
    _set_norm_map_identity(postprocessor)
    _write_json(postprocessor_path, postprocessor)
    return overlay_dir


def _format_task_ids(task_ids: list[int]) -> str:
    return "[" + ",".join(str(task_id) for task_id in task_ids) + "]"


def _lerobot_eval_args(request: RunRequest, raw_dir: Path, policy_path: Path | None = None) -> list[str]:
    assert request.policy_path is not None
    effective_policy_path = policy_path or request.policy_path
    args = [
        "lerobot-eval",
        f"--policy.path={effective_policy_path}",
        "--env.type=libero",
        f"--env.task={request.suite}",
        f"--env.task_ids={_format_task_ids(request.task_ids)}",
        f"--env.obs_type={request.obs_type}",
        f"--env.camera_name={request.libero_camera_name}",
        f"--env.control_mode={request.libero_control_mode}",
        f"--env.init_states={str(request.libero_init_states).lower()}",
        f"--env.observation_height={request.camera_size}",
        f"--env.observation_width={request.camera_size}",
        f"--eval.n_episodes={request.episodes}",
        f"--eval.batch_size={request.eval_batch_size}",
        f"--eval.use_async_envs={str(request.use_async_envs).lower()}",
        f"--policy.compile_model={str(request.compile_model).lower()}",
        "--policy.gradient_checkpointing=false",
        "--policy.device=cuda",
        f"--seed={request.seed}",
        f"--output_dir={raw_dir}",
    ]
    if request.episode_length is not None:
        args.append(f"--env.episode_length={request.episode_length}")
    if request.libero_camera_name_mapping is not None:
        mapping = json.dumps(request.libero_camera_name_mapping, separators=(",", ":"))
        args.append(f"--env.camera_name_mapping={mapping}")
    return args


def _lerobot_command(request: RunRequest, raw_dir: Path) -> list[str]:
    eval_args = _lerobot_eval_args(request, raw_dir)
    command = ["conda", "run", "-n", request.libero_env]
    state_keys = json.dumps(request.libero_state_keys, separators=(",", ":"))
    action_permutation = json.dumps(request.action_dimension_permutation, separators=(",", ":"))
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_drop_postprocessor:
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "action.drop_postprocessor",
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.action_reorder_dimensions:
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "action.reorder_dimensions",
                "--permutation",
                action_permutation,
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.observation_image_flip:
        assert request.libero_image_flip_axis is not None
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "observation.image_flip",
                "--axis",
                request.libero_image_flip_axis,
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.observation_image_blackout:
        assert request.libero_image_blackout_value is not None
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "observation.image_blackout",
                "--value",
                str(request.libero_image_blackout_value),
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_blackout:
        assert request.libero_state_blackout_value is not None
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "observation.state_blackout",
                "--keys",
                state_keys,
                "--value",
                str(request.libero_state_blackout_value),
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_noise:
        assert request.libero_state_noise_std is not None
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "observation.state_noise",
                "--keys",
                state_keys,
                "--std",
                str(request.libero_state_noise_std),
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_key_drop:
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "observation.state_key_drop",
                "--keys",
                state_keys,
                "--",
                *eval_args,
            ]
        )
    elif request.injection.enabled and request.injection.operator == InjectionOperator.code_semantic_bug_flag:
        assert request.semantic_bug_flag is not None
        command.extend(
            [
                "python",
                "-m",
                "evaltriage.runners.lerobot_overlay_worker",
                "--overlay",
                "code.semantic_bug_flag",
                "--semantic-bug-flag",
                request.semantic_bug_flag,
                "--",
                *eval_args,
            ]
        )
    else:
        command.extend(eval_args)
    return command


def _capture_conda_runtime_env(conda_env: str, env: dict[str, str]) -> RuntimeEnvManifest | None:
    code = f"""
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys

def version(name):
    try:
        return md.version(name)
    except Exception:
        return None

try:
    import torch
    torch_v = torch.__version__
    cuda_v = torch.version.cuda
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
except Exception:
    torch_v = cuda_v = gpu = None

try:
    driver = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip().splitlines()[0]
except Exception:
    driver = None

print(json.dumps({{
    "conda_env": {json.dumps(conda_env)},
    "python": sys.version.split()[0],
    "torch": torch_v,
    "cuda": cuda_v,
    "gpu": gpu,
    "driver": driver,
    "mujoco": version("mujoco"),
    "robosuite": version("robosuite"),
    "mani_skill": version("mani-skill"),
    "os": f"{{platform.system()}} {{platform.release()}}",
}}))
"""
    proc = subprocess.run(
        ["conda", "run", "-n", conda_env, "python", "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        return None
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return RuntimeEnvManifest.model_validate(json.loads(lines[-1]))


def _episodes_from_eval_info(info: dict, request: RunRequest) -> list[EpisodeRecord]:
    episodes: list[EpisodeRecord] = []
    episode_id = 0
    for task in info.get("per_task", []):
        task_suite = task.get("task_group", request.suite)
        task_id = int(task.get("task_id", request.task_ids[0]))
        metrics = task.get("metrics", {})
        rewards = metrics.get("sum_rewards", [])
        successes = metrics.get("successes", [])
        videos = metrics.get("video_paths", [])
        if not successes:
            raise RuntimeError("lerobot eval_info.json has no per-episode successes")
        for i, success in enumerate(successes):
            reward = rewards[i] if i < len(rewards) else None
            video = videos[i] if i < len(videos) else None
            episodes.append(
                EpisodeRecord(
                    episode_id=episode_id,
                    task_suite=task_suite,
                    task_id=task_id,
                    seed=request.seed + episode_id,
                    success=bool(success),
                    reward=reward,
                    num_steps=None,
                    termination_reason="success" if success else "failure",
                    video_path=video,
                )
            )
            episode_id += 1
    return episodes


def _run_dataset_preflight(request: RunRequest, raw_dir: Path, logs_path: Path) -> RunnerResult:
    if request.dataset_path is None:
        raise RuntimeError("dataset preflight requires dataset_path")
    feature_key = request.dataset_feature_key or "observation.state"
    start = time.time()
    info_path = request.dataset_path / "meta" / "info.json"
    preflight_path = raw_dir / "dataset_preflight.json"
    command = ["internal:lerobot_dataset_preflight", str(info_path), feature_key]
    if not info_path.exists():
        wall = time.time() - start
        logs_path.write_text(f"missing dataset info.json: {info_path}\n")
        raise RunnerExecutionError(
            f"missing dataset info.json: {info_path}",
            command=command,
            stage="dataset_preflight",
            failure_kind="missing_dataset_metadata",
            cost=CostRecord(wall_clock_s=wall, gpu_minutes=0.0),
        )

    info = json.loads(info_path.read_text())
    features = dict(info.get("features") or {})
    effective_info_path = info_path
    if request.injection.enabled and request.injection.operator == InjectionOperator.dataset_remove_feature_column:
        overlay_dir = raw_dir / "dataset_overlay" / "meta"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_info = dict(info)
        overlay_features = dict(features)
        overlay_features.pop(feature_key, None)
        overlay_info["features"] = overlay_features
        effective_info_path = overlay_dir / "info.json"
        _write_json(effective_info_path, overlay_info)
        features = overlay_features

    payload = {
        "dataset_path": str(request.dataset_path),
        "effective_info_path": str(effective_info_path),
        "required_feature": feature_key,
        "feature_present": feature_key in features,
        "feature_count": len(features),
    }
    _write_json(preflight_path, payload)
    with logs_path.open("w") as logs:
        logs.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    wall = time.time() - start
    if feature_key not in features:
        raise RunnerExecutionError(
            f"dataset required feature missing: {feature_key}",
            command=command,
            stage="dataset_preflight",
            failure_kind="missing_dataset_feature",
            raw_output_path=str(preflight_path),
            cost=CostRecord(wall_clock_s=wall, gpu_minutes=0.0),
        )

    episode = EpisodeRecord(
        episode_id=0,
        task_suite=request.suite,
        task_id=request.task_ids[0],
        seed=request.seed,
        success=True,
        reward=1.0,
        num_steps=0,
        termination_reason="dataset_preflight_passed",
    )
    return RunnerResult(
        command=command,
        raw_output_path=str(preflight_path),
        episodes=[episode],
        metrics=RunMetrics(success_rate=1.0, mean_reward=1.0, num_episodes=1, num_success=1, num_failure=0),
        cost=CostRecord(wall_clock_s=wall, gpu_minutes=0.0),
        benchmark="lerobot_dataset_preflight",
        runtime_env=_capture_conda_runtime_env(request.libero_env, base_env("0")),
    )


def run_lerobot_libero(request: RunRequest, raw_dir: Path, logs_path: Path) -> RunnerResult:
    raw_dir.mkdir(parents=True, exist_ok=True)
    if request.dataset_path is not None:
        return _run_dataset_preflight(request, raw_dir, logs_path)
    effective_policy_path = request.policy_path
    if request.injection.enabled and request.injection.operator in {
        InjectionOperator.checkpoint_config_feature_mismatch,
        InjectionOperator.checkpoint_remove_processor_stats,
    }:
        overlay_policy_path = _prepare_checkpoint_overlay(request, raw_dir)
        request = request.model_copy(update={"policy_path": overlay_policy_path})
        effective_policy_path = overlay_policy_path
    command = _lerobot_command(request, raw_dir)
    env = base_env("0")
    env["LIBERO_CONFIG_PATH"] = str(LIBERO_CONFIG_PATH)
    start = time.time()
    with logs_path.open("w") as logs:
        proc = subprocess.run(command, env=env, stdout=logs, stderr=subprocess.STDOUT, text=True)
    wall = time.time() - start
    if proc.returncode != 0:
        raise RunnerExecutionError(
            f"lerobot-eval failed with exit code {proc.returncode}; see {logs_path}",
            command=command,
            exit_code=proc.returncode,
            stage="evaluation",
            failure_kind="process_exit",
            cost=CostRecord(wall_clock_s=wall, gpu_minutes=wall / 60.0),
        )
    eval_info_path = raw_dir / "eval_info.json"
    if not eval_info_path.exists():
        raise RuntimeError(f"lerobot-eval did not produce {eval_info_path}")
    info = json.loads(eval_info_path.read_text())
    episodes = _episodes_from_eval_info(info, request)
    num_success = sum(1 for ep in episodes if ep.success)
    num_episodes = len(episodes)
    expected_episodes = request.episodes * len(request.task_ids)
    if num_episodes != expected_episodes:
        raise RuntimeError(f"expected {expected_episodes} LeRobot episodes, got {num_episodes}")
    metrics = RunMetrics(
        success_rate=(num_success / num_episodes) if num_episodes else None,
        mean_reward=sum((ep.reward or 0.0) for ep in episodes) / num_episodes if num_episodes else None,
        num_episodes=num_episodes,
        num_success=num_success,
        num_failure=num_episodes - num_success,
    )
    cost = CostRecord(wall_clock_s=wall, gpu_minutes=wall / 60.0)
    runtime_env = _capture_conda_runtime_env(request.libero_env, env)
    return RunnerResult(
        command=command,
        raw_output_path=str(eval_info_path),
        effective_policy_path=str(effective_policy_path) if effective_policy_path is not None else None,
        episodes=episodes,
        metrics=metrics,
        cost=cost,
        benchmark="libero",
        runtime_env=runtime_env,
    )
