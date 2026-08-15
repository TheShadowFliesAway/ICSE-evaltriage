"""Registry of required EvalTriage injection operators."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import (
    AttributionFactor,
    DeviationSymptom,
    DiagnosisStatus,
    InjectionOperator,
    Platform,
    RQ1FactorCategory,
    RQ1SupportLevel,
)


class OperatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: InjectionOperator
    factor: AttributionFactor
    expected_symptom: DeviationSymptom
    required_platforms: list[Platform]
    config_params: dict[str, str] = Field(default_factory=dict)
    replay_reversal: str
    expected_status: DiagnosisStatus
    expected_factor: AttributionFactor | None
    rq1_factor_category: RQ1FactorCategory
    rq1_evidence_refs: list[str] = Field(default_factory=list)
    rq1_support_level: RQ1SupportLevel = RQ1SupportLevel.synthetic_stress
    validation_checks: list[str] = Field(default_factory=list)


def _spec(
    operator: InjectionOperator,
    factor: AttributionFactor,
    symptom: DeviationSymptom,
    platforms: list[Platform],
    reversal: str,
    rq1_category: RQ1FactorCategory,
    params: dict[str, str] | None = None,
    expected_factor: AttributionFactor | None = None,
) -> OperatorSpec:
    return OperatorSpec(
        operator=operator,
        factor=factor,
        expected_symptom=symptom,
        required_platforms=platforms,
        config_params=params or {},
        replay_reversal=reversal,
        expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
        expected_factor=expected_factor or factor,
        rq1_factor_category=rq1_category,
        validation_checks=["manifest_diff_captures_factor", "current_deviation_detected", "replay_restores_or_reduces_deviation"],
    )


_UNSET = object()


def _custom_spec(
    operator: InjectionOperator,
    factor: AttributionFactor,
    symptom: DeviationSymptom,
    platforms: list[Platform],
    reversal: str,
    rq1_category: RQ1FactorCategory,
    expected_status: DiagnosisStatus,
    params: dict[str, str] | None = None,
    expected_factor: AttributionFactor | None | object = _UNSET,
    support_level: RQ1SupportLevel = RQ1SupportLevel.synthetic_stress,
    validation_checks: list[str] | None = None,
) -> OperatorSpec:
    return OperatorSpec(
        operator=operator,
        factor=factor,
        expected_symptom=symptom,
        required_platforms=platforms,
        config_params=params or {},
        replay_reversal=reversal,
        expected_status=expected_status,
        expected_factor=factor if expected_factor is _UNSET else expected_factor,
        rq1_factor_category=rq1_category,
        rq1_support_level=support_level,
        validation_checks=validation_checks
        or ["manifest_diff_captures_factor", "current_deviation_detected"],
    )


OPERATORS: dict[InjectionOperator, OperatorSpec] = {
    InjectionOperator.eval_protocol_change_episode_length: _spec(
        InjectionOperator.eval_protocol_change_episode_length,
        AttributionFactor.evaluation_protocol_metric,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_eval_protocol",
        RQ1FactorCategory.evaluation_protocol_metric,
        {"episode_length": "integer"},
    ),
    InjectionOperator.eval_protocol_change_success_aggregation: _spec(
        InjectionOperator.eval_protocol_change_success_aggregation,
        AttributionFactor.evaluation_protocol_metric,
        DeviationSymptom.reward_score_metric_mismatch,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_eval_protocol",
        RQ1FactorCategory.evaluation_protocol_metric,
    ),
    InjectionOperator.evaluation_script_modify_harness_flag: _spec(
        InjectionOperator.evaluation_script_modify_harness_flag,
        AttributionFactor.evaluation_script_harness,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_eval_protocol",
        RQ1FactorCategory.evaluation_script_harness,
        {"flag": "string", "value": "integer"},
    ),
    InjectionOperator.action_scale_multiplier: _spec(
        InjectionOperator.action_scale_multiplier,
        AttributionFactor.action_controller_interface,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_action_interface",
        RQ1FactorCategory.action_controller_interface,
        {"multiplier": "float"},
    ),
    InjectionOperator.action_change_control_mode: _spec(
        InjectionOperator.action_change_control_mode,
        AttributionFactor.action_controller_interface,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero],
        "restore_action_interface",
        RQ1FactorCategory.action_controller_interface,
        {"control_mode": "string"},
    ),
    InjectionOperator.action_drop_postprocessor: _spec(
        InjectionOperator.action_drop_postprocessor,
        AttributionFactor.action_controller_interface,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero],
        "restore_action_interface",
        RQ1FactorCategory.action_controller_interface,
    ),
    InjectionOperator.action_reorder_dimensions: _spec(
        InjectionOperator.action_reorder_dimensions,
        AttributionFactor.action_controller_interface,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_action_interface",
        RQ1FactorCategory.action_controller_interface,
        {"permutation": "list[int]"},
    ),
    InjectionOperator.observation_swap_camera_keys: _spec(
        InjectionOperator.observation_swap_camera_keys,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"camera_name_mapping": "dict[str,str]"},
    ),
    InjectionOperator.observation_image_flip: _spec(
        InjectionOperator.observation_image_flip,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"axis": "string"},
    ),
    InjectionOperator.observation_image_blackout: _spec(
        InjectionOperator.observation_image_blackout,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"value": "float"},
    ),
    InjectionOperator.observation_state_blackout: _spec(
        InjectionOperator.observation_state_blackout,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"keys": "list[str]", "value": "float"},
    ),
    InjectionOperator.observation_state_noise: _spec(
        InjectionOperator.observation_state_noise,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.rollout_behavior_anomaly,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"keys": "list[str]", "std": "float"},
    ),
    InjectionOperator.observation_state_key_drop: _spec(
        InjectionOperator.observation_state_key_drop,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.evaluation_crash_or_failure,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"keys": "list[str]"},
    ),
    InjectionOperator.observation_drop_image_key: _spec(
        InjectionOperator.observation_drop_image_key,
        AttributionFactor.observation_sensor_preprocessing,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero],
        "restore_observation_pipeline",
        RQ1FactorCategory.observation_sensor_preprocessing,
        {"camera_name": "string"},
    ),
    InjectionOperator.checkpoint_remove_processor_stats: _spec(
        InjectionOperator.checkpoint_remove_processor_stats,
        AttributionFactor.checkpoint_config_compatibility,
        DeviationSymptom.evaluation_crash_or_failure,
        [Platform.lerobot_libero],
        "restore_checkpoint_config",
        RQ1FactorCategory.checkpoint_config_compatibility,
    ),
    InjectionOperator.checkpoint_config_feature_mismatch: _spec(
        InjectionOperator.checkpoint_config_feature_mismatch,
        AttributionFactor.checkpoint_config_compatibility,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero],
        "restore_checkpoint_config",
        RQ1FactorCategory.checkpoint_config_compatibility,
        {"overlay_mode": "string"},
    ),
    InjectionOperator.reset_disable_fixed_init_state: _spec(
        InjectionOperator.reset_disable_fixed_init_state,
        AttributionFactor.reset_or_initial_state,
        DeviationSymptom.evaluation_instability_or_flakiness,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_seed_or_init",
        RQ1FactorCategory.reset_or_initial_state,
        {"seed_offset": "optional_integer", "init_states": "optional_boolean"},
    ),
    InjectionOperator.maniskill_change_object_pose: _spec(
        InjectionOperator.maniskill_change_object_pose,
        AttributionFactor.object_scene_task_initialization,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.maniskill],
        "restore_seed_or_init",
        RQ1FactorCategory.object_scene_task_initialization,
    ),
    InjectionOperator.runtime_switch_mujoco_env: _spec(
        InjectionOperator.runtime_switch_mujoco_env,
        AttributionFactor.dependency_runtime_environment,
        DeviationSymptom.setup_sensitive_result,
        [Platform.lerobot_libero],
        "restore_runtime_env",
        RQ1FactorCategory.dependency_runtime_environment,
        {"conda_env": "string"},
    ),
    InjectionOperator.runtime_switch_incompatible_env: _spec(
        InjectionOperator.runtime_switch_incompatible_env,
        AttributionFactor.dependency_runtime_environment,
        DeviationSymptom.evaluation_crash_or_failure,
        [Platform.lerobot_libero],
        "restore_runtime_env",
        RQ1FactorCategory.dependency_runtime_environment,
        {"conda_env": "string"},
    ),
    InjectionOperator.dataset_remove_feature_column: _spec(
        InjectionOperator.dataset_remove_feature_column,
        AttributionFactor.data_dataset_format,
        DeviationSymptom.evaluation_crash_or_failure,
        [Platform.lerobot_libero],
        "restore_dataset_format",
        RQ1FactorCategory.data_dataset_format,
        {"feature_key": "string"},
    ),
    InjectionOperator.dataset_corrupt_video_or_parquet_reference: _spec(
        InjectionOperator.dataset_corrupt_video_or_parquet_reference,
        AttributionFactor.data_dataset_format,
        DeviationSymptom.evaluation_crash_or_failure,
        [Platform.lerobot_libero],
        "restore_dataset_format",
        RQ1FactorCategory.data_dataset_format,
    ),
    InjectionOperator.code_semantic_bug_flag: _spec(
        InjectionOperator.code_semantic_bug_flag,
        AttributionFactor.semantic_code_regression,
        DeviationSymptom.success_rate_drop_or_mismatch,
        [Platform.lerobot_libero, Platform.maniskill],
        "no_external_factor_reversal",
        RQ1FactorCategory.evaluation_script_harness,
    ),
    InjectionOperator.manifest_hide_factor_fields: _spec(
        InjectionOperator.manifest_hide_factor_fields,
        AttributionFactor.evaluation_script_harness,
        DeviationSymptom.unknown_or_not_applicable,
        [Platform.lerobot_libero, Platform.maniskill],
        "restore_manifest_fields",
        RQ1FactorCategory.unknown_or_not_specified,
        {"fields": "list[str]"},
    ),
}

OPERATORS[InjectionOperator.code_semantic_bug_flag] = _custom_spec(
    InjectionOperator.code_semantic_bug_flag,
    AttributionFactor.semantic_code_regression,
    DeviationSymptom.success_rate_drop_or_mismatch,
    [Platform.lerobot_libero, Platform.maniskill],
    "no_external_factor_reversal",
    RQ1FactorCategory.evaluation_script_harness,
    DiagnosisStatus.likely_true_regression,
    params={"flag": "string", "semantic_change_ref": "string"},
    validation_checks=[
        "semantic_change_evidence_present",
        "external_factor_replays_do_not_recover",
        "current_deviation_detected",
    ],
)

OPERATORS[InjectionOperator.manifest_hide_factor_fields] = _custom_spec(
    InjectionOperator.manifest_hide_factor_fields,
    AttributionFactor.evaluation_script_harness,
    DeviationSymptom.unknown_or_not_applicable,
    [Platform.lerobot_libero, Platform.maniskill],
    "restore_manifest_fields",
    RQ1FactorCategory.unknown_or_not_specified,
    DiagnosisStatus.unknown_engineering_factor,
    params={"fields": "list[str]"},
    expected_factor=None,
    validation_checks=[
        "required_manifest_fields_missing",
        "diagnosis_abstains_without_high_confidence_factor",
    ],
)

PARAM_TYPES = {
    "integer": int,
    "float": (int, float),
    "string": str,
    "boolean": bool,
    "list[str]": list,
    "list[int]": list,
    "dict[str,str]": dict,
    "optional_integer": int,
    "optional_boolean": bool,
}


def get_operator_spec(operator: InjectionOperator | str) -> OperatorSpec:
    op = InjectionOperator(operator)
    return OPERATORS[op]


def list_operator_specs() -> list[OperatorSpec]:
    return list(OPERATORS.values())


def validate_operator_params(operator: InjectionOperator | str, params: dict[str, Any]) -> None:
    spec = get_operator_spec(operator)
    allowed = set(spec.config_params)
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"unknown params for {spec.operator.value}: {unknown}")
    for name, kind in spec.config_params.items():
        optional = kind.startswith("optional_")
        if name not in params:
            if optional:
                continue
            raise ValueError(f"missing param for {spec.operator.value}: {name}")
        expected = PARAM_TYPES.get(kind)
        if expected is None:
            continue
        value = params[name]
        if kind in {"integer", "optional_integer"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"param {name} for {spec.operator.value} must be {kind}")
            continue
        if kind == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"param {name} for {spec.operator.value} must be {kind}")
            continue
        if not isinstance(value, expected):
            raise ValueError(f"param {name} for {spec.operator.value} must be {kind}")
        if kind == "list[str]" and not all(isinstance(item, str) for item in value):
            raise ValueError(f"param {name} for {spec.operator.value} must be list[str]")
        if kind == "dict[str,str]" and not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
            raise ValueError(f"param {name} for {spec.operator.value} must be dict[str,str]")


def validate_operator_params_for_platform(
    operator: InjectionOperator | str,
    params: dict[str, Any],
    platform: Platform,
) -> None:
    validate_operator_params(operator, params)
    op = InjectionOperator(operator)
    if op != InjectionOperator.reset_disable_fixed_init_state:
        return
    if platform == Platform.maniskill:
        if "seed_offset" not in params:
            raise ValueError("reset.disable_fixed_init_state on ManiSkill requires seed_offset")
        if "init_states" in params:
            raise ValueError("reset.disable_fixed_init_state on ManiSkill does not use init_states")
    elif platform == Platform.lerobot_libero:
        if params.get("init_states") is not False:
            raise ValueError("reset.disable_fixed_init_state on LeRobot/LIBERO requires init_states=false")
        if "seed_offset" in params:
            raise ValueError("reset.disable_fixed_init_state on LeRobot/LIBERO does not use seed_offset")
