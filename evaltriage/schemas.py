"""Strict schemas for EvalTriage configs and outputs."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Platform(str, Enum):
    lerobot_libero = "lerobot_libero"
    maniskill = "maniskill"


class RunRole(str, Enum):
    baseline = "baseline"
    current = "current"
    replay = "replay"
    smoke = "smoke"


class ExecutionStatus(str, Enum):
    completed = "completed"
    failed = "failed"


class CaseFamily(str, Enum):
    setup_sensitive_factor = "setup_sensitive_factor"
    flaky = "flaky"
    true_regression = "true_regression"
    unknown = "unknown"


class DiagnosisStatus(str, Enum):
    likely_setup_sensitive_deviation = "likely_setup_sensitive_deviation"
    likely_flaky_evaluation = "likely_flaky_evaluation"
    likely_true_regression = "likely_true_regression"
    unknown_engineering_factor = "unknown_engineering_factor"


class ArtifactSplit(str, Enum):
    smoke = "smoke"
    validation = "validation"
    full = "full"


class RQ1SupportLevel(str, Enum):
    evidence_backed = "evidence_backed"
    synthetic_stress = "synthetic_stress"
    extension = "extension"


class CoverageStatus(str, Enum):
    core_planned = "core_planned"
    planned_extension = "planned_extension"
    supporting_context = "supporting_context"


class AttributionFactor(str, Enum):
    seed_or_randomness = "seed_or_randomness"
    reset_or_initial_state = "reset_or_initial_state"
    object_scene_task_initialization = "object_scene_task_initialization"
    simulator_physics_rendering = "simulator_physics_rendering"
    dependency_runtime_environment = "dependency_runtime_environment"
    action_controller_interface = "action_controller_interface"
    observation_sensor_preprocessing = "observation_sensor_preprocessing"
    checkpoint_config_compatibility = "checkpoint_config_compatibility"
    evaluation_protocol_metric = "evaluation_protocol_metric"
    evaluation_script_harness = "evaluation_script_harness"
    data_dataset_format = "data_dataset_format"
    semantic_code_regression = "semantic_code_regression"


class RQ1FactorCategory(str, Enum):
    seed_or_randomness = "seed_or_randomness"
    reset_or_initial_state = "reset_or_initial_state"
    object_scene_task_initialization = "object_scene_task_initialization"
    simulator_physics_rendering = "simulator_physics_rendering"
    dependency_runtime_environment = "dependency_runtime_environment"
    action_controller_interface = "action_controller_interface"
    observation_sensor_preprocessing = "observation_sensor_preprocessing"
    checkpoint_config_compatibility = "checkpoint_config_compatibility"
    evaluation_protocol_metric = "evaluation_protocol_metric"
    evaluation_script_harness = "evaluation_script_harness"
    data_dataset_format = "data_dataset_format"
    training_evaluation_interaction = "training_evaluation_interaction"
    ci_regression_evaluation = "ci_regression_evaluation"
    unknown_or_not_specified = "unknown_or_not_specified"


class DeviationSymptom(str, Enum):
    reproduction_failure = "reproduction_failure"
    success_rate_drop_or_mismatch = "success_rate_drop_or_mismatch"
    reward_score_metric_mismatch = "reward_score_metric_mismatch"
    rollout_behavior_anomaly = "rollout_behavior_anomaly"
    evaluation_crash_or_failure = "evaluation_crash_or_failure"
    evaluation_instability_or_flakiness = "evaluation_instability_or_flakiness"
    setup_sensitive_result = "setup_sensitive_result"
    unknown_or_not_applicable = "unknown_or_not_applicable"


class InjectionOperator(str, Enum):
    eval_protocol_change_episode_length = "eval_protocol.change_episode_length"
    eval_protocol_change_success_aggregation = "eval_protocol.change_success_aggregation"
    evaluation_script_modify_harness_flag = "evaluation_script.modify_harness_flag"
    action_change_control_mode = "action.change_control_mode"
    action_scale_multiplier = "action.scale_multiplier"
    action_drop_postprocessor = "action.drop_postprocessor"
    action_reorder_dimensions = "action.reorder_dimensions"
    observation_swap_camera_keys = "observation.swap_camera_keys"
    observation_image_flip = "observation.image_flip"
    observation_image_blackout = "observation.image_blackout"
    observation_state_blackout = "observation.state_blackout"
    observation_state_noise = "observation.state_noise"
    observation_state_key_drop = "observation.state_key_drop"
    observation_drop_image_key = "observation.drop_image_key"
    checkpoint_remove_processor_stats = "checkpoint.remove_processor_stats"
    checkpoint_config_feature_mismatch = "checkpoint.config_feature_mismatch"
    reset_disable_fixed_init_state = "reset.disable_fixed_init_state"
    maniskill_change_object_pose = "maniskill.change_object_pose"
    runtime_switch_mujoco_env = "runtime.switch_mujoco_env"
    runtime_switch_incompatible_env = "runtime.switch_incompatible_env"
    dataset_remove_feature_column = "dataset.remove_feature_column"
    dataset_corrupt_video_or_parquet_reference = "dataset.corrupt_video_or_parquet_reference"
    code_semantic_bug_flag = "code.semantic_bug_flag"
    manifest_hide_factor_fields = "manifest.hide_factor_fields"


class ReplayType(str, Enum):
    restore_seed_or_init = "restore_seed_or_init"
    restore_action_interface = "restore_action_interface"
    restore_observation_pipeline = "restore_observation_pipeline"
    restore_checkpoint_config = "restore_checkpoint_config"
    restore_eval_protocol = "restore_eval_protocol"
    restore_runtime_env = "restore_runtime_env"
    restore_dataset_format = "restore_dataset_format"
    rerun_same_manifest = "rerun_same_manifest"
    affected_task_subset_replay = "affected_task_subset_replay"


class PolicyManifest(StrictModel):
    path: str | None = None
    repo_id: str | None = None
    checkpoint_checksum: str | None = None
    config_checksum: str | None = None
    preprocessor_checksum: str | None = None
    postprocessor_checksum: str | None = None


class CodeManifest(StrictModel):
    evaltriage_commit: str | None = None
    lerobot_commit: str | None = None
    dirty: bool = False
    semantic_change_refs: list[str] = Field(default_factory=list)


class RuntimeEnvManifest(StrictModel):
    conda_env: str | None = None
    python: str | None = None
    torch: str | None = None
    cuda: str | None = None
    gpu: str | None = None
    driver: str | None = None
    mujoco: str | None = None
    robosuite: str | None = None
    mani_skill: str | None = None
    os: str | None = None


class EvaluationManifest(StrictModel):
    command: str
    episode_length: int | None = None
    batch_size: int = Field(default=1, ge=1)
    use_async_envs: bool = False
    compile_model: bool = False
    metric_definition: str = "success_rate_percent"


class ObservationManifest(StrictModel):
    obs_type: str | None = None
    camera_names: list[str] = Field(default_factory=list)
    image_keys: list[str] = Field(default_factory=list)
    height: int | None = Field(default=None, ge=1)
    width: int | None = Field(default=None, ge=1)
    preprocessing: list[str] = Field(default_factory=list)


class ActionManifest(StrictModel):
    action_dim: int | None = Field(default=None, ge=1)
    control_mode: str | None = None
    normalization: str | None = None
    postprocessing: list[str] = Field(default_factory=list)


class ResetManifest(StrictModel):
    init_states: bool | None = None
    seed_offset: int | None = None


class InjectionManifest(StrictModel):
    enabled: bool = False
    factor: AttributionFactor | None = None
    operator: InjectionOperator | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enabled_requires_operator(self) -> "InjectionManifest":
        if self.enabled and (self.factor is None or self.operator is None):
            raise ValueError("enabled injection requires both factor and operator")
        if not self.enabled and (self.factor is not None or self.operator is not None or self.params):
            raise ValueError("disabled injection cannot carry factor, operator, or params")
        return self


class RunMetrics(StrictModel):
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_reward: float | None = None
    num_episodes: int = Field(default=0, ge=0)
    num_success: int = Field(default=0, ge=0)
    num_failure: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _counts_match(self) -> "RunMetrics":
        if self.num_episodes and self.num_success + self.num_failure > self.num_episodes:
            raise ValueError("num_success + num_failure cannot exceed num_episodes")
        return self


class CostRecord(StrictModel):
    wall_clock_s: float | None = Field(default=None, ge=0.0)
    gpu_minutes: float | None = Field(default=None, ge=0.0)
    max_gpu_mem_mb: float | None = Field(default=None, ge=0.0)


class Manifest(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    case_id: str | None = None
    role: RunRole
    platform: Platform
    benchmark: str
    task_suite: str
    task_ids: list[int]
    seed: int
    n_episodes: int = Field(ge=1)
    policy: PolicyManifest = Field(default_factory=PolicyManifest)
    code: CodeManifest = Field(default_factory=CodeManifest)
    runtime_env: RuntimeEnvManifest = Field(default_factory=RuntimeEnvManifest)
    evaluation: EvaluationManifest
    observation: ObservationManifest = Field(default_factory=ObservationManifest)
    action: ActionManifest = Field(default_factory=ActionManifest)
    reset: ResetManifest = Field(default_factory=ResetManifest)
    injection: InjectionManifest = Field(default_factory=InjectionManifest)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    cost: CostRecord = Field(default_factory=CostRecord)


class EpisodeRecord(StrictModel):
    episode_id: int = Field(ge=0)
    task_suite: str
    task_id: int
    seed: int | None = None
    success: bool
    reward: float | None = None
    num_steps: int | None = Field(default=None, ge=0)
    termination_reason: str | None = None
    error: str | None = None
    behavior_tags: list[str] = Field(default_factory=list)
    video_path: str | None = None


class FailureRecord(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    case_id: str | None = None
    role: RunRole
    platform: Platform
    factor: AttributionFactor | None = None
    operator: InjectionOperator | None = None
    failure_kind: str
    stage: str
    exit_code: int | None = None
    signal: int | None = None
    exception_type: str | None = None
    message: str
    log_excerpt: str | None = None
    command: str | None = None
    logs_path: str | None = None
    raw_output_path: str | None = None
    cost: CostRecord = Field(default_factory=CostRecord)


class RunSummary(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    case_id: str | None = None
    role: RunRole
    platform: Platform
    benchmark: str
    task_suite: str
    task_ids: list[int]
    seed: int
    execution_status: ExecutionStatus = ExecutionStatus.completed
    metrics: RunMetrics
    cost: CostRecord
    manifest_path: str
    episodes_path: str
    logs_path: str
    raw_output_path: str | None = None
    failure_path: str | None = None

    @model_validator(mode="after")
    def _metrics_count_matches_request_shape(self) -> "RunSummary":
        if self.execution_status == ExecutionStatus.completed and self.metrics.num_episodes == 0:
            raise ValueError("run summary requires at least one episode")
        if self.execution_status == ExecutionStatus.failed:
            if self.failure_path is None:
                raise ValueError("failed run summary requires failure_path")
            if (
                self.metrics.num_episodes != 0
                or self.metrics.num_success != 0
                or self.metrics.num_failure != 0
                or self.metrics.success_rate is not None
                or self.metrics.mean_reward is not None
            ):
                raise ValueError("failed run summary cannot carry completed-rollout metrics")
        return self


class CaseRecord(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    platform: Platform
    case_family: CaseFamily
    deviation_symptom: DeviationSymptom
    expected_status: DiagnosisStatus
    expected_factor: AttributionFactor | None = None
    injected_factor: AttributionFactor | None = None
    injection_operator: InjectionOperator | None = None
    baseline_run_ids: list[str] = Field(default_factory=list)
    current_run_ids: list[str] = Field(default_factory=list)
    replay_run_ids: list[str] = Field(default_factory=list)
    rq1_factor_category: RQ1FactorCategory | None = None
    rq1_evidence_refs: list[str] = Field(default_factory=list)
    rq1_support_level: RQ1SupportLevel
    coverage_status: CoverageStatus | None = None
    artifact_split: ArtifactSplit
    selected_by_validation: bool = False
    unknown_reason: str | None = None

    @model_validator(mode="after")
    def _validate_ground_truth(self) -> "CaseRecord":
        if self.case_family == CaseFamily.unknown:
            if self.expected_status != DiagnosisStatus.unknown_engineering_factor:
                raise ValueError("unknown cases must expect unknown_engineering_factor")
            if self.expected_factor is not None:
                raise ValueError("unknown cases must not define a normal expected_factor")
            if not self.unknown_reason:
                raise ValueError("unknown cases must include unknown_reason")
        else:
            if self.expected_factor is None:
                raise ValueError("non-unknown cases require expected_factor")
            if self.expected_status == DiagnosisStatus.unknown_engineering_factor:
                raise ValueError("non-unknown cases cannot expect unknown_engineering_factor")
        if self.expected_factor == AttributionFactor.semantic_code_regression:
            if self.case_family != CaseFamily.true_regression:
                raise ValueError("semantic_code_regression requires true_regression case_family")
            if self.expected_status != DiagnosisStatus.likely_true_regression:
                raise ValueError("semantic_code_regression requires likely_true_regression status")
        if self.rq1_support_level == RQ1SupportLevel.evidence_backed and not self.rq1_evidence_refs:
            raise ValueError("evidence_backed cases require rq1_evidence_refs")
        if self.coverage_status == CoverageStatus.core_planned and not self.rq1_evidence_refs:
            raise ValueError("core_planned cases require rq1_evidence_refs")
        if self.rq1_factor_category == RQ1FactorCategory.unknown_or_not_specified:
            if self.case_family != CaseFamily.unknown:
                raise ValueError("unknown_or_not_specified RQ1 category is only valid for unknown cases")
        return self


class DeviationRecord(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    baseline_run_ids: list[str]
    current_run_ids: list[str]
    symptom: DeviationSymptom
    metric_name: str
    baseline_value: float | None = None
    current_value: float | None = None
    delta: float | None = None
    threshold: float | None = None
    detected: bool
    evidence: list[str] = Field(default_factory=list)


class ManifestDiffEntry(StrictModel):
    path: str
    baseline_value: Any = None
    current_value: Any = None
    factor: AttributionFactor | RQ1FactorCategory | None = None


class ManifestDiff(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    baseline_run_id: str
    current_run_id: str
    entries: list[ManifestDiffEntry] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ReplayStep(StrictModel):
    replay_id: str
    replay_type: ReplayType
    target_factor: AttributionFactor | None = None
    reason: str
    run_id: str | None = None
    estimated_episodes: int | None = Field(default=None, ge=0)
    estimated_gpu_minutes: float | None = Field(default=None, ge=0.0)
    params: dict[str, Any] = Field(default_factory=dict)


class ReplayPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    budget: str
    steps: list[ReplayStep] = Field(default_factory=list)
    skipped_reason: str | None = None


class FactorAttribution(StrictModel):
    factor: AttributionFactor
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    decision_rule: str | None = None


class Diagnosis(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    status: DiagnosisStatus
    status_confidence: float = Field(ge=0.0, le=1.0)
    top_factors: list[FactorAttribution] = Field(default_factory=list)
    decision_rules_fired: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    unknown_reason: str | None = None

    @model_validator(mode="after")
    def _unknown_has_reason(self) -> "Diagnosis":
        if self.status == DiagnosisStatus.unknown_engineering_factor and not self.unknown_reason:
            raise ValueError("unknown diagnosis requires unknown_reason")
        return self


class BaselineMethodResult(StrictModel):
    method: str
    status: DiagnosisStatus | None = None
    top_factors: list[AttributionFactor] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    not_applicable_reason: str | None = None
    cost: CostRecord = Field(default_factory=CostRecord)


class BaselinesReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str
    results: list[BaselineMethodResult]


class RunRequest(StrictModel):
    platform: Platform
    run_id: str
    role: RunRole
    suite: str
    task_ids: list[int]
    seed: int
    episodes: int = Field(ge=1)
    output_root: Path
    case_id: str | None = None
    policy_path: Path | None = None
    libero_env: str = "evaltriage-lr"
    mujoco_env: str = "evaltriage-lr-mujoco37"
    obs_type: str = "pixels_agent_pos"
    camera_size: int = Field(default=360, ge=1)
    episode_length: int | None = Field(default=None, ge=1)
    libero_control_mode: str = "relative"
    libero_camera_name: str = "agentview_image,robot0_eye_in_hand_image"
    libero_camera_name_mapping: dict[str, str] | None = None
    libero_init_states: bool = True
    libero_image_flip_axis: str | None = None
    libero_image_blackout_value: float | None = None
    libero_state_keys: list[str] = Field(default_factory=lambda: ["observation.state"])
    libero_state_blackout_value: float | None = None
    libero_state_noise_std: float | None = None
    checkpoint_overlay_mode: str | None = None
    semantic_bug_flag: str | None = None
    action_dimension_permutation: list[int] = Field(default_factory=list)
    compile_model: bool = False
    eval_batch_size: int = Field(default=1, ge=1)
    use_async_envs: bool = False
    maniskill_env: str = "evaltriage-ms"
    control_policy: str | None = None
    obs_mode: str | None = None
    allow_failure: bool = False
    dataset_path: Path | None = None
    dataset_feature_key: str | None = None
    injection: InjectionManifest = Field(default_factory=InjectionManifest)

    @model_validator(mode="after")
    def _platform_requirements(self) -> "RunRequest":
        if self.platform == Platform.lerobot_libero and self.policy_path is None and self.dataset_path is None:
            raise ValueError("policy_path is required for lerobot_libero")
        if self.platform == Platform.maniskill and (not self.control_policy or not self.obs_mode):
            raise ValueError("control_policy and obs_mode are required for maniskill")
        return self


class ExperimentConfig(StrictModel):
    schema_version: str = SCHEMA_VERSION
    kind: Literal["experiment"]
    experiment_id: str
    split: ArtifactSplit
    output_root: Path
    runs: list[RunRequest] = Field(default_factory=list)


class CaseConfig(StrictModel):
    schema_version: str = SCHEMA_VERSION
    kind: Literal["case"]
    case: CaseRecord
    baseline_runs: list[RunRequest] = Field(default_factory=list)
    current_runs: list[RunRequest] = Field(default_factory=list)
    replay_runs: list[RunRequest] = Field(default_factory=list)
    baseline_run_ids: list[str] = Field(default_factory=list)
    current_run_ids: list[str] = Field(default_factory=list)
    replay_run_ids: list[str] = Field(default_factory=list)
    thresholds_path: Path | None = None

    @model_validator(mode="after")
    def _requires_baseline_and_current(self) -> "CaseConfig":
        split_pairs = [
            ("baseline", self.baseline_runs, self.baseline_run_ids),
            ("current", self.current_runs, self.current_run_ids),
            ("replay", self.replay_runs, self.replay_run_ids),
        ]
        for name, run_requests, run_ids in split_pairs:
            if run_requests and run_ids:
                raise ValueError(f"case config cannot mix {name}_runs and {name}_run_ids")
        if not self.baseline_runs and not self.baseline_run_ids:
            raise ValueError("case config requires baseline_runs or baseline_run_ids")
        if not self.current_runs and not self.current_run_ids:
            raise ValueError("case config requires current_runs or current_run_ids")
        return self

    @model_validator(mode="after")
    def _run_requests_match_case_splits(self) -> "CaseConfig":
        split_specs = [
            ("baseline", self.baseline_runs, RunRole.baseline),
            ("current", self.current_runs, RunRole.current),
            ("replay", self.replay_runs, RunRole.replay),
        ]
        seen_run_ids: dict[str, str] = {}
        for split, run_requests, expected_role in split_specs:
            for run in run_requests:
                if run.role != expected_role:
                    raise ValueError(f"{split}_runs require role={expected_role.value}; got {run.role.value}")
                if run.platform != self.case.platform:
                    raise ValueError(f"{split} run {run.run_id} platform does not match case platform")
                if run.case_id is not None and run.case_id != self.case.case_id:
                    raise ValueError(f"{split} run {run.run_id} case_id does not match case.case_id")
                previous = seen_run_ids.get(run.run_id)
                if previous is not None:
                    raise ValueError(f"run_id {run.run_id} appears in both {previous}_runs and {split}_runs")
                seen_run_ids[run.run_id] = split
        return self


class ThresholdsConfig(StrictModel):
    schema_version: str = SCHEMA_VERSION
    kind: Literal["thresholds"]
    success_rate_drop_abs: float = Field(default=0.1, ge=0.0, le=1.0)
    reward_drop_abs: float | None = Field(default=None, ge=0.0)
    flaky_success_rate_std: float = Field(default=0.2, ge=0.0, le=1.0)
    replay_recovery_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
    high_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    medium_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _confidence_order(self) -> "ThresholdsConfig":
        if self.high_confidence < self.medium_confidence:
            raise ValueError("high_confidence must be >= medium_confidence")
        return self


class MetricsCaseRow(StrictModel):
    case_id: str
    config_path: str
    run_path: str
    split: ArtifactSplit
    selected_by_validation: bool
    platform: Platform
    case_family: CaseFamily
    deviation_symptom: DeviationSymptom | None = None
    deviation_detected: bool | None = None
    matrix_bucket: str | None = None
    expected_status: DiagnosisStatus
    evaltriage_status: DiagnosisStatus | None = None
    expected_factor: AttributionFactor | None = None
    evaltriage_top1_factor: AttributionFactor | None = None
    evaltriage_top3_factors: list[AttributionFactor] = Field(default_factory=list)
    factor_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank: float | None = Field(default=None, ge=0.0, le=1.0)
    unknown_abstention_correct: bool | None = None
    over_attribution_error: bool | None = None
    status_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rerun_count: int = Field(default=0, ge=0)
    episode_count: int = Field(default=0, ge=0)
    failed_run_count: int = Field(default=0, ge=0)
    gpu_minutes: float | None = Field(default=None, ge=0.0)
    wall_clock_minutes: float | None = Field(default=None, ge=0.0)
    diagnosis_latency_s: float | None = Field(default=None, ge=0.0)
    pipeline_overhead_s: float | None = Field(default=None, ge=0.0)
    affected_task_replay_cost_ratio: float | None = Field(default=None, ge=0.0)
