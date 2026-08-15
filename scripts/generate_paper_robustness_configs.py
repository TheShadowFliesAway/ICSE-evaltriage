"""Generate robustness appendix configs for the paper matrix.

These configs extend the completed paper matrix without overwriting it:

- robust_lerobot_ep3_*: LeRobot/LIBERO completed-rollout robustness.
- robust_failure_*: failed-run robustness variants.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs" / "cases"
OUTPUT_ROOT = "/data/project/zjx/runs/evaltriage"
POLICY = "/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"
DATASET = "/data/project/zjx/datasets/lerobot/libero_10_image"
THRESHOLDS = "configs/thresholds/validation_lerobot_libero.yaml"
TASKS = list(range(10))
SEEDS = [1000, 2000, 3000]
EPISODES = 3


def run(
    run_id: str,
    role: str,
    seed: int,
    *,
    episodes: int = EPISODES,
    task_ids: list[int] | None = None,
    injection: dict[str, Any] | None = None,
    allow_failure: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "platform": "lerobot_libero",
        "run_id": run_id,
        "role": role,
        "suite": "libero_goal",
        "task_ids": task_ids or TASKS,
        "seed": seed,
        "episodes": episodes,
        "output_root": OUTPUT_ROOT,
        "policy_path": POLICY,
        "obs_type": "pixels_agent_pos",
        "camera_size": 360,
        "compile_model": False,
        "use_async_envs": False,
    }
    payload.update(extra)
    if allow_failure:
        payload["allow_failure"] = True
    if injection is not None:
        payload["injection"] = injection
    return payload


def dataset_run(
    run_id: str,
    role: str,
    feature_key: str,
    *,
    injection: dict[str, Any] | None = None,
    allow_failure: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "platform": "lerobot_libero",
        "run_id": run_id,
        "role": role,
        "suite": "libero_10_image",
        "task_ids": [0],
        "seed": 1000,
        "episodes": 1,
        "output_root": OUTPUT_ROOT,
        "dataset_path": DATASET,
        "dataset_feature_key": feature_key,
        "obs_type": "dataset_preflight",
    }
    if allow_failure:
        payload["allow_failure"] = True
    if injection is not None:
        payload["injection"] = injection
    return payload


def injection(factor: str, operator: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"enabled": True, "factor": factor, "operator": operator, "params": params}


def case_record(
    case_id: str,
    *,
    symptom: str,
    factor: str,
    operator: str | None,
    refs: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "case_id": case_id,
        "platform": "lerobot_libero",
        "case_family": "setup_sensitive_factor",
        "deviation_symptom": symptom,
        "expected_status": "likely_setup_sensitive_deviation",
        "expected_factor": factor,
        "rq1_factor_category": factor,
        "rq1_evidence_refs": refs,
        "rq1_support_level": "evidence_backed",
        "coverage_status": "core_planned",
        "artifact_split": "full",
    }
    if operator is not None:
        payload["injected_factor"] = factor
        payload["injection_operator"] = operator
    return payload


CANONICAL = {
    "action_control_mode": {
        "factor": "action_controller_interface",
        "operator": "action.change_control_mode",
        "symptom": "success_rate_drop_or_mismatch",
        "refs": ["github_issue::huggingface/lerobot::3401"],
        "extra": {"libero_control_mode": "absolute"},
        "params": {"control_mode": "absolute"},
    },
    "checkpoint_feature_mismatch": {
        "factor": "checkpoint_config_compatibility",
        "operator": "checkpoint.config_feature_mismatch",
        "symptom": "success_rate_drop_or_mismatch",
        "refs": ["github_issue::huggingface/lerobot::3252"],
        "extra": {"checkpoint_overlay_mode": "postprocessor_action_norm_identity"},
        "params": {"overlay_mode": "postprocessor_action_norm_identity"},
    },
    "eval_protocol_episode_length": {
        "factor": "evaluation_protocol_metric",
        "operator": "eval_protocol.change_episode_length",
        "symptom": "success_rate_drop_or_mismatch",
        "refs": ["github_issue::huggingface/lerobot::1316"],
        "extra": {"episode_length": 10},
        "params": {"episode_length": 10},
    },
    "harness_batch_size": {
        "factor": "evaluation_script_harness",
        "operator": "evaluation_script.modify_harness_flag",
        "symptom": "rollout_behavior_anomaly",
        "refs": ["github_issue::huggingface/lerobot::2850"],
        "extra": {"eval_batch_size": 2},
        "params": {"flag": "eval.batch_size", "value": 2},
    },
    "observation_state_blackout": {
        "factor": "observation_sensor_preprocessing",
        "operator": "observation.state_blackout",
        "symptom": "rollout_behavior_anomaly",
        "refs": ["github_issue::huggingface/lerobot::1007"],
        "extra": {"libero_state_keys": ["observation.state"], "libero_state_blackout_value": 0.0},
        "params": {"keys": ["observation.state"], "value": 0.0},
    },
    "reset_disable_init_states": {
        "factor": "reset_or_initial_state",
        "operator": "reset.disable_fixed_init_state",
        "symptom": "evaluation_instability_or_flakiness",
        "refs": ["github_issue::huggingface/lerobot::3814"],
        "extra": {"libero_init_states": False},
        "params": {"init_states": False},
    },
    "dependency_mujoco37": {
        "factor": "dependency_runtime_environment",
        "operator": "runtime.switch_mujoco_env",
        "symptom": "setup_sensitive_result",
        "refs": ["github_issue::huggingface/lerobot::2697", "github_issue::moojink/openvla-oft::150"],
        "extra": {"libero_env": "evaltriage-lr-mujoco37", "mujoco_env": "evaltriage-lr-mujoco37"},
        "params": {"conda_env": "evaltriage-lr-mujoco37"},
    },
}


def write_config(name: str, payload: dict[str, Any]) -> None:
    path = OUT / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def build_completed_rollout() -> None:
    for seed in SEEDS:
        baseline_id = f"robust_lr_goal_tasks0to9_ep3_baseline_seed{seed}"
        replay_id = f"robust_lr_goal_tasks0to9_ep3_replay_seed{seed}"
        for key, spec in CANONICAL.items():
            factor = spec["factor"]
            operator = spec["operator"]
            case_id = f"robust_lerobot_ep3_{key}_goal_tasks0to9_seed{seed}"
            current_id = f"robust_lr_goal_tasks0to9_ep3_current_{key}_seed{seed}"
            payload = {
                "schema_version": "1.0",
                "kind": "case",
                "case": case_record(
                    case_id,
                    symptom=spec["symptom"],
                    factor=factor,
                    operator=operator,
                    refs=spec["refs"],
                ),
                "baseline_runs": [run(baseline_id, "baseline", seed)],
                "current_runs": [
                    run(
                        current_id,
                        "current",
                        seed,
                        injection=injection(factor, operator, spec["params"]),
                        **spec["extra"],
                    )
                ],
                "replay_runs": [run(replay_id, "replay", seed)],
                "thresholds_path": THRESHOLDS,
            }
            write_config(f"{case_id}.yaml", payload)

    for baseline_seed, current_seed in [
        (1000, 2000),
        (2000, 1000),
        (1000, 3000),
        (3000, 1000),
        (2000, 3000),
        (3000, 2000),
    ]:
        case_id = (
            "robust_lerobot_ep3_seed_drift_goal_tasks0to9_"
            f"baseline{baseline_seed}_current{current_seed}"
        )
        payload = {
            "schema_version": "1.0",
            "kind": "case",
            "case": case_record(
                case_id,
                symptom="evaluation_instability_or_flakiness",
                factor="seed_or_randomness",
                operator=None,
                refs=["github_issue::Farama-Foundation/Metaworld::555"],
            ),
            "baseline_runs": [run(f"robust_lr_goal_tasks0to9_ep3_baseline_seed{baseline_seed}", "baseline", baseline_seed)],
            "current_runs": [
                run(
                    f"robust_lr_goal_tasks0to9_ep3_current_clean_seed{current_seed}_for_seed_drift_from{baseline_seed}",
                    "current",
                    current_seed,
                )
            ],
            "replay_runs": [run(f"robust_lr_goal_tasks0to9_ep3_replay_seed{baseline_seed}", "replay", baseline_seed)],
            "thresholds_path": THRESHOLDS,
        }
        write_config(f"{case_id}.yaml", payload)


def build_failed_run() -> None:
    for task, seed in [(5, 2000), (7, 3000)]:
        baseline = run(
            f"robust_lr_goal_task{task}_ep1_failure_baseline_seed{seed}",
            "baseline",
            seed,
            episodes=1,
            task_ids=[task],
        )
        replay = run(
            f"robust_lr_goal_task{task}_ep1_failure_replay_seed{seed}",
            "replay",
            seed,
            episodes=1,
            task_ids=[task],
        )
        variants = [
            (
                f"robust_failure_observation_state_key_drop_goal_task{task}_seed{seed}",
                "observation_sensor_preprocessing",
                "observation.state_key_drop",
                ["github_issue::huggingface/lerobot::1007"],
                run(
                    f"robust_lr_goal_task{task}_ep1_current_state_key_drop_seed{seed}",
                    "current",
                    seed,
                    episodes=1,
                    task_ids=[task],
                    allow_failure=True,
                    libero_state_keys=["observation.state"],
                    injection=injection(
                        "observation_sensor_preprocessing",
                        "observation.state_key_drop",
                        {"keys": ["observation.state"]},
                    ),
                ),
            ),
            (
                f"robust_failure_checkpoint_remove_processor_stats_goal_task{task}_seed{seed}",
                "checkpoint_config_compatibility",
                "checkpoint.remove_processor_stats",
                ["github_issue::huggingface/lerobot::2731"],
                run(
                    f"robust_lr_goal_task{task}_ep1_current_remove_processor_stats_seed{seed}",
                    "current",
                    seed,
                    episodes=1,
                    task_ids=[task],
                    allow_failure=True,
                    checkpoint_overlay_mode="remove_processor_stats",
                    injection=injection("checkpoint_config_compatibility", "checkpoint.remove_processor_stats", {}),
                ),
            ),
            (
                f"robust_failure_dependency_incompatible_env_goal_task{task}_seed{seed}",
                "dependency_runtime_environment",
                "runtime.switch_incompatible_env",
                ["github_issue::huggingface/lerobot::2134"],
                run(
                    f"robust_lr_goal_task{task}_ep1_current_incompatible_base_env_seed{seed}",
                    "current",
                    seed,
                    episodes=1,
                    task_ids=[task],
                    allow_failure=True,
                    libero_env="base",
                    injection=injection(
                        "dependency_runtime_environment",
                        "runtime.switch_incompatible_env",
                        {"conda_env": "base"},
                    ),
                ),
            ),
        ]
        for case_id, factor, operator, refs, current in variants:
            payload = {
                "schema_version": "1.0",
                "kind": "case",
                "case": case_record(
                    case_id,
                    symptom="evaluation_crash_or_failure",
                    factor=factor,
                    operator=operator,
                    refs=refs,
                ),
                "baseline_runs": [baseline],
                "current_runs": [current],
                "replay_runs": [replay],
                "thresholds_path": THRESHOLDS,
            }
            write_config(f"{case_id}.yaml", payload)

    for feature_key, slug in [
        ("action", "action"),
        ("observation.images.image", "observation_images_image"),
    ]:
        case_id = f"robust_failure_dataset_remove_{slug}_libero10_seed1000"
        payload = {
            "schema_version": "1.0",
            "kind": "case",
            "case": case_record(
                case_id,
                symptom="evaluation_crash_or_failure",
                factor="data_dataset_format",
                operator="dataset.remove_feature_column",
                refs=["github_issue::openvla/openvla::93"],
            ),
            "baseline_runs": [dataset_run(f"robust_dataset_libero10_preflight_baseline_{slug}_seed1000", "baseline", feature_key)],
            "current_runs": [
                dataset_run(
                    f"robust_dataset_libero10_preflight_current_remove_{slug}_seed1000",
                    "current",
                    feature_key,
                    allow_failure=True,
                    injection=injection(
                        "data_dataset_format",
                        "dataset.remove_feature_column",
                        {"feature_key": feature_key},
                    ),
                )
            ],
            "replay_runs": [dataset_run(f"robust_dataset_libero10_preflight_replay_{slug}_seed1000", "replay", feature_key)],
            "thresholds_path": THRESHOLDS,
        }
        write_config(f"{case_id}.yaml", payload)


def main() -> None:
    build_completed_rollout()
    build_failed_run()


if __name__ == "__main__":
    main()
