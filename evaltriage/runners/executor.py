"""Run executor that writes the standard EvalTriage run outputs."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from ..io import write_json, write_jsonl
from ..injection.registry import get_operator_spec, validate_operator_params_for_platform
from ..manifest.collect import base_manifest
from ..paths import ensure_output_root, run_paths
from ..schemas import (
    CostRecord,
    ExecutionStatus,
    FailureRecord,
    InjectionOperator,
    Platform,
    RunMetrics,
    RunRequest,
    RunSummary,
)
from .base import RunnerExecutionError
from .lerobot_libero import run_lerobot_libero
from .maniskill import run_maniskill


def _finalize_staged_value(value: str | None, staging_dir: Path, final_dir: Path) -> str | None:
    if value is None:
        return None
    return value.replace(str(staging_dir), str(final_dir))


def _finalize_episode_paths(episodes, staging_dir: Path, final_dir: Path):
    return [
        episode.model_copy(update={"video_path": _finalize_staged_value(episode.video_path, staging_dir, final_dir)})
        for episode in episodes
    ]


def _finalize_manifest_paths(manifest, staging_dir: Path, final_dir: Path):
    policy_path = _finalize_staged_value(manifest.policy.path, staging_dir, final_dir)
    command = _finalize_staged_value(manifest.evaluation.command, staging_dir, final_dir) or manifest.evaluation.command
    return manifest.model_copy(
        update={
            "policy": manifest.policy.model_copy(update={"path": policy_path}),
            "evaluation": manifest.evaluation.model_copy(update={"command": command}),
        }
    )


REAL_INJECTION_BACKENDS = {
    (Platform.lerobot_libero, InjectionOperator.eval_protocol_change_episode_length),
    (Platform.lerobot_libero, InjectionOperator.evaluation_script_modify_harness_flag),
    (Platform.lerobot_libero, InjectionOperator.action_change_control_mode),
    (Platform.lerobot_libero, InjectionOperator.action_drop_postprocessor),
    (Platform.lerobot_libero, InjectionOperator.action_reorder_dimensions),
    (Platform.lerobot_libero, InjectionOperator.observation_swap_camera_keys),
    (Platform.lerobot_libero, InjectionOperator.observation_drop_image_key),
    (Platform.lerobot_libero, InjectionOperator.observation_image_flip),
    (Platform.lerobot_libero, InjectionOperator.observation_image_blackout),
    (Platform.lerobot_libero, InjectionOperator.observation_state_blackout),
    (Platform.lerobot_libero, InjectionOperator.observation_state_noise),
    (Platform.lerobot_libero, InjectionOperator.observation_state_key_drop),
    (Platform.lerobot_libero, InjectionOperator.checkpoint_config_feature_mismatch),
    (Platform.lerobot_libero, InjectionOperator.checkpoint_remove_processor_stats),
    (Platform.lerobot_libero, InjectionOperator.reset_disable_fixed_init_state),
    (Platform.lerobot_libero, InjectionOperator.runtime_switch_mujoco_env),
    (Platform.lerobot_libero, InjectionOperator.runtime_switch_incompatible_env),
    (Platform.lerobot_libero, InjectionOperator.dataset_remove_feature_column),
    (Platform.lerobot_libero, InjectionOperator.code_semantic_bug_flag),
    (Platform.maniskill, InjectionOperator.action_scale_multiplier),
    (Platform.maniskill, InjectionOperator.reset_disable_fixed_init_state),
}


def _validate_real_injection_backend(request: RunRequest) -> None:
    if not request.injection.enabled:
        return
    spec = get_operator_spec(request.injection.operator)
    validate_operator_params_for_platform(spec.operator, request.injection.params, request.platform)
    if request.platform not in spec.required_platforms:
        platforms = ", ".join(platform.value for platform in spec.required_platforms)
        raise RuntimeError(f"{spec.operator.value} is not valid for {request.platform.value}; expected one of {platforms}")
    if request.injection.factor != spec.factor:
        raise RuntimeError(
            f"injection factor {request.injection.factor.value if request.injection.factor else None} "
            f"does not match operator factor {spec.factor.value}"
        )
    if (request.platform, spec.operator) not in REAL_INJECTION_BACKENDS:
        raise RuntimeError(
            f"injection operator {spec.operator.value} is registered but not yet connected to a real "
            f"{request.platform.value} runner overlay; refusing to write non-injected run outputs"
        )
    if spec.operator == InjectionOperator.action_scale_multiplier and request.control_policy != "random":
        raise RuntimeError(
            "ManiSkill action.scale_multiplier is currently connected only for control_policy=random; "
            "motionplanning controls actions inside the solver and must get a separate overlay"
        )
    if spec.operator == InjectionOperator.eval_protocol_change_episode_length:
        expected = request.injection.params["episode_length"]
        if request.episode_length != expected:
            raise RuntimeError(
                "eval_protocol.change_episode_length requires request.episode_length to match "
                "injection.params['episode_length']"
            )
    if spec.operator == InjectionOperator.evaluation_script_modify_harness_flag:
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("evaluation_script.modify_harness_flag is currently connected only for LeRobot/LIBERO")
        flag = request.injection.params["flag"]
        value = request.injection.params["value"]
        if flag != "eval.batch_size":
            raise RuntimeError(f"unsupported evaluation_script.modify_harness_flag flag: {flag}")
        if request.eval_batch_size != value:
            raise RuntimeError(
                "evaluation_script.modify_harness_flag requires request.eval_batch_size to match "
                "injection.params['value']"
            )
        if value == 1:
            raise RuntimeError("evaluation_script.modify_harness_flag requires a non-default eval_batch_size")
    if spec.operator == InjectionOperator.action_change_control_mode:
        expected = request.injection.params["control_mode"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("action.change_control_mode is currently connected only for LeRobot/LIBERO")
        if request.libero_control_mode != expected:
            raise RuntimeError(
                "action.change_control_mode requires request.libero_control_mode to match "
                "injection.params['control_mode']"
            )
        if expected == "relative":
            raise RuntimeError("action.change_control_mode requires a non-default LeRobot/LIBERO control mode")
    if spec.operator == InjectionOperator.action_drop_postprocessor:
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("action.drop_postprocessor is currently connected only for LeRobot/LIBERO")
    if spec.operator == InjectionOperator.action_reorder_dimensions:
        expected = request.injection.params["permutation"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("action.reorder_dimensions is currently connected only for LeRobot/LIBERO")
        if request.action_dimension_permutation != expected:
            raise RuntimeError(
                "action.reorder_dimensions requires request.action_dimension_permutation to match "
                "injection.params['permutation']"
            )
        if sorted(expected) != list(range(7)):
            raise RuntimeError("action.reorder_dimensions requires a permutation of action dimensions 0..6")
    if spec.operator == InjectionOperator.observation_swap_camera_keys:
        expected = request.injection.params["camera_name_mapping"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.swap_camera_keys is currently connected only for LeRobot/LIBERO")
        if request.libero_camera_name_mapping != expected:
            raise RuntimeError(
                "observation.swap_camera_keys requires request.libero_camera_name_mapping to match "
                "injection.params['camera_name_mapping']"
            )
        if expected == {"agentview_image": "image", "robot0_eye_in_hand_image": "image2"}:
            raise RuntimeError("observation.swap_camera_keys requires a non-default camera_name_mapping")
    if spec.operator == InjectionOperator.observation_drop_image_key:
        expected = request.injection.params["camera_name"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.drop_image_key is currently connected only for LeRobot/LIBERO")
        if request.libero_camera_name != expected:
            raise RuntimeError(
                "observation.drop_image_key requires request.libero_camera_name to match "
                "injection.params['camera_name']"
            )
        if expected == "agentview_image,robot0_eye_in_hand_image":
            raise RuntimeError("observation.drop_image_key requires a single-camera camera_name")
    if spec.operator == InjectionOperator.observation_image_flip:
        expected = request.injection.params["axis"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.image_flip is currently connected only for LeRobot/LIBERO")
        if request.libero_image_flip_axis != expected:
            raise RuntimeError(
                "observation.image_flip requires request.libero_image_flip_axis to match "
                "injection.params['axis']"
            )
    if spec.operator == InjectionOperator.observation_image_blackout:
        expected = request.injection.params["value"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.image_blackout is currently connected only for LeRobot/LIBERO")
        if request.libero_image_blackout_value != expected:
            raise RuntimeError(
                "observation.image_blackout requires request.libero_image_blackout_value to match "
                "injection.params['value']"
            )
    if spec.operator == InjectionOperator.observation_state_blackout:
        expected_keys = request.injection.params["keys"]
        expected_value = request.injection.params["value"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.state_blackout is currently connected only for LeRobot/LIBERO")
        if request.libero_state_keys != expected_keys:
            raise RuntimeError(
                "observation.state_blackout requires request.libero_state_keys to match "
                "injection.params['keys']"
            )
        if request.libero_state_blackout_value != expected_value:
            raise RuntimeError(
                "observation.state_blackout requires request.libero_state_blackout_value to match "
                "injection.params['value']"
            )
    if spec.operator == InjectionOperator.observation_state_noise:
        expected_keys = request.injection.params["keys"]
        expected_std = request.injection.params["std"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.state_noise is currently connected only for LeRobot/LIBERO")
        if request.libero_state_keys != expected_keys:
            raise RuntimeError(
                "observation.state_noise requires request.libero_state_keys to match "
                "injection.params['keys']"
            )
        if request.libero_state_noise_std != expected_std:
            raise RuntimeError(
                "observation.state_noise requires request.libero_state_noise_std to match "
                "injection.params['std']"
            )
        if expected_std <= 0:
            raise RuntimeError("observation.state_noise requires a positive std")
    if spec.operator == InjectionOperator.observation_state_key_drop:
        expected_keys = request.injection.params["keys"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("observation.state_key_drop is currently connected only for LeRobot/LIBERO")
        if request.libero_state_keys != expected_keys:
            raise RuntimeError(
                "observation.state_key_drop requires request.libero_state_keys to match "
                "injection.params['keys']"
            )
    if spec.operator == InjectionOperator.checkpoint_config_feature_mismatch:
        expected = request.injection.params["overlay_mode"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("checkpoint.config_feature_mismatch is currently connected only for LeRobot/LIBERO")
        if request.checkpoint_overlay_mode != expected:
            raise RuntimeError(
                "checkpoint.config_feature_mismatch requires request.checkpoint_overlay_mode to match "
                "injection.params['overlay_mode']"
            )
        if expected != "postprocessor_action_norm_identity":
            raise RuntimeError(f"unsupported checkpoint overlay mode: {expected}")
    if spec.operator == InjectionOperator.checkpoint_remove_processor_stats:
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("checkpoint.remove_processor_stats is currently connected only for LeRobot/LIBERO")
        if request.checkpoint_overlay_mode != "remove_processor_stats":
            raise RuntimeError("checkpoint.remove_processor_stats requires checkpoint_overlay_mode=remove_processor_stats")
    if spec.operator == InjectionOperator.reset_disable_fixed_init_state:
        if request.platform == Platform.lerobot_libero:
            expected = request.injection.params["init_states"]
            if request.libero_init_states != expected:
                raise RuntimeError(
                    "reset.disable_fixed_init_state requires request.libero_init_states to match "
                    "injection.params['init_states']"
                )
            if expected is not False:
                raise RuntimeError("reset.disable_fixed_init_state requires libero_init_states=false")
        elif request.platform == Platform.maniskill:
            if "seed_offset" not in request.injection.params:
                raise RuntimeError("reset.disable_fixed_init_state requires seed_offset on ManiSkill")
    if spec.operator == InjectionOperator.runtime_switch_mujoco_env:
        expected = request.injection.params["conda_env"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("runtime.switch_mujoco_env is currently connected only for LeRobot/LIBERO")
        if request.libero_env != expected:
            raise RuntimeError(
                "runtime.switch_mujoco_env requires request.libero_env to match "
                "injection.params['conda_env']"
            )
        if request.mujoco_env != expected:
            raise RuntimeError(
                "runtime.switch_mujoco_env requires request.mujoco_env to match "
                "injection.params['conda_env']"
            )
        if expected == "evaltriage-lr":
            raise RuntimeError("runtime.switch_mujoco_env requires a non-default LeRobot/LIBERO env")
    if spec.operator == InjectionOperator.runtime_switch_incompatible_env:
        expected = request.injection.params["conda_env"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("runtime.switch_incompatible_env is currently connected only for LeRobot/LIBERO")
        if request.libero_env != expected:
            raise RuntimeError(
                "runtime.switch_incompatible_env requires request.libero_env to match "
                "injection.params['conda_env']"
            )
        if expected == "evaltriage-lr":
            raise RuntimeError("runtime.switch_incompatible_env requires a non-default LeRobot/LIBERO env")
    if spec.operator == InjectionOperator.dataset_remove_feature_column:
        expected = request.injection.params["feature_key"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("dataset.remove_feature_column is currently connected only for LeRobot/LIBERO")
        if request.dataset_path is None:
            raise RuntimeError("dataset.remove_feature_column requires request.dataset_path")
        if request.dataset_feature_key != expected:
            raise RuntimeError(
                "dataset.remove_feature_column requires request.dataset_feature_key to match "
                "injection.params['feature_key']"
            )
    if spec.operator == InjectionOperator.code_semantic_bug_flag:
        expected = request.injection.params["flag"]
        if request.platform != Platform.lerobot_libero:
            raise RuntimeError("code.semantic_bug_flag is currently connected only for LeRobot/LIBERO")
        if request.semantic_bug_flag != expected:
            raise RuntimeError(
                "code.semantic_bug_flag requires request.semantic_bug_flag to match injection.params['flag']"
            )
        if expected not in {
            "zero_action_output",
            "freeze_first_action",
            "translation_sign_flip",
            "gripper_sign_flip",
        }:
            raise RuntimeError(f"unsupported semantic bug flag: {expected}")
        if not request.injection.params.get("semantic_change_ref"):
            raise RuntimeError("code.semantic_bug_flag requires semantic_change_ref evidence")


def _command_text(command: list[str] | None, staging_dir: Path, final_dir: Path) -> str | None:
    if not command:
        return None
    finalized = [_finalize_staged_value(item, staging_dir, final_dir) or "" for item in command]
    return " ".join(finalized)


def _log_excerpt(path: Path, max_chars: int = 4000) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _failure_benchmark(request: RunRequest) -> str:
    if request.dataset_path is not None:
        return "lerobot_dataset_preflight"
    if request.platform == Platform.lerobot_libero:
        return "libero"
    if request.platform == Platform.maniskill:
        return "maniskill"
    return request.platform.value


def _write_failed_run(
    request: RunRequest,
    exc: Exception,
    staging_dir: Path,
    final_dir: Path,
    staging_paths,
    paths,
) -> RunSummary:
    runner_exc = exc if isinstance(exc, RunnerExecutionError) else None
    command = _command_text(runner_exc.command if runner_exc else None, staging_dir, final_dir)
    if command is None:
        command = f"internal:{request.platform.value}"
    if not staging_paths.logs.exists():
        staging_paths.logs.write_text(f"{type(exc).__name__}: {exc}\n")
    cost = runner_exc.cost if runner_exc else CostRecord()
    metrics = RunMetrics()
    manifest = base_manifest(
        request,
        command=command,
        metrics=metrics,
        cost=cost,
        benchmark=_failure_benchmark(request),
    )
    manifest = _finalize_manifest_paths(manifest, staging_dir, final_dir)
    exit_code = runner_exc.exit_code if runner_exc else None
    failure = FailureRecord(
        run_id=request.run_id,
        case_id=request.case_id,
        role=request.role,
        platform=request.platform,
        factor=request.injection.factor if request.injection.enabled else None,
        operator=request.injection.operator if request.injection.enabled else None,
        failure_kind=runner_exc.failure_kind if runner_exc else "exception",
        stage=runner_exc.stage if runner_exc else "runner",
        exit_code=exit_code,
        signal=(-exit_code if exit_code is not None and exit_code < 0 else None),
        exception_type=type(exc).__name__,
        message=str(exc),
        log_excerpt=_log_excerpt(staging_paths.logs),
        command=command,
        logs_path=str(paths.logs),
        raw_output_path=_finalize_staged_value(runner_exc.raw_output_path, staging_dir, final_dir) if runner_exc else None,
        cost=cost,
    )
    summary = RunSummary(
        run_id=request.run_id,
        case_id=request.case_id,
        role=request.role,
        platform=request.platform,
        benchmark=manifest.benchmark,
        task_suite=request.suite,
        task_ids=request.task_ids,
        seed=request.seed,
        execution_status=ExecutionStatus.failed,
        metrics=metrics,
        cost=cost,
        manifest_path=str(paths.manifest),
        episodes_path=str(paths.episodes),
        logs_path=str(paths.logs),
        raw_output_path=failure.raw_output_path,
        failure_path=str(paths.failure),
    )
    write_json(staging_paths.manifest, manifest)
    write_jsonl(staging_paths.episodes, [])
    write_json(staging_paths.failure, failure)
    write_json(staging_paths.summary, summary)
    staging_dir.rename(paths.run_dir)
    return summary


def execute_run(request: RunRequest) -> RunSummary:
    paths = run_paths(request.run_id, request.output_root)
    if paths.run_dir.exists():
        raise RuntimeError(f"run directory already exists: {paths.run_dir}")
    _validate_real_injection_backend(request)

    root = ensure_output_root(request.output_root)
    staging_dir = root / "runs" / f".staging_{request.run_id}_{uuid.uuid4().hex}"
    staging_paths = run_paths(staging_dir.name, request.output_root)
    staging_dir.mkdir(parents=True, exist_ok=False)
    staging_paths.raw_output_dir.mkdir(parents=True, exist_ok=True)
    try:
        if request.platform == Platform.lerobot_libero:
            result = run_lerobot_libero(request, staging_paths.raw_output_dir, staging_paths.logs)
        elif request.platform == Platform.maniskill:
            result = run_maniskill(request, staging_paths.raw_output_dir, staging_paths.logs)
        else:
            raise RuntimeError(f"unsupported platform: {request.platform}")

        final_command = [
            _finalize_staged_value(item, staging_dir, paths.run_dir) or ""
            for item in result.command
        ] if result.command else None
        command = " ".join(final_command) if final_command else f"internal:{request.platform.value}"
        effective_policy_path = result.effective_policy_path
        manifest_request = request
        if effective_policy_path is not None:
            manifest_request = request.model_copy(update={"policy_path": Path(effective_policy_path)})
        manifest = base_manifest(
            manifest_request,
            command=command,
            metrics=result.metrics,
            cost=result.cost,
            benchmark=result.benchmark,
            runtime_env=result.runtime_env,
        )
        manifest = _finalize_manifest_paths(manifest, staging_dir, paths.run_dir)
        summary = RunSummary(
            run_id=request.run_id,
            case_id=request.case_id,
            role=request.role,
            platform=request.platform,
            benchmark=result.benchmark,
            task_suite=request.suite,
            task_ids=request.task_ids,
            seed=request.seed,
            metrics=result.metrics,
            cost=result.cost,
            manifest_path=str(paths.manifest),
            episodes_path=str(paths.episodes),
            logs_path=str(paths.logs),
            raw_output_path=_finalize_staged_value(result.raw_output_path, staging_dir, paths.run_dir),
        )
        if not result.episodes:
            raise RuntimeError("runner produced zero episodes")
        episodes = _finalize_episode_paths(result.episodes, staging_dir, paths.run_dir)
        write_json(staging_paths.manifest, manifest)
        write_jsonl(staging_paths.episodes, episodes)
        write_json(staging_paths.summary, summary)
        # Commit the completed run atomically within the output filesystem.
        staging_dir.rename(paths.run_dir)
        return summary
    except Exception as exc:
        if request.allow_failure:
            return _write_failed_run(request, exc, staging_dir, paths.run_dir, staging_paths, paths)
        if staging_paths.logs.exists():
            failure_dir = root / "failures" / request.run_id
            failure_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging_paths.logs, failure_dir / "logs.txt")
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
