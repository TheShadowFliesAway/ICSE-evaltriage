"""Generate real LeRobot/LIBERO RQ2 status-classification configs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs" / "cases"
OUTPUT_ROOT = "/data/project/zjx/runs/evaltriage"
POLICY = "/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"
THRESHOLDS = "configs/thresholds/validation_lerobot_libero.yaml"
TASKS = list(range(10))
SEEDS = [1000, 2000, 3000]
EPISODES = 3


def injection(factor: str, operator: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"enabled": True, "factor": factor, "operator": operator, "params": params}


def run(
    run_id: str,
    role: str,
    seed: int,
    *,
    injection_payload: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
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
    if injection_payload is not None:
        payload["injection"] = injection_payload
    return payload


def true_regression_case(case_id: str, flag: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "platform": "lerobot_libero",
        "case_family": "true_regression",
        "deviation_symptom": "success_rate_drop_or_mismatch",
        "expected_status": "likely_true_regression",
        "expected_factor": "semantic_code_regression",
        "injected_factor": "semantic_code_regression",
        "injection_operator": "code.semantic_bug_flag",
        "rq1_factor_category": "evaluation_script_harness",
        "rq1_evidence_refs": ["github_issue::huggingface/lerobot::2850"],
        "rq1_support_level": "evidence_backed",
        "coverage_status": "planned_extension",
        "artifact_split": "full",
    }


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
        "artifact_split": "full",
    }


def write_config(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def build_true_regression() -> None:
    flags = [
        "zero_action_output",
        "freeze_first_action",
        "translation_sign_flip",
        "gripper_sign_flip",
    ]
    for flag in flags:
        inj = injection(
            "semantic_code_regression",
            "code.semantic_bug_flag",
            {"flag": flag, "semantic_change_ref": f"rq2_true_regression::{flag}"},
        )
        for seed in SEEDS:
            case_id = f"rq2_true_regression_{flag}_goal_tasks0to9_seed{seed}"
            payload = {
                "schema_version": "1.0",
                "kind": "case",
                "case": true_regression_case(case_id, flag),
                "baseline_runs": [
                    run(f"rq2_lr_goal_tasks0to9_ep3_true_regression_baseline_seed{seed}", "baseline", seed)
                ],
                "current_runs": [
                    run(
                        f"rq2_lr_goal_tasks0to9_ep3_current_{flag}_seed{seed}",
                        "current",
                        seed,
                        semantic_bug_flag=flag,
                        injection_payload=inj,
                    )
                ],
                "replay_runs": [
                    run(
                        f"rq2_lr_goal_tasks0to9_ep3_replay_{flag}_seed{seed}",
                        "replay",
                        seed,
                        semantic_bug_flag=flag,
                        injection_payload=inj,
                    )
                ],
                "thresholds_path": THRESHOLDS,
            }
            write_config(f"{case_id}.yaml", payload)


def build_flaky() -> None:
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
        "fixed_init_async_batch2": {
            "libero_init_states": True,
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
            case_id = f"rq2_flaky_{profile}_goal_tasks0to9_seed{seed}"
            repeated_runs: dict[str, list[dict[str, Any]]] = {
                "baseline_runs": [],
                "current_runs": [],
                "replay_runs": [],
            }
            for role, key in [("baseline", "baseline_runs"), ("current", "current_runs"), ("replay", "replay_runs")]:
                for repeat in [0, 1]:
                    repeated_runs[key].append(
                        run(
                            f"rq2_lr_goal_tasks0to9_ep3_flaky_{profile}_{role}_seed{seed}_repeat{repeat}",
                            role,
                            seed,
                            **extra,
                        )
                    )
            payload = {
                "schema_version": "1.0",
                "kind": "case",
                "case": flaky_case(case_id),
                **repeated_runs,
                "thresholds_path": THRESHOLDS,
            }
            write_config(f"{case_id}.yaml", payload)


def main() -> None:
    build_true_regression()
    build_flaky()


if __name__ == "__main__":
    main()
