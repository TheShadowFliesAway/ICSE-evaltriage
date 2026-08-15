"""Manifest collection helpers."""

from __future__ import annotations

from pathlib import Path

from .checksum import sha256_file
from ..runtime import capture_code_manifest, capture_runtime_env
from ..schemas import (
    ActionManifest,
    EvaluationManifest,
    InjectionOperator,
    InjectionManifest,
    Manifest,
    ObservationManifest,
    Platform,
    PolicyManifest,
    ResetManifest,
    RunMetrics,
    RunRequest,
    RuntimeEnvManifest,
)


def _parse_libero_camera_names(camera_name: str) -> list[str]:
    return [item.strip() for item in camera_name.split(",") if item.strip()]


def collect_policy_manifest(policy_path: Path | None) -> PolicyManifest:
    if policy_path is None:
        return PolicyManifest()
    return PolicyManifest(
        path=str(policy_path),
        repo_id="lerobot/pi0_libero_finetuned_v044" if "pi0_libero_finetuned_v044" in str(policy_path) else None,
        checkpoint_checksum=sha256_file(policy_path / "model.safetensors"),
        config_checksum=sha256_file(policy_path / "config.json"),
        preprocessor_checksum=sha256_file(policy_path / "policy_preprocessor.json"),
        postprocessor_checksum=sha256_file(policy_path / "policy_postprocessor.json"),
    )


def base_manifest(
    request: RunRequest,
    *,
    command: str,
    metrics: RunMetrics,
    cost,
    benchmark: str,
    runtime_env: RuntimeEnvManifest | None = None,
) -> Manifest:
    image_keys = []
    camera_names = []
    if request.platform == Platform.lerobot_libero:
        camera_names = _parse_libero_camera_names(request.libero_camera_name)
        default_mapping = {"agentview_image": "image", "robot0_eye_in_hand_image": "image2"}
        mapping = request.libero_camera_name_mapping or default_mapping
        image_keys = [f"observation.images.{mapping[name]}" for name in camera_names if name in mapping]
    action_postprocessing = []
    observation_preprocessing = []
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_scale_multiplier:
        action_postprocessing.append(f"action_scale_multiplier={request.injection.params['multiplier']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_change_control_mode:
        action_postprocessing.append(f"libero_control_mode={request.injection.params['control_mode']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_drop_postprocessor:
        action_postprocessing.append("drop_policy_postprocessor=true")
    if request.injection.enabled and request.injection.operator == InjectionOperator.action_reorder_dimensions:
        action_postprocessing.append(f"action_dimension_permutation={request.injection.params['permutation']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.checkpoint_config_feature_mismatch:
        action_postprocessing.append(f"checkpoint_overlay_mode={request.injection.params['overlay_mode']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.checkpoint_remove_processor_stats:
        action_postprocessing.append("checkpoint_overlay_mode=remove_processor_stats")
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_swap_camera_keys:
        observation_preprocessing.append(f"camera_name_mapping={request.injection.params['camera_name_mapping']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_drop_image_key:
        observation_preprocessing.append(f"camera_name={request.injection.params['camera_name']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_image_flip:
        observation_preprocessing.append(f"image_flip_axis={request.injection.params['axis']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_image_blackout:
        observation_preprocessing.append(f"image_blackout_value={request.injection.params['value']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_blackout:
        observation_preprocessing.append(
            f"state_blackout_keys={request.injection.params['keys']};value={request.injection.params['value']}"
        )
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_noise:
        observation_preprocessing.append(
            f"state_noise_keys={request.injection.params['keys']};std={request.injection.params['std']}"
        )
    if request.injection.enabled and request.injection.operator == InjectionOperator.observation_state_key_drop:
        observation_preprocessing.append(f"state_key_drop_keys={request.injection.params['keys']}")
    if request.injection.enabled and request.injection.operator == InjectionOperator.dataset_remove_feature_column:
        observation_preprocessing.append(f"dataset_remove_feature_column={request.injection.params['feature_key']}")
    code = capture_code_manifest()
    if request.injection.enabled and request.injection.operator == InjectionOperator.code_semantic_bug_flag:
        semantic_ref = request.injection.params.get("semantic_change_ref")
        refs = list(code.semantic_change_refs)
        if isinstance(semantic_ref, str) and semantic_ref and semantic_ref not in refs:
            refs.append(semantic_ref)
        code = code.model_copy(update={"semantic_change_refs": refs})
    reset_seed_offset = None
    if request.injection.enabled and request.injection.operator == InjectionOperator.reset_disable_fixed_init_state:
        reset_seed_offset = request.injection.params.get("seed_offset")
    return Manifest(
        run_id=request.run_id,
        case_id=request.case_id,
        role=request.role,
        platform=request.platform,
        benchmark=benchmark,
        task_suite=request.suite,
        task_ids=request.task_ids,
        seed=request.seed,
        n_episodes=request.episodes,
        policy=collect_policy_manifest(request.policy_path),
        code=code,
        runtime_env=runtime_env or capture_runtime_env(),
        evaluation=EvaluationManifest(
            command=command,
            episode_length=request.episode_length,
            batch_size=request.eval_batch_size,
            use_async_envs=request.use_async_envs,
            compile_model=request.compile_model,
        ),
        observation=ObservationManifest(
            obs_type=request.obs_type if request.platform == Platform.lerobot_libero else request.obs_mode,
            camera_names=camera_names,
            image_keys=image_keys,
            height=request.camera_size if request.platform == Platform.lerobot_libero else None,
            width=request.camera_size if request.platform == Platform.lerobot_libero else None,
            preprocessing=observation_preprocessing,
        ),
        action=ActionManifest(
            action_dim=7 if request.platform == Platform.lerobot_libero else None,
            control_mode=request.libero_control_mode if request.platform == Platform.lerobot_libero else request.control_policy,
            postprocessing=action_postprocessing,
        ),
        reset=ResetManifest(
            init_states=request.libero_init_states if request.platform == Platform.lerobot_libero else None,
            seed_offset=reset_seed_offset if isinstance(reset_seed_offset, int) else None,
        ),
        injection=request.injection or InjectionManifest(),
        metrics=metrics,
        cost=cost,
    )
