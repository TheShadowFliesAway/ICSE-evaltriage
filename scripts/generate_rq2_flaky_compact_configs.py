"""Generate compact real LeRobot/LIBERO flaky status configs.

These configs reduce runtime while preserving real rollout evidence:

- tasks: LIBERO goal [4, 5, 7]
- episodes: 2 per task
- repeated same-manifest runs: 2 baseline + 2 current

They are intended as an RQ2 flaky signal probe, not as a replacement for the
full paper/robustness matrix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs" / "cases"
OUTPUT_ROOT = "/data/project/zjx/runs/evaltriage"
POLICY = "/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"
THRESHOLDS = "configs/thresholds/validation_lerobot_libero.yaml"
TASKS = [4, 5, 7]
SEEDS = [1000, 2000, 3000]
EPISODES = 2


def run(run_id: str, role: str, seed: int, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "platform": "lerobot_libero",
        "run_id": run_id,
        "role": role,
        "suite": "libero_goal",
        "task_ids": TASKS,
        "seed": seed,
        "episodes": EPISODES,
        "output_root": OUTPUT_ROOT,
        "policy_path": POLICY,
        "obs_type": "pixels_agent_pos",
        "camera_size": 360,
        "compile_model": False,
        "use_async_envs": False,
    }
    payload.update(extra)
    return payload


def flaky_case(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "platform": "lerobot_libero",
        "case_family": "flaky",
        "deviation_symptom": "evaluation_instability_or_flakiness",
        "expected_status": "likely_flaky_evaluation",
        "expected_factor": "seed_or_randomness",
        "rq1_factor_category": "seed_or_randomness",
        "rq1_evidence_refs": ["github_issue::Farama-Foundation/Metaworld::555"],
        "rq1_support_level": "evidence_backed",
        "coverage_status": "core_planned",
        "artifact_split": "validation",
    }


def write_config(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(yaml.safe_dump(payload, sort_keys=False))


def main() -> None:
    profiles: dict[str, dict[str, Any]] = {
        "unfixed_init_sync_batch1": {
            "libero_init_states": False,
            "use_async_envs": False,
            "eval_batch_size": 1,
        },
        "unfixed_init_async_batch2": {
            "libero_init_states": False,
            "use_async_envs": True,
            "eval_batch_size": 2,
        },
        "unfixed_init_async_batch4": {
            "libero_init_states": False,
            "use_async_envs": True,
            "eval_batch_size": 4,
        },
    }
    for profile, extra in profiles.items():
        for seed in SEEDS:
            case_id = f"rq2_flaky_compact_{profile}_tasks457_ep2_seed{seed}"
            baseline_runs = [
                run(
                    f"rq2_compact_flaky_{profile}_tasks457_ep2_baseline_seed{seed}_repeat{repeat}",
                    "baseline",
                    seed,
                    **extra,
                )
                for repeat in [0, 1]
            ]
            current_runs = [
                run(
                    f"rq2_compact_flaky_{profile}_tasks457_ep2_current_seed{seed}_repeat{repeat}",
                    "current",
                    seed,
                    **extra,
                )
                for repeat in [0, 1]
            ]
            payload = {
                "schema_version": "1.0",
                "kind": "case",
                "case": flaky_case(case_id),
                "baseline_runs": baseline_runs,
                "current_runs": current_runs,
                "thresholds_path": THRESHOLDS,
            }
            write_config(f"{case_id}.yaml", payload)


if __name__ == "__main__":
    main()
