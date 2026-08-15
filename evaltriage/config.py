"""Configuration loading and validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .injection.registry import get_operator_spec, validate_operator_params_for_platform
from .paths import ensure_output_root, rq1_evidence_index_path
from .schemas import (
    CaseConfig,
    CoverageStatus,
    DeviationSymptom,
    DiagnosisStatus,
    InjectionOperator,
    ExperimentConfig,
    Platform,
    RQ1SupportLevel,
    ThresholdsConfig,
)


SECRET_MARKERS = ("token", "secret", "api_key", "apikey", "password", "hf_token")


class ConfigError(ValueError):
    """Raised when an EvalTriage config fails semantic validation."""


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        raise ConfigError(f"unsupported config extension: {path}")
    if not isinstance(data, dict):
        raise ConfigError(f"config must be a mapping: {path}")
    return data


def _scan_secrets(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_s = str(key).lower()
            if any(marker in key_s for marker in SECRET_MARKERS):
                raise ConfigError(f"secret-like field is not allowed in config: {'.'.join(path + (str(key),))}")
            _scan_secrets(item, path + (str(key),))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_secrets(item, path + (str(i),))
    elif isinstance(value, str):
        low = value.lower()
        if "hf_" in low and ("token" in low or len(value) > 24):
            raise ConfigError(f"secret-like value is not allowed in config: {'.'.join(path)}")


def load_config(path: str | Path) -> ExperimentConfig | CaseConfig | ThresholdsConfig:
    config_path = Path(path)
    data = _load_mapping(config_path)
    _scan_secrets(data)
    kind = data.get("kind")
    try:
        if kind == "experiment":
            cfg = ExperimentConfig.model_validate(data)
            ensure_output_root(cfg.output_root)
            return cfg
        if kind == "case":
            cfg = CaseConfig.model_validate(data)
            for run in [*cfg.baseline_runs, *cfg.current_runs, *cfg.replay_runs]:
                ensure_output_root(run.output_root)
            validate_case_rq1_refs(cfg)
            validate_case_operator_linkage(cfg)
            return cfg
        if kind == "thresholds":
            return ThresholdsConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
    raise ConfigError(f"unknown config kind: {kind!r}")


def load_thresholds(path: str | Path | None) -> ThresholdsConfig:
    if path is None:
        return ThresholdsConfig(kind="thresholds")
    cfg = load_config(path)
    if not isinstance(cfg, ThresholdsConfig):
        raise ConfigError(f"expected thresholds config: {path}")
    return cfg


def load_rq1_evidence_ids(path: Path | None = None) -> set[str]:
    evidence_path = path or rq1_evidence_index_path()
    if not evidence_path.exists():
        raise ConfigError(f"RQ1 evidence index not found: {evidence_path}")
    with evidence_path.open(newline="") as f:
        return {row["candidate_id"] for row in csv.DictReader(f) if row.get("candidate_id")}


def validate_case_rq1_refs(cfg: CaseConfig, evidence_ids: set[str] | None = None) -> None:
    evidence_ids = evidence_ids or load_rq1_evidence_ids()
    refs = cfg.case.rq1_evidence_refs
    missing = sorted(set(refs) - evidence_ids)
    if missing:
        raise ConfigError(f"unknown RQ1 evidence refs for case {cfg.case.case_id}: {missing}")
    if not refs and cfg.case.rq1_support_level != RQ1SupportLevel.synthetic_stress:
        raise ConfigError(
            f"case {cfg.case.case_id} without RQ1 evidence refs must use rq1_support_level=synthetic_stress"
        )
    if cfg.case.coverage_status == CoverageStatus.core_planned and not refs:
        raise ConfigError(f"core planned case {cfg.case.case_id} requires at least one RQ1 evidence ref")


def validate_case_operator_linkage(cfg: CaseConfig) -> None:
    case = cfg.case
    injected_runs = [run for run in cfg.current_runs if run.injection.enabled]
    for split_name, runs in [
        ("baseline", cfg.baseline_runs),
        ("current", cfg.current_runs),
        ("replay", cfg.replay_runs),
    ]:
        for run in runs:
            if run.allow_failure and case.deviation_symptom != DeviationSymptom.evaluation_crash_or_failure:
                raise ConfigError(f"{split_name} run {run.run_id} sets allow_failure outside a crash/failure case")
            if (
                run.allow_failure
                and case.deviation_symptom == DeviationSymptom.evaluation_crash_or_failure
                and split_name != "current"
            ):
                raise ConfigError(f"{split_name} run {run.run_id} cannot allow failure in a crash/failure case")
    if case.injection_operator is None:
        if injected_runs:
            raise ConfigError(f"case {case.case_id} has injected current runs but no case.injection_operator")
        return

    try:
        spec = get_operator_spec(case.injection_operator)
    except ValueError as exc:
        raise ConfigError(f"unknown injection operator for case {case.case_id}: {case.injection_operator}") from exc

    if case.platform not in spec.required_platforms:
        platforms = ", ".join(platform.value for platform in spec.required_platforms)
        raise ConfigError(f"operator {spec.operator.value} is not valid for {case.platform.value}; expected one of {platforms}")
    if case.injected_factor is not None and case.injected_factor != spec.factor:
        raise ConfigError(
            f"case {case.case_id} injected_factor={case.injected_factor.value} does not match operator factor={spec.factor.value}"
        )
    is_unknown_case = case.expected_status == DiagnosisStatus.unknown_engineering_factor
    if not is_unknown_case and case.expected_factor is not None and case.expected_factor != spec.expected_factor:
        raise ConfigError(
            f"case {case.case_id} expected_factor={case.expected_factor.value} does not match operator expected_factor={spec.expected_factor.value}"
        )
    if not is_unknown_case and case.expected_status != spec.expected_status:
        raise ConfigError(
            f"case {case.case_id} expected_status={case.expected_status.value} does not match operator expected_status={spec.expected_status.value}"
        )
    if (
        not is_unknown_case
        and case.rq1_factor_category is not None
        and case.rq1_factor_category != spec.rq1_factor_category
    ):
        raise ConfigError(
            f"case {case.case_id} rq1_factor_category={case.rq1_factor_category.value} does not match operator category={spec.rq1_factor_category.value}"
        )

    if not injected_runs and not cfg.current_run_ids:
        raise ConfigError(f"case {case.case_id} with injection_operator requires at least one injected current run")
    for run in injected_runs:
        if run.platform != case.platform:
            raise ConfigError(f"injected run {run.run_id} platform does not match case {case.case_id}")
        if run.injection.operator != case.injection_operator:
            raise ConfigError(f"injected run {run.run_id} operator does not match case {case.case_id}")
        if run.injection.factor != spec.factor:
            raise ConfigError(f"injected run {run.run_id} factor does not match operator {spec.operator.value}")
        try:
            validate_operator_params_for_platform(run.injection.operator, run.injection.params, run.platform)
        except ValueError as exc:
            raise ConfigError(f"injected run {run.run_id} has invalid operator params: {exc}") from exc
        if run.injection.operator == InjectionOperator.eval_protocol_change_episode_length:
            expected = run.injection.params["episode_length"]
            if run.episode_length != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set episode_length={expected} for "
                    "eval_protocol.change_episode_length"
                )
        if run.injection.operator == InjectionOperator.evaluation_script_modify_harness_flag:
            flag = run.injection.params["flag"]
            value = run.injection.params["value"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("evaluation_script.modify_harness_flag is currently connected only for LeRobot/LIBERO")
            if flag != "eval.batch_size":
                raise ConfigError(f"injected run {run.run_id} uses unsupported harness flag {flag}")
            if run.eval_batch_size != value:
                raise ConfigError(
                    f"injected run {run.run_id} must set eval_batch_size={value} for "
                    "evaluation_script.modify_harness_flag"
                )
            if value == 1:
                raise ConfigError(f"injected run {run.run_id} must use a non-default eval_batch_size")
        if run.injection.operator == InjectionOperator.action_change_control_mode:
            expected = run.injection.params["control_mode"]
            if run.libero_control_mode != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_control_mode={expected} for "
                    "action.change_control_mode"
                )
            if expected == "relative":
                raise ConfigError(f"injected run {run.run_id} must use a non-default libero_control_mode")
        if run.injection.operator == InjectionOperator.action_drop_postprocessor:
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("action.drop_postprocessor is currently connected only for LeRobot/LIBERO")
        if run.injection.operator == InjectionOperator.action_reorder_dimensions:
            expected = run.injection.params["permutation"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("action.reorder_dimensions is currently connected only for LeRobot/LIBERO")
            if run.action_dimension_permutation != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set action_dimension_permutation={expected} for "
                    "action.reorder_dimensions"
                )
            if sorted(expected) != list(range(7)):
                raise ConfigError(f"injected run {run.run_id} must use a permutation of action dimensions 0..6")
        if run.injection.operator == InjectionOperator.observation_swap_camera_keys:
            expected = run.injection.params["camera_name_mapping"]
            if run.libero_camera_name_mapping != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_camera_name_mapping={expected} for "
                    "observation.swap_camera_keys"
                )
            if expected == {"agentview_image": "image", "robot0_eye_in_hand_image": "image2"}:
                raise ConfigError(f"injected run {run.run_id} must use a non-default camera mapping")
        if run.injection.operator == InjectionOperator.observation_drop_image_key:
            expected = run.injection.params["camera_name"]
            if run.libero_camera_name != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_camera_name={expected} for "
                    "observation.drop_image_key"
                )
            if expected == "agentview_image,robot0_eye_in_hand_image":
                raise ConfigError(f"injected run {run.run_id} must use a single-camera camera_name")
        if run.injection.operator == InjectionOperator.observation_image_flip:
            expected = run.injection.params["axis"]
            if run.libero_image_flip_axis != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_image_flip_axis={expected} for "
                    "observation.image_flip"
                )
        if run.injection.operator == InjectionOperator.observation_image_blackout:
            expected = run.injection.params["value"]
            if run.libero_image_blackout_value != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_image_blackout_value={expected} for "
                    "observation.image_blackout"
                )
        if run.injection.operator == InjectionOperator.observation_state_blackout:
            expected_keys = run.injection.params["keys"]
            expected_value = run.injection.params["value"]
            if run.libero_state_keys != expected_keys:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_state_keys={expected_keys} for "
                    "observation.state_blackout"
                )
            if run.libero_state_blackout_value != expected_value:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_state_blackout_value={expected_value} for "
                    "observation.state_blackout"
                )
        if run.injection.operator == InjectionOperator.observation_state_noise:
            expected_keys = run.injection.params["keys"]
            expected_std = run.injection.params["std"]
            if run.libero_state_keys != expected_keys:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_state_keys={expected_keys} for "
                    "observation.state_noise"
                )
            if run.libero_state_noise_std != expected_std:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_state_noise_std={expected_std} for "
                    "observation.state_noise"
                )
            if expected_std <= 0:
                raise ConfigError(f"injected run {run.run_id} must use positive state noise std")
        if run.injection.operator == InjectionOperator.observation_state_key_drop:
            expected_keys = run.injection.params["keys"]
            if run.libero_state_keys != expected_keys:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_state_keys={expected_keys} for "
                    "observation.state_key_drop"
                )
        if run.injection.operator == InjectionOperator.checkpoint_config_feature_mismatch:
            expected = run.injection.params["overlay_mode"]
            if run.checkpoint_overlay_mode != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set checkpoint_overlay_mode={expected} for "
                    "checkpoint.config_feature_mismatch"
                )
            if expected != "postprocessor_action_norm_identity":
                raise ConfigError(f"injected run {run.run_id} uses unsupported checkpoint overlay mode")
        if run.injection.operator == InjectionOperator.checkpoint_remove_processor_stats:
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("checkpoint.remove_processor_stats is currently connected only for LeRobot/LIBERO")
            if run.checkpoint_overlay_mode != "remove_processor_stats":
                raise ConfigError(
                    f"injected run {run.run_id} must set checkpoint_overlay_mode=remove_processor_stats for "
                    "checkpoint.remove_processor_stats"
                )
        if run.injection.operator == InjectionOperator.reset_disable_fixed_init_state:
            if run.platform == Platform.lerobot_libero:
                expected = run.injection.params["init_states"]
                if run.libero_init_states != expected:
                    raise ConfigError(
                        f"injected run {run.run_id} must set libero_init_states={expected} for "
                        "reset.disable_fixed_init_state"
                    )
                if expected is not False:
                    raise ConfigError(f"injected run {run.run_id} must disable LIBERO init states")
        if run.injection.operator == InjectionOperator.runtime_switch_mujoco_env:
            expected = run.injection.params["conda_env"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("runtime.switch_mujoco_env is currently connected only for LeRobot/LIBERO")
            if run.libero_env != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_env={expected} for "
                    "runtime.switch_mujoco_env"
                )
            if run.mujoco_env != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set mujoco_env={expected} for "
                    "runtime.switch_mujoco_env"
                )
            if expected == "evaltriage-lr":
                raise ConfigError(f"injected run {run.run_id} must use a non-default LeRobot/LIBERO env")
        if run.injection.operator == InjectionOperator.runtime_switch_incompatible_env:
            expected = run.injection.params["conda_env"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("runtime.switch_incompatible_env is currently connected only for LeRobot/LIBERO")
            if run.libero_env != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set libero_env={expected} for "
                    "runtime.switch_incompatible_env"
                )
            if expected == "evaltriage-lr":
                raise ConfigError(f"injected run {run.run_id} must use a non-default LeRobot/LIBERO env")
        if run.injection.operator == InjectionOperator.dataset_remove_feature_column:
            expected = run.injection.params["feature_key"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("dataset.remove_feature_column is currently connected only for LeRobot/LIBERO")
            if run.dataset_path is None:
                raise ConfigError(f"injected run {run.run_id} must set dataset_path for dataset.remove_feature_column")
            if run.dataset_feature_key != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set dataset_feature_key={expected} for "
                    "dataset.remove_feature_column"
                )
        if run.injection.operator == InjectionOperator.code_semantic_bug_flag:
            expected = run.injection.params["flag"]
            if run.platform != Platform.lerobot_libero:
                raise ConfigError("code.semantic_bug_flag is currently connected only for LeRobot/LIBERO")
            if run.semantic_bug_flag != expected:
                raise ConfigError(
                    f"injected run {run.run_id} must set semantic_bug_flag={expected} for "
                    "code.semantic_bug_flag"
                )
            if expected not in {
                "zero_action_output",
                "freeze_first_action",
                "translation_sign_flip",
                "gripper_sign_flip",
            }:
                raise ConfigError(f"injected run {run.run_id} uses unsupported semantic bug flag")
            if not run.injection.params.get("semantic_change_ref"):
                raise ConfigError(f"injected run {run.run_id} must include semantic_change_ref evidence")
        if case.deviation_symptom == DeviationSymptom.evaluation_crash_or_failure and not run.allow_failure:
            raise ConfigError(f"injected crash/failure run {run.run_id} must set allow_failure=true")
