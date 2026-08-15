"""EvalTriage 的正式命令行入口。"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

import typer

from .artifact.build import build_artifact
from .case_runner import run_case, validate_case_existing_runs
from .config import ConfigError, load_config
from .metrics.ablation import aggregate_ablation
from .metrics.aggregate import aggregate_cases
from .metrics.rq2 import aggregate_rq2_status
from .paths import DEFAULT_OUTPUT_ROOT, ensure_output_root, ensure_within_output_root
from .runners.executor import execute_run
from .schemas import AttributionFactor, CaseConfig, InjectionManifest, InjectionOperator, Platform, RunRequest, RunRole


run_app = typer.Typer(
    add_completion=False,
    help="运行一个 baseline、current、replay 或 smoke run。",
)
case_app = typer.Typer(
    add_completion=False,
    help="执行一个完整 diagnosis case。",
)
aggregate_app = typer.Typer(
    add_completion=False,
    help="聚合 case 输出并生成 RQ2-RQ4 指标 CSV。",
)
ablate_app = typer.Typer(
    add_completion=False,
    help="从真实 paper case artifacts 重新计算正式消融 CSV。",
)
rq2_status_app = typer.Typer(
    add_completion=False,
    help="从真实 artifacts 重新计算 RQ2 status-classification CSV。",
)
artifact_app = typer.Typer(
    add_completion=False,
    help="从 EvalTriage 输出生成 ICSE artifact 目录。",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _emit_validated(command: str, args: dict[str, Any]) -> None:
    payload = {
        "command": command,
        "validated": True,
        "args": _jsonable(args),
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _die(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(2)


def _parse_task_ids(value: str) -> list[int]:
    try:
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            raise ValueError
        return [int(item) for item in items]
    except ValueError:
        _die("--task-ids must be a comma-separated list of integer task ids")


def _parse_csv_strings(value: str, flag: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        _die(f"{flag} must be a comma-separated list of strings")
    return items


def _parse_csv_ints(value: str, flag: str) -> list[int]:
    try:
        items = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError:
        _die(f"{flag} must be a comma-separated list of integers")
    if not items:
        _die(f"{flag} must be a comma-separated list of integers")
    return items


def _parse_positive_int(value: int, flag: str) -> int:
    if value <= 0:
        _die(f"{flag} must be a positive integer")
    return value


def _parse_bool(value: str, flag: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    _die(f"{flag} must be true or false")


@run_app.command()
def run(
    platform: Platform = typer.Option(..., "--platform", help="实验平台。"),
    run_id: str = typer.Option(..., "--run-id", help="run 级唯一 ID。"),
    role: RunRole = typer.Option(..., "--role", help="run 角色。"),
    suite: str = typer.Option(..., "--suite", help="LIBERO suite 或 ManiSkill task。"),
    task_ids: str = typer.Option(..., "--task-ids", help="逗号分隔的 task id 列表。"),
    seed: int = typer.Option(..., "--seed", help="随机种子。"),
    episodes: int = typer.Option(..., "--episodes", help="episode 数量。"),
    output_root: Path = typer.Option(
        DEFAULT_OUTPUT_ROOT,
        "--output-root",
        help="EvalTriage 输出根目录。",
    ),
    policy_path: Path | None = typer.Option(
        None,
        "--policy-path",
        help="LeRobot policy checkpoint 路径。",
    ),
    libero_env: str = typer.Option(
        "evaltriage-lr",
        "--libero-env",
        help="LeRobot + LIBERO conda 环境名。",
    ),
    mujoco_env: str = typer.Option(
        "evaltriage-lr-mujoco37",
        "--mujoco-env",
        help="MuJoCo drift 对照环境名。",
    ),
    incompatible_env: str = typer.Option(
        "base",
        "--incompatible-env",
        help="runtime.switch_incompatible_env 使用的非 LeRobot conda 环境名。",
    ),
    obs_type: str = typer.Option(
        "pixels_agent_pos",
        "--obs-type",
        help="LeRobot + LIBERO observation 类型。",
    ),
    camera_size: int = typer.Option(360, "--camera-size", help="相机输入尺寸。"),
    episode_length: int | None = typer.Option(
        None,
        "--episode-length",
        help="覆盖环境 episode_length；用于 eval_protocol.change_episode_length。",
    ),
    libero_control_mode: str = typer.Option(
        "relative",
        "--libero-control-mode",
        help="LeRobot + LIBERO control mode：relative 或 absolute。",
    ),
    libero_camera_name: str = typer.Option(
        "agentview_image,robot0_eye_in_hand_image",
        "--libero-camera-name",
        help="LeRobot + LIBERO camera_name；逗号分隔。",
    ),
    libero_camera_swap: bool = typer.Option(
        False,
        "--libero-camera-swap",
        help="交换 LIBERO agentview 和 eye-in-hand 到 policy image/image2 的映射。",
    ),
    libero_init_states: str = typer.Option(
        "true",
        "--libero-init-states",
        help="是否使用 LIBERO task init states；reset.disable_fixed_init_state 需要 false。",
    ),
    libero_image_flip_axis: str | None = typer.Option(
        None,
        "--libero-image-flip-axis",
        help="对 policy 输入图像做 runtime flip：horizontal、vertical 或 both。",
    ),
    libero_image_blackout_value: float | None = typer.Option(
        None,
        "--libero-image-blackout-value",
        help="对 policy 输入图像做 runtime blackout 的填充值；用于 observation.image_blackout。",
    ),
    libero_state_keys: str = typer.Option(
        "observation.state",
        "--libero-state-keys",
        help="逗号分隔的 LeRobot policy state observation keys；用于 observation.state_*。",
    ),
    libero_state_blackout_value: float | None = typer.Option(
        None,
        "--libero-state-blackout-value",
        help="对 policy state observation 做 runtime blackout 的填充值；用于 observation.state_blackout。",
    ),
    libero_state_noise_std: float | None = typer.Option(
        None,
        "--libero-state-noise-std",
        help="对 policy state observation 注入 Gaussian noise 的 std；用于 observation.state_noise。",
    ),
    checkpoint_overlay_mode: str | None = typer.Option(
        None,
        "--checkpoint-overlay-mode",
        help="checkpoint.config_feature_mismatch 的临时 checkpoint overlay 模式。",
    ),
    compile_model: str = typer.Option(
        "false",
        "--compile-model",
        help="是否启用 policy.compile_model。",
    ),
    eval_batch_size: int = typer.Option(
        1,
        "--eval-batch-size",
        help="LeRobot eval.batch_size；evaluation_script.modify_harness_flag 可修改该值。",
    ),
    use_async_envs: str = typer.Option(
        "false",
        "--use-async-envs",
        help="是否启用 async env。",
    ),
    maniskill_env: str = typer.Option(
        "evaltriage-ms",
        "--maniskill-env",
        help="ManiSkill conda 环境名。",
    ),
    control_policy: str | None = typer.Option(
        None,
        "--control-policy",
        help="ManiSkill control policy；当前真实 runner 支持 motionplanning 或 random。",
    ),
    obs_mode: str | None = typer.Option(
        None,
        "--obs-mode",
        help="ManiSkill observation mode。",
    ),
    allow_failure: bool = typer.Option(
        False,
        "--allow-failure",
        help="允许预期 crash/failure run 写入正式 failed-run artifact。",
    ),
    dataset_path: Path | None = typer.Option(
        None,
        "--dataset-path",
        help="LeRobot dataset preflight 路径；用于 dataset.* operators。",
    ),
    dataset_feature_key: str | None = typer.Option(
        None,
        "--dataset-feature-key",
        help="dataset.remove_feature_column 的 required feature key。",
    ),
    semantic_bug_flag: str | None = typer.Option(
        None,
        "--semantic-bug-flag",
        help="code.semantic_bug_flag 的真实 action 语义 bug flag。",
    ),
    injection_operator: InjectionOperator | None = typer.Option(
        None,
        "--injection-operator",
        help="真实接入的 fault injection operator；未接入 backend 的 operator 会失败。",
    ),
    action_scale_multiplier: float | None = typer.Option(
        None,
        "--action-scale-multiplier",
        help="action.scale_multiplier 的 multiplier 参数。",
    ),
    action_dimension_permutation: str | None = typer.Option(
        None,
        "--action-dimension-permutation",
        help="action.reorder_dimensions 的逗号分隔维度排列，例如 1,0,2,3,4,5,6。",
    ),
    reset_seed_offset: int | None = typer.Option(
        None,
        "--reset-seed-offset",
        help="reset.disable_fixed_init_state 的 seed_offset 参数。",
    ),
    harness_flag: str | None = typer.Option(
        None,
        "--harness-flag",
        help="evaluation_script.modify_harness_flag 的 flag；当前支持 eval.batch_size。",
    ),
    harness_value: int | None = typer.Option(
        None,
        "--harness-value",
        help="evaluation_script.modify_harness_flag 的整数 value。",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行后端。",
    ),
) -> None:
    parsed_task_ids = _parse_task_ids(task_ids)
    parsed_episodes = _parse_positive_int(episodes, "--episodes")
    parsed_camera_size = _parse_positive_int(camera_size, "--camera-size")
    parsed_episode_length = None
    if episode_length is not None:
        parsed_episode_length = _parse_positive_int(episode_length, "--episode-length")
    parsed_compile_model = _parse_bool(compile_model, "--compile-model")
    parsed_eval_batch_size = _parse_positive_int(eval_batch_size, "--eval-batch-size")
    parsed_use_async_envs = _parse_bool(use_async_envs, "--use-async-envs")
    parsed_libero_init_states = _parse_bool(libero_init_states, "--libero-init-states")
    parsed_libero_state_keys = _parse_csv_strings(libero_state_keys, "--libero-state-keys")
    parsed_action_dimension_permutation = (
        _parse_csv_ints(action_dimension_permutation, "--action-dimension-permutation")
        if action_dimension_permutation is not None
        else []
    )

    if platform == Platform.lerobot_libero and policy_path is None and dataset_path is None:
        _die("--policy-path is required when --platform=lerobot_libero unless --dataset-path is provided")
    if libero_control_mode not in {"relative", "absolute"}:
        _die("--libero-control-mode must be relative or absolute")
    if platform == Platform.maniskill:
        missing = []
        if control_policy is None:
            missing.append("--control-policy")
        if obs_mode is None:
            missing.append("--obs-mode")
        if missing:
            _die(f"{', '.join(missing)} required when --platform=maniskill")
    injection = InjectionManifest()
    if injection_operator is not None:
        if (
            injection_operator != InjectionOperator.observation_image_blackout
            and libero_image_blackout_value is not None
        ):
            _die("--libero-image-blackout-value can only be used with observation.image_blackout")
        if (
            injection_operator != InjectionOperator.observation_state_blackout
            and libero_state_blackout_value is not None
        ):
            _die("--libero-state-blackout-value can only be used with observation.state_blackout")
        if (
            injection_operator != InjectionOperator.observation_state_noise
            and libero_state_noise_std is not None
        ):
            _die("--libero-state-noise-std can only be used with observation.state_noise")
        if (
            injection_operator != InjectionOperator.action_reorder_dimensions
            and action_dimension_permutation is not None
        ):
            _die("--action-dimension-permutation can only be used with action.reorder_dimensions")
        if injection_operator != InjectionOperator.code_semantic_bug_flag and semantic_bug_flag is not None:
            _die("--semantic-bug-flag can only be used with code.semantic_bug_flag")
        if injection_operator == InjectionOperator.action_scale_multiplier:
            if action_scale_multiplier is None:
                _die("--action-scale-multiplier is required with --injection-operator=action.scale_multiplier")
            if reset_seed_offset is not None:
                _die("--reset-seed-offset cannot be used with action.scale_multiplier")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.action_controller_interface,
                operator=injection_operator,
                params={"multiplier": action_scale_multiplier},
            )
        elif injection_operator == InjectionOperator.reset_disable_fixed_init_state:
            if action_scale_multiplier is not None:
                _die("--action-scale-multiplier cannot be used with reset.disable_fixed_init_state")
            if platform == Platform.maniskill:
                if reset_seed_offset is None:
                    _die("--reset-seed-offset is required with --injection-operator=reset.disable_fixed_init_state on ManiSkill")
                params = {"seed_offset": reset_seed_offset}
            elif platform == Platform.lerobot_libero:
                if reset_seed_offset is not None:
                    _die("--reset-seed-offset cannot be used with reset.disable_fixed_init_state on LeRobot/LIBERO")
                if parsed_libero_init_states is not False:
                    _die("--libero-init-states false is required with --injection-operator=reset.disable_fixed_init_state")
                params = {"init_states": False}
            else:
                _die("reset.disable_fixed_init_state is not connected for this platform")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.reset_or_initial_state,
                operator=injection_operator,
                params=params,
            )
        elif injection_operator == InjectionOperator.runtime_switch_mujoco_env:
            if platform != Platform.lerobot_libero:
                _die("runtime.switch_mujoco_env is currently connected only for --platform=lerobot_libero")
            if mujoco_env == "evaltriage-lr":
                _die("--mujoco-env must be a non-default LeRobot/LIBERO env")
            if (
                action_scale_multiplier is not None
                or reset_seed_offset is not None
                or harness_flag is not None
                or harness_value is not None
                or libero_image_blackout_value is not None
                or libero_state_blackout_value is not None
                or libero_state_noise_std is not None
                or parsed_episode_length is not None
                or libero_image_flip_axis is not None
                or libero_camera_swap
                or libero_control_mode != "relative"
                or parsed_libero_init_states is not True
            ):
                _die("runtime.switch_mujoco_env cannot be combined with other injection controls")
            libero_env = mujoco_env
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.dependency_runtime_environment,
                operator=injection_operator,
                params={"conda_env": mujoco_env},
            )
        elif injection_operator == InjectionOperator.runtime_switch_incompatible_env:
            if platform != Platform.lerobot_libero:
                _die("runtime.switch_incompatible_env is currently connected only for --platform=lerobot_libero")
            if incompatible_env == "evaltriage-lr":
                _die("--incompatible-env must be a non-default LeRobot/LIBERO env")
            if not allow_failure:
                _die("--allow-failure is required with runtime.switch_incompatible_env")
            libero_env = incompatible_env
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.dependency_runtime_environment,
                operator=injection_operator,
                params={"conda_env": incompatible_env},
            )
        elif injection_operator == InjectionOperator.eval_protocol_change_episode_length:
            if parsed_episode_length is None:
                _die("--episode-length is required with --injection-operator=eval_protocol.change_episode_length")
            if action_scale_multiplier is not None or reset_seed_offset is not None or harness_flag is not None or harness_value is not None:
                _die("--action-scale-multiplier/--reset-seed-offset/--harness-* cannot be used with eval_protocol.change_episode_length")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.evaluation_protocol_metric,
                operator=injection_operator,
                params={"episode_length": parsed_episode_length},
            )
        elif injection_operator == InjectionOperator.evaluation_script_modify_harness_flag:
            if platform != Platform.lerobot_libero:
                _die("evaluation_script.modify_harness_flag is currently connected only for --platform=lerobot_libero")
            if harness_flag != "eval.batch_size":
                _die("--harness-flag must be eval.batch_size")
            if harness_value is None:
                _die("--harness-value is required with --injection-operator=evaluation_script.modify_harness_flag")
            parsed_harness_value = _parse_positive_int(harness_value, "--harness-value")
            if parsed_eval_batch_size != parsed_harness_value:
                _die("--eval-batch-size must match --harness-value")
            if parsed_harness_value == 1:
                _die("--harness-value must be non-default for evaluation_script.modify_harness_flag")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with evaluation_script.modify_harness_flag")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.evaluation_script_harness,
                operator=injection_operator,
                params={"flag": harness_flag, "value": parsed_harness_value},
            )
        elif injection_operator == InjectionOperator.action_change_control_mode:
            if platform != Platform.lerobot_libero:
                _die("action.change_control_mode is currently connected only for --platform=lerobot_libero")
            if libero_control_mode == "relative":
                _die("--libero-control-mode must be non-default with --injection-operator=action.change_control_mode")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with action.change_control_mode")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.action_controller_interface,
                operator=injection_operator,
                params={"control_mode": libero_control_mode},
            )
        elif injection_operator == InjectionOperator.action_drop_postprocessor:
            if platform != Platform.lerobot_libero:
                _die("action.drop_postprocessor is currently connected only for --platform=lerobot_libero")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with action.drop_postprocessor")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.action_controller_interface,
                operator=injection_operator,
                params={},
            )
        elif injection_operator == InjectionOperator.action_reorder_dimensions:
            if platform != Platform.lerobot_libero:
                _die("action.reorder_dimensions is currently connected only for --platform=lerobot_libero")
            if sorted(parsed_action_dimension_permutation) != list(range(7)):
                _die("--action-dimension-permutation must be a permutation of 0,1,2,3,4,5,6")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with action.reorder_dimensions")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.action_controller_interface,
                operator=injection_operator,
                params={"permutation": parsed_action_dimension_permutation},
            )
        elif injection_operator == InjectionOperator.observation_swap_camera_keys:
            if platform != Platform.lerobot_libero:
                _die("observation.swap_camera_keys is currently connected only for --platform=lerobot_libero")
            if not libero_camera_swap:
                _die("--libero-camera-swap is required with --injection-operator=observation.swap_camera_keys")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.swap_camera_keys")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={
                    "camera_name_mapping": {
                        "agentview_image": "image2",
                        "robot0_eye_in_hand_image": "image",
                    }
                },
            )
        elif injection_operator == InjectionOperator.observation_drop_image_key:
            if platform != Platform.lerobot_libero:
                _die("observation.drop_image_key is currently connected only for --platform=lerobot_libero")
            if libero_camera_name == "agentview_image,robot0_eye_in_hand_image":
                _die("--libero-camera-name must name a single camera with --injection-operator=observation.drop_image_key")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.drop_image_key")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.drop_image_key")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"camera_name": libero_camera_name},
            )
        elif injection_operator == InjectionOperator.observation_image_flip:
            if platform != Platform.lerobot_libero:
                _die("observation.image_flip is currently connected only for --platform=lerobot_libero")
            if libero_image_flip_axis not in {"horizontal", "vertical", "both"}:
                _die("--libero-image-flip-axis must be horizontal, vertical, or both")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.image_flip")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.image_flip")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"axis": libero_image_flip_axis},
            )
        elif injection_operator == InjectionOperator.observation_image_blackout:
            if platform != Platform.lerobot_libero:
                _die("observation.image_blackout is currently connected only for --platform=lerobot_libero")
            if libero_image_blackout_value is None:
                _die("--libero-image-blackout-value is required with observation.image_blackout")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.image_blackout")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.image_blackout")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"value": libero_image_blackout_value},
            )
        elif injection_operator == InjectionOperator.observation_state_blackout:
            if platform != Platform.lerobot_libero:
                _die("observation.state_blackout is currently connected only for --platform=lerobot_libero")
            if libero_state_blackout_value is None:
                _die("--libero-state-blackout-value is required with observation.state_blackout")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.state_blackout")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.state_blackout")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"keys": parsed_libero_state_keys, "value": libero_state_blackout_value},
            )
        elif injection_operator == InjectionOperator.observation_state_noise:
            if platform != Platform.lerobot_libero:
                _die("observation.state_noise is currently connected only for --platform=lerobot_libero")
            if libero_state_noise_std is None or libero_state_noise_std <= 0:
                _die("--libero-state-noise-std must be positive with observation.state_noise")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.state_noise")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.state_noise")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"keys": parsed_libero_state_keys, "std": libero_state_noise_std},
            )
        elif injection_operator == InjectionOperator.observation_state_key_drop:
            if platform != Platform.lerobot_libero:
                _die("observation.state_key_drop is currently connected only for --platform=lerobot_libero")
            if libero_camera_swap:
                _die("--libero-camera-swap cannot be used with observation.state_key_drop")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with observation.state_key_drop")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=injection_operator,
                params={"keys": parsed_libero_state_keys},
            )
        elif injection_operator == InjectionOperator.checkpoint_config_feature_mismatch:
            if platform != Platform.lerobot_libero:
                _die("checkpoint.config_feature_mismatch is currently connected only for --platform=lerobot_libero")
            if checkpoint_overlay_mode != "postprocessor_action_norm_identity":
                _die("--checkpoint-overlay-mode must be postprocessor_action_norm_identity")
            if action_scale_multiplier is not None or reset_seed_offset is not None:
                _die("--action-scale-multiplier/--reset-seed-offset cannot be used with checkpoint.config_feature_mismatch")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.checkpoint_config_compatibility,
                operator=injection_operator,
                params={"overlay_mode": checkpoint_overlay_mode},
            )
        elif injection_operator == InjectionOperator.checkpoint_remove_processor_stats:
            if platform != Platform.lerobot_libero:
                _die("checkpoint.remove_processor_stats is currently connected only for --platform=lerobot_libero")
            if not allow_failure:
                _die("--allow-failure is required with checkpoint.remove_processor_stats")
            checkpoint_overlay_mode = "remove_processor_stats"
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.checkpoint_config_compatibility,
                operator=injection_operator,
                params={},
            )
        elif injection_operator == InjectionOperator.dataset_remove_feature_column:
            if platform != Platform.lerobot_libero:
                _die("dataset.remove_feature_column is currently connected only for --platform=lerobot_libero")
            if dataset_path is None:
                _die("--dataset-path is required with dataset.remove_feature_column")
            if dataset_feature_key is None:
                _die("--dataset-feature-key is required with dataset.remove_feature_column")
            if not allow_failure:
                _die("--allow-failure is required with dataset.remove_feature_column")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.data_dataset_format,
                operator=injection_operator,
                params={"feature_key": dataset_feature_key},
            )
        elif injection_operator == InjectionOperator.code_semantic_bug_flag:
            if platform != Platform.lerobot_libero:
                _die("code.semantic_bug_flag is currently connected only for --platform=lerobot_libero")
            allowed_flags = {
                "zero_action_output",
                "freeze_first_action",
                "translation_sign_flip",
                "gripper_sign_flip",
            }
            if semantic_bug_flag not in allowed_flags:
                _die(f"--semantic-bug-flag must be one of: {', '.join(sorted(allowed_flags))}")
            if (
                action_scale_multiplier is not None
                or action_dimension_permutation is not None
                or reset_seed_offset is not None
                or harness_flag is not None
                or harness_value is not None
                or libero_image_blackout_value is not None
                or libero_state_blackout_value is not None
                or libero_state_noise_std is not None
                or parsed_episode_length is not None
                or libero_image_flip_axis is not None
                or libero_camera_swap
                or libero_control_mode != "relative"
                or parsed_libero_init_states is not True
                or checkpoint_overlay_mode is not None
                or dataset_path is not None
            ):
                _die("code.semantic_bug_flag cannot be combined with other factor controls")
            injection = InjectionManifest(
                enabled=True,
                factor=AttributionFactor.semantic_code_regression,
                operator=injection_operator,
                params={
                    "flag": semantic_bug_flag,
                    "semantic_change_ref": f"rq2_true_regression::{semantic_bug_flag}",
                },
            )
        else:
            _die(f"{injection_operator.value} is registered but not connected to a real CLI runner overlay yet")
    elif (
        action_scale_multiplier is not None
        or action_dimension_permutation is not None
        or reset_seed_offset is not None
        or harness_flag is not None
        or harness_value is not None
        or libero_image_blackout_value is not None
        or libero_state_blackout_value is not None
        or libero_state_noise_std is not None
        or semantic_bug_flag is not None
    ):
        _die(
            "--action-scale-multiplier/--reset-seed-offset/--harness-*/--libero-image-blackout-value/"
            "--libero-state-*/--action-dimension-permutation/--semantic-bug-flag require --injection-operator"
        )

    request = RunRequest(
        platform=platform,
        run_id=run_id,
        role=role,
        suite=suite,
        task_ids=parsed_task_ids,
        seed=seed,
        episodes=parsed_episodes,
        output_root=ensure_output_root(output_root),
        policy_path=policy_path,
        libero_env=libero_env,
        mujoco_env=mujoco_env,
        obs_type=obs_type,
        camera_size=parsed_camera_size,
        episode_length=parsed_episode_length,
        libero_control_mode=libero_control_mode,
        libero_camera_name=libero_camera_name,
        libero_camera_name_mapping=(
            {"agentview_image": "image2", "robot0_eye_in_hand_image": "image"}
            if libero_camera_swap
            else None
        ),
        libero_init_states=parsed_libero_init_states,
        libero_image_flip_axis=libero_image_flip_axis,
        libero_image_blackout_value=libero_image_blackout_value,
        libero_state_keys=parsed_libero_state_keys,
        libero_state_blackout_value=libero_state_blackout_value,
        libero_state_noise_std=libero_state_noise_std,
        checkpoint_overlay_mode=checkpoint_overlay_mode,
        semantic_bug_flag=semantic_bug_flag,
        action_dimension_permutation=parsed_action_dimension_permutation,
        compile_model=parsed_compile_model,
        eval_batch_size=parsed_eval_batch_size,
        use_async_envs=parsed_use_async_envs,
        maniskill_env=maniskill_env,
        control_policy=control_policy,
        obs_mode=obs_mode,
        allow_failure=allow_failure,
        dataset_path=dataset_path,
        dataset_feature_key=dataset_feature_key,
        injection=injection,
    )
    args = request.model_dump(mode="json")
    args["validate_only"] = validate_only
    if validate_only:
        _emit_validated("evaltriage-run", args)
        return
    summary = execute_run(request)
    _emit_validated("evaltriage-run", {"summary": summary.model_dump(mode="json"), "executed": True})


@case_app.command()
def case(
    case_config: Path = typer.Option(..., "--case-config", help="case config 路径。"),
    output_root: Path = typer.Option(
        DEFAULT_OUTPUT_ROOT,
        "--output-root",
        help="EvalTriage 输出根目录。",
    ),
    rerun_k: int = typer.Option(3, "--rerun-k", help="rerun baseline 的 k 值。"),
    replay_budget: str = typer.Option(..., "--replay-budget", help="replay 预算。"),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行后端。",
    ),
) -> None:
    parsed_rerun_k = _parse_positive_int(rerun_k, "--rerun-k")
    if validate_only:
        try:
            cfg = load_config(case_config)
            ensure_output_root(output_root)
            if isinstance(cfg, CaseConfig):
                validate_case_existing_runs(cfg, output_root)
        except (ConfigError, ValueError) as exc:
            _die(str(exc))
    args = {
        "case_config": case_config,
        "output_root": output_root,
        "rerun_k": parsed_rerun_k,
        "replay_budget": replay_budget,
        "validate_only": validate_only,
    }
    if validate_only:
        _emit_validated("evaltriage-case", args)
        return
    case_record = run_case(case_config, output_root, parsed_rerun_k, replay_budget)
    _emit_validated("evaltriage-case", {"case": case_record.model_dump(mode="json"), "executed": True})


@aggregate_app.command()
def aggregate(
    cases_root: Path = typer.Option(..., "--cases-root", help="cases 输出根目录。"),
    output_dir: Path = typer.Option(..., "--output-dir", help="metrics 输出目录。"),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行后端。",
    ),
) -> None:
    args = {
        "cases_root": cases_root,
        "output_dir": output_dir,
        "validate_only": validate_only,
    }
    if validate_only:
        try:
            ensure_within_output_root(cases_root)
            ensure_within_output_root(output_dir)
        except ValueError as exc:
            _die(str(exc))
        _emit_validated("evaltriage-aggregate", args)
        return
    ensure_within_output_root(cases_root)
    ensure_within_output_root(output_dir)
    out = aggregate_cases(cases_root, output_dir)
    _emit_validated("evaltriage-aggregate", {"output_dir": out, "executed": True})


@ablate_app.command()
def ablate(
    cases_root: Path = typer.Option(..., "--cases-root", help="case artifacts 根目录。"),
    include_prefix: list[str] = typer.Option(
        ...,
        "--include-prefix",
        help="只纳入 case_id/path basename 以该前缀开头的 case；可重复传入。",
    ),
    output_dir: Path = typer.Option(..., "--output-dir", help="ablation CSV 输出目录。"),
    thresholds_path: Path = typer.Option(
        Path("configs/thresholds/validation_lerobot_libero.yaml"),
        "--thresholds-path",
        help="重新计算 ablation 时使用的阈值配置。",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行聚合。",
    ),
) -> None:
    args = {
        "cases_root": cases_root,
        "include_prefix": include_prefix,
        "output_dir": output_dir,
        "thresholds_path": thresholds_path,
        "validate_only": validate_only,
    }
    if not include_prefix:
        _die("--include-prefix must be provided at least once")
    if validate_only:
        try:
            ensure_within_output_root(cases_root)
            ensure_within_output_root(output_dir)
            load_config(thresholds_path)
        except (ValueError, ConfigError) as exc:
            _die(str(exc))
        _emit_validated("evaltriage-ablate", args)
        return
    ensure_within_output_root(cases_root)
    ensure_within_output_root(output_dir)
    out = aggregate_ablation(cases_root, output_dir, include_prefix, thresholds_path)
    _emit_validated("evaltriage-ablate", {"output_dir": out, "executed": True})


@rq2_status_app.command()
def rq2_status(
    cases_root: Path = typer.Option(..., "--cases-root", help="case artifacts 根目录。"),
    include_prefix: list[str] = typer.Option(
        ...,
        "--include-prefix",
        help="只纳入 case_id/path basename 以该前缀开头的 case；可重复传入。",
    ),
    output_dir: Path = typer.Option(..., "--output-dir", help="RQ2 status CSV 输出目录。"),
    thresholds_path: Path = typer.Option(
        Path("configs/thresholds/validation_lerobot_libero.yaml"),
        "--thresholds-path",
        help="重新计算 RQ2 status 时使用的阈值配置。",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行聚合。",
    ),
) -> None:
    args = {
        "cases_root": cases_root,
        "include_prefix": include_prefix,
        "output_dir": output_dir,
        "thresholds_path": thresholds_path,
        "validate_only": validate_only,
    }
    if not include_prefix:
        _die("--include-prefix must be provided at least once")
    if validate_only:
        try:
            ensure_within_output_root(cases_root)
            ensure_within_output_root(output_dir)
            load_config(thresholds_path)
        except (ValueError, ConfigError) as exc:
            _die(str(exc))
        _emit_validated("evaltriage-rq2-status", args)
        return
    ensure_within_output_root(cases_root)
    ensure_within_output_root(output_dir)
    out = aggregate_rq2_status(cases_root, output_dir, include_prefix, thresholds_path)
    _emit_validated("evaltriage-rq2-status", {"output_dir": out, "executed": True})


@artifact_app.command()
def artifact(
    output_dir: Path = typer.Option(..., "--output-dir", help="artifact 输出目录。"),
    sample_runs_root: Path | None = typer.Option(
        None,
        "--sample-runs-root",
        help="sample runs 输入目录。",
    ),
    sample_cases_root: Path | None = typer.Option(
        None,
        "--sample-cases-root",
        help="sample cases 输入目录。",
    ),
    precomputed_metrics_dir: Path | None = typer.Option(
        None,
        "--precomputed-metrics-dir",
        help="precomputed metrics 输入目录。",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="只校验参数，不执行后端。",
    ),
) -> None:
    args = {
        "output_dir": output_dir,
        "sample_runs_root": sample_runs_root,
        "sample_cases_root": sample_cases_root,
        "precomputed_metrics_dir": precomputed_metrics_dir,
        "validate_only": validate_only,
    }
    if validate_only:
        try:
            ensure_within_output_root(output_dir)
        except ValueError as exc:
            _die(str(exc))
        _emit_validated("evaltriage-artifact", args)
        return
    ensure_within_output_root(output_dir)
    out = build_artifact(output_dir, sample_runs_root, sample_cases_root, precomputed_metrics_dir)
    _emit_validated("evaltriage-artifact", {"output_dir": out, "executed": True})


def _invoke(app: typer.Typer, prog_name: str, argv: Sequence[str] | None = None) -> None:
    kwargs: dict[str, Any] = {"prog_name": prog_name}
    if argv is not None:
        kwargs["args"] = list(argv)
    app(**kwargs)


def run_main(argv: Sequence[str] | None = None) -> None:
    _invoke(run_app, "evaltriage-run", argv)


def case_main(argv: Sequence[str] | None = None) -> None:
    _invoke(case_app, "evaltriage-case", argv)


def aggregate_main(argv: Sequence[str] | None = None) -> None:
    _invoke(aggregate_app, "evaltriage-aggregate", argv)


def ablate_main(argv: Sequence[str] | None = None) -> None:
    _invoke(ablate_app, "evaltriage-ablate", argv)


def rq2_status_main(argv: Sequence[str] | None = None) -> None:
    _invoke(rq2_status_app, "evaltriage-rq2-status", argv)


def artifact_main(argv: Sequence[str] | None = None) -> None:
    _invoke(artifact_app, "evaltriage-artifact", argv)
