"""Dependency-light ManiSkill worker for running inside evaltriage-ms."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


SUPPORTED_TASKS = {"PickCube-v1", "StackCube-v1", "PegInsertionSide-v1", "PushCube-v1"}
MOTION_PLANNING_SOLVERS = {
    "PickCube-v1": "mani_skill.examples.motionplanning.panda.solutions.pick_cube",
    "StackCube-v1": "mani_skill.examples.motionplanning.panda.solutions.stack_cube",
    "PegInsertionSide-v1": "mani_skill.examples.motionplanning.panda.solutions.peg_insertion_side",
    "PushCube-v1": "mani_skill.examples.motionplanning.panda.solutions.push_cube",
}


def _to_float(value: Any) -> float:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return float(np.asarray(value).reshape(-1)[0])


def _to_bool(value: Any) -> bool:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return bool(np.asarray(value).reshape(-1)[0])


def _run_random_episode(env, seed: int, max_steps: int, action_scale_multiplier: float) -> tuple[bool, float, int, str, list[str]]:
    env.reset(seed=seed)
    total_reward = 0.0
    success = False
    tags = []
    if action_scale_multiplier != 1.0:
        tags.append(f"action_scale_multiplier={action_scale_multiplier}")
    for step in range(max_steps):
        action = env.action_space.sample()
        if action_scale_multiplier != 1.0:
            action = action * action_scale_multiplier
        _, reward, terminated, truncated, info = env.step(action)
        total_reward += _to_float(reward)
        success = _to_bool(info.get("success", False)) or success
        if _to_bool(terminated) or _to_bool(truncated):
            return success, total_reward, step + 1, "success" if success else "terminated", tags
    return success, total_reward, max_steps, "success" if success else "timeout", tags


def _run_motionplanning_episode(env, task: str, seed: int) -> tuple[bool, float, int, str, list[str]]:
    module = importlib.import_module(MOTION_PLANNING_SOLVERS[task])
    result = module.solve(env, seed=seed, debug=False, vis=False)
    success = False
    reward = 0.0
    steps = len(result) if isinstance(result, list) else 0
    termination = "planner_failed" if result == -1 else "completed"
    try:
        evaluation = env.unwrapped.evaluate()
        if isinstance(evaluation, dict) and "success" in evaluation:
            success = _to_bool(evaluation["success"])
    except Exception:
        pass
    return success, reward, steps, "success" if success else termination, []


def _module_version(name: str) -> str | None:
    try:
        mod = importlib.import_module(name)
        return getattr(mod, "__version__", None) or getattr(mod, "version", None)
    except Exception:
        return None


def _driver_version() -> str | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None
    return out.splitlines()[0] if out else None


def _runtime_env() -> dict[str, str | None]:
    torch_v = None
    cuda_v = None
    gpu = None
    try:
        import torch

        torch_v = torch.__version__
        cuda_v = torch.version.cuda
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        pass
    return {
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "python": sys.version.split()[0],
        "torch": torch_v,
        "cuda": cuda_v,
        "gpu": gpu,
        "driver": _driver_version(),
        "mujoco": _module_version("mujoco"),
        "robosuite": _module_version("robosuite"),
        "mani_skill": _module_version("mani_skill"),
        "os": f"{platform.system()} {platform.release()}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--obs-mode", required=True)
    parser.add_argument("--control-policy", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action-scale-multiplier", type=float, default=1.0)
    parser.add_argument("--reset-seed-offset", type=int, default=0)
    args = parser.parse_args()

    if args.task not in SUPPORTED_TASKS:
        raise RuntimeError(f"unsupported ManiSkill task: {args.task}")
    if not math.isfinite(args.action_scale_multiplier) or args.action_scale_multiplier < 0:
        raise RuntimeError("--action-scale-multiplier must be a finite non-negative float")
    if args.action_scale_multiplier != 1.0 and args.control_policy != "random":
        raise RuntimeError("--action-scale-multiplier is currently supported only with --control-policy random")
    import gymnasium as gym
    import mani_skill.envs  # noqa: F401

    kwargs = {"obs_mode": args.obs_mode, "render_mode": None}
    if args.control_policy == "motionplanning":
        kwargs["control_mode"] = "pd_joint_pos"
    env = gym.make(args.task, **kwargs)
    episodes = []
    start = time.time()
    try:
        for i in range(args.episodes):
            seed = args.seed + args.reset_seed_offset + i
            reset_tags = []
            if args.reset_seed_offset != 0:
                reset_tags.append(f"reset_seed_offset={args.reset_seed_offset}")
            if args.control_policy == "random":
                success, reward, steps, termination, tags = _run_random_episode(
                    env,
                    seed,
                    200,
                    args.action_scale_multiplier,
                )
            elif args.control_policy == "motionplanning":
                success, reward, steps, termination, tags = _run_motionplanning_episode(env, args.task, seed)
            else:
                raise RuntimeError("control_policy must be random or motionplanning")
            tags = [*reset_tags, *tags]
            episodes.append(
                {
                    "episode_id": i,
                    "task_id": 0,
                    "seed": seed,
                    "success": success,
                    "reward": reward,
                    "num_steps": steps,
                    "termination_reason": termination,
                    "behavior_tags": tags,
                }
            )
    finally:
        env.close()
    payload = {"wall_clock_s": time.time() - start, "runtime_env": _runtime_env(), "episodes": episodes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
