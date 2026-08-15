from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from evaltriage.case_runner import validate_case_existing_runs
from evaltriage.config import ConfigError, load_config
from evaltriage.detection.deviation import detect_deviation, detect_repeated_run_instability
from evaltriage.diagnosis.attribution import diagnose_case
from evaltriage.manifest.diff import diff_manifests
from evaltriage.metrics.ablation import _selected_case_dirs, _summarize_rows
from evaltriage.paths import DEFAULT_OUTPUT_ROOT, PathSafetyError, ensure_output_root, run_paths
from evaltriage.runtime import base_env
from evaltriage.runners.executor import execute_run
from evaltriage.runners.executor import _finalize_episode_paths
from evaltriage.schemas import (
    ArtifactSplit,
    AttributionFactor,
    CaseFamily,
    CaseConfig,
    CaseRecord,
    CostRecord,
    DeviationRecord,
    DeviationSymptom,
    DiagnosisStatus,
    EpisodeRecord,
    ExecutionStatus,
    FailureRecord,
    InjectionManifest,
    InjectionOperator,
    ManifestDiff,
    Platform,
    RQ1FactorCategory,
    RQ1SupportLevel,
    RunMetrics,
    RunRequest,
    RunRole,
    RunSummary,
    ThresholdsConfig,
)


def test_unknown_schema_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CaseRecord.model_validate(
            {
                "case_id": "bad_extra",
                "platform": "maniskill",
                "case_family": "unknown",
                "deviation_symptom": "unknown_or_not_applicable",
                "expected_status": "unknown_engineering_factor",
                "rq1_factor_category": "unknown_or_not_specified",
                "rq1_support_level": "synthetic_stress",
                "artifact_split": "smoke",
                "unknown_reason": "missing manifest fields",
                "typo_field": True,
            }
        )


def test_unknown_case_cannot_have_normal_factor() -> None:
    with pytest.raises(ValidationError):
        CaseRecord(
            case_id="bad_unknown",
            platform=Platform.maniskill,
            case_family=CaseFamily.unknown,
            deviation_symptom=DeviationSymptom.unknown_or_not_applicable,
            expected_status=DiagnosisStatus.unknown_engineering_factor,
            expected_factor=AttributionFactor.action_controller_interface,
            rq1_factor_category=RQ1FactorCategory.unknown_or_not_specified,
            rq1_support_level=RQ1SupportLevel.synthetic_stress,
            artifact_split=ArtifactSplit.smoke,
            unknown_reason="insufficient evidence",
        )


def test_output_root_must_stay_under_formal_root() -> None:
    with pytest.raises(PathSafetyError):
        ensure_output_root(Path("/tmp/evaltriage"))


def test_base_env_allows_explicit_cuda_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALTRIAGE_CUDA_VISIBLE_DEVICES", "1")
    assert base_env("0")["CUDA_VISIBLE_DEVICES"] == "1"


def test_config_rejects_secret_like_fields(tmp_path: Path) -> None:
    cfg = {
        "schema_version": "1.0",
        "kind": "thresholds",
        "success_rate_drop_abs": 0.1,
        "hf_token": "hf_should_not_be_written",
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError):
        load_config(path)


def test_unconnected_injection_without_real_overlay_fails_before_formal_outputs() -> None:
    run_id = "pytest_unconnected_injection_refuses_fake_outputs"
    paths = run_paths(run_id, DEFAULT_OUTPUT_ROOT)
    if paths.run_dir.exists():
        pytest.skip(f"formal run dir already exists: {paths.run_dir}")
    request = RunRequest(
        platform=Platform.maniskill,
        run_id=run_id,
        role=RunRole.current,
        suite="PickCube-v1",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        control_policy="random",
        obs_mode="state",
            injection=InjectionManifest(
                enabled=True,
                factor=AttributionFactor.observation_sensor_preprocessing,
                operator=InjectionOperator.observation_image_flip,
                params={"axis": "both"},
            ),
        )
    with pytest.raises(RuntimeError, match="not yet connected to a real maniskill runner overlay"):
        execute_run(request)
    assert not paths.run_dir.exists()


def _summary(run_id: str, success_rate: float, mean_reward: float) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        role=RunRole.baseline,
        platform=Platform.maniskill,
        benchmark="maniskill",
        task_suite="PickCube-v1",
        task_ids=[0],
        seed=1000,
        metrics=RunMetrics(
            success_rate=success_rate,
            mean_reward=mean_reward,
            num_episodes=1,
            num_success=1 if success_rate else 0,
            num_failure=0 if success_rate else 1,
        ),
        cost=CostRecord(wall_clock_s=1.0, gpu_minutes=0.01),
        manifest_path="manifest.json",
        episodes_path="episodes.jsonl",
        logs_path="logs.txt",
    )


def _failed_summary(run_id: str) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        role=RunRole.current,
        platform=Platform.lerobot_libero,
        benchmark="libero",
        task_suite="libero_goal",
        task_ids=[4],
        seed=1000,
        execution_status=ExecutionStatus.failed,
        metrics=RunMetrics(),
        cost=CostRecord(wall_clock_s=1.0, gpu_minutes=0.01),
        manifest_path="manifest.json",
        episodes_path="episodes.jsonl",
        logs_path="logs.txt",
        failure_path="failure.json",
    )


def test_failed_run_summary_allows_zero_episodes_with_failure_path() -> None:
    summary = _failed_summary("failed")
    assert summary.execution_status == ExecutionStatus.failed
    assert summary.metrics.num_episodes == 0


def test_failed_run_summary_rejects_rollout_metrics() -> None:
    with pytest.raises(ValidationError, match="failed run summary cannot carry completed-rollout metrics"):
        RunSummary(
            run_id="bad_failed",
            role=RunRole.current,
            platform=Platform.lerobot_libero,
            benchmark="libero",
            task_suite="libero_goal",
            task_ids=[4],
            seed=1000,
            execution_status=ExecutionStatus.failed,
            metrics=RunMetrics(success_rate=0.0, num_episodes=1, num_success=0, num_failure=1),
            cost=CostRecord(),
            manifest_path="manifest.json",
            episodes_path="episodes.jsonl",
            logs_path="logs.txt",
            failure_path="failure.json",
        )


def _case() -> CaseRecord:
    return CaseRecord(
        case_id="unit_case",
        platform=Platform.maniskill,
        case_family=CaseFamily.setup_sensitive_factor,
        deviation_symptom=DeviationSymptom.rollout_behavior_anomaly,
        expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
        expected_factor=AttributionFactor.action_controller_interface,
        injected_factor=AttributionFactor.action_controller_interface,
        injection_operator=InjectionOperator.action_scale_multiplier,
        rq1_factor_category=RQ1FactorCategory.action_controller_interface,
        rq1_evidence_refs=["github_issue::huggingface/lerobot::3401"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.smoke,
    )


def test_case_config_accepts_existing_run_id_mode() -> None:
    cfg = CaseConfig(
        kind="case",
        case=_case(),
        baseline_run_ids=["baseline_existing"],
        current_run_ids=["current_existing"],
        replay_run_ids=["replay_existing"],
    )
    assert cfg.baseline_run_ids == ["baseline_existing"]


def test_existing_run_validation_rejects_missing_outputs(tmp_path: Path) -> None:
    cfg = CaseConfig(kind="case", case=_case(), baseline_run_ids=["missing"], current_run_ids=["missing_current"])
    with pytest.raises(RuntimeError, match="missing required outputs"):
        validate_case_existing_runs(cfg, tmp_path, enforce_root=False)


def test_no_deviation_forces_unknown_diagnosis() -> None:
    baseline = _summary("baseline", 1.0, 10.0)
    current = _summary("current", 1.0, 10.0)
    deviation = DeviationRecord(
        case_id="unit_case",
        baseline_run_ids=["baseline"],
        current_run_ids=["current"],
        symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        metric_name="success_rate",
        baseline_value=1.0,
        current_value=1.0,
        delta=0.0,
        threshold=0.1,
        detected=False,
    )
    diagnosis = diagnose_case(
        _case(),
        deviation,
        ManifestDiff(case_id="unit_case", baseline_run_id="baseline", current_run_id="current"),
        baseline,
        current,
        [],
        ThresholdsConfig(kind="thresholds"),
    )
    assert diagnosis.status == DiagnosisStatus.unknown_engineering_factor
    assert diagnosis.decision_rules_fired == ["no_deviation_detected"]


def test_reward_threshold_detects_mean_reward_deviation() -> None:
    baseline = _summary("baseline", 1.0, 10.0)
    current = _summary("current", 1.0, 7.5)
    thresholds = ThresholdsConfig(kind="thresholds", reward_drop_abs=2.0)
    deviation = detect_deviation("unit_case", baseline, current, thresholds)
    assert deviation.detected is True
    assert deviation.metric_name == "mean_reward"


def test_failure_deviation_and_replay_recovery_diagnose_injected_factor() -> None:
    from evaltriage.detection.deviation import detect_failure_deviation

    baseline = RunSummary(
        run_id="baseline",
        role=RunRole.baseline,
        platform=Platform.lerobot_libero,
        benchmark="libero",
        task_suite="libero_goal",
        task_ids=[4],
        seed=1000,
        metrics=RunMetrics(success_rate=1.0, num_episodes=1, num_success=1, num_failure=0),
        cost=CostRecord(),
        manifest_path="manifest.json",
        episodes_path="episodes.jsonl",
        logs_path="logs.txt",
    )
    current = _failed_summary("current")
    replay = baseline.model_copy(update={"run_id": "replay", "role": RunRole.replay})
    case = CaseRecord(
        case_id="failure_case",
        platform=Platform.lerobot_libero,
        case_family=CaseFamily.setup_sensitive_factor,
        deviation_symptom=DeviationSymptom.evaluation_crash_or_failure,
        expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
        expected_factor=AttributionFactor.observation_sensor_preprocessing,
        injected_factor=AttributionFactor.observation_sensor_preprocessing,
        injection_operator=InjectionOperator.observation_state_key_drop,
        rq1_factor_category=RQ1FactorCategory.observation_sensor_preprocessing,
        rq1_evidence_refs=["github_issue::huggingface/lerobot::2731"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.validation,
    )
    deviation = detect_failure_deviation(case.case_id, baseline, current, replay)
    diagnosis = diagnose_case(
        case,
        deviation,
        ManifestDiff(case_id=case.case_id, baseline_run_id="baseline", current_run_id="current"),
        baseline,
        current,
        [replay],
        ThresholdsConfig(kind="thresholds"),
    )
    assert deviation.detected is True
    assert diagnosis.status == DiagnosisStatus.likely_setup_sensitive_deviation
    assert diagnosis.top_factors[0].factor == AttributionFactor.observation_sensor_preprocessing


def test_ablation_prefix_selection_keeps_paper_cases_only(tmp_path: Path) -> None:
    for name in [
        "paper_lerobot_full_action",
        "paper_failure_dataset",
        "validation_lerobot_action",
        "smoke_maniskill_action",
    ]:
        (tmp_path / name).mkdir()
    selected = _selected_case_dirs(tmp_path, ["paper_lerobot_full_", "paper_failure_"])
    assert [path.name for path in selected] == ["paper_failure_dataset", "paper_lerobot_full_action"]


def test_ablation_summary_counts_false_attribution_on_negative() -> None:
    rows = [
        {
            "bucket": "completed_rollout",
            "method": "manifest_diff_heuristic",
            "evaltriage_detected": False,
            "negative_calibration": True,
            "applicable": True,
            "top1_hit": False,
            "top3_hit": False,
            "false_attribution_on_negative": True,
        },
        {
            "bucket": "completed_rollout",
            "method": "manifest_diff_heuristic",
            "evaltriage_detected": True,
            "negative_calibration": False,
            "applicable": True,
            "top1_hit": True,
            "top3_hit": True,
            "false_attribution_on_negative": False,
        },
    ]
    summary = _summarize_rows(rows)
    row = next(item for item in summary if item["bucket"] == "completed_rollout" and item["method"] == "manifest_diff_heuristic")
    assert row["false_attribution_on_negative"] == 1
    assert row["false_attribution_rate_on_negative"] == 1.0
    assert row["top1_among_detected"] == 1.0


def test_failed_run_rollout_baselines_are_not_applicable() -> None:
    from evaltriage.baselines.naive_statistical import naive_statistical_gate
    from evaltriage.baselines.no_episode_evidence import no_episode_evidence_judgment
    from evaltriage.baselines.rerun_k import rerun_k
    from evaltriage.baselines.single_run import single_run_judgment

    baseline = RunSummary(
        run_id="baseline",
        role=RunRole.baseline,
        platform=Platform.lerobot_libero,
        benchmark="libero",
        task_suite="libero_goal",
        task_ids=[4],
        seed=1000,
        metrics=RunMetrics(success_rate=1.0, num_episodes=1, num_success=1, num_failure=0),
        cost=CostRecord(),
        manifest_path="manifest.json",
        episodes_path="episodes.jsonl",
        logs_path="logs.txt",
    )
    current = _failed_summary("current")
    case = CaseRecord(
        case_id="failure_case",
        platform=Platform.lerobot_libero,
        case_family=CaseFamily.setup_sensitive_factor,
        deviation_symptom=DeviationSymptom.evaluation_crash_or_failure,
        expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
        expected_factor=AttributionFactor.data_dataset_format,
        rq1_factor_category=RQ1FactorCategory.data_dataset_format,
        rq1_evidence_refs=["github_issue::openvla/openvla::93"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.validation,
    )
    thresholds = ThresholdsConfig(kind="thresholds")
    diff = ManifestDiff(case_id="failure_case", baseline_run_id="baseline", current_run_id="current")
    results = [
        single_run_judgment(baseline, current, thresholds),
        rerun_k([baseline, current], thresholds),
        naive_statistical_gate([baseline, current], thresholds),
        no_episode_evidence_judgment(case, baseline, current, [], diff, thresholds),
    ]
    assert all(result.not_applicable_reason for result in results)


def test_logs_only_failure_regex_prioritizes_dataset_missing_feature() -> None:
    from evaltriage.baselines.logs_only_failure_regex import logs_only_failure_regex

    failure = FailureRecord(
        run_id="dataset_failure",
        role=RunRole.current,
        platform=Platform.lerobot_libero,
        factor=AttributionFactor.data_dataset_format,
        operator=InjectionOperator.dataset_remove_feature_column,
        failure_kind="missing_dataset_feature",
        stage="dataset_preflight",
        message="dataset required feature missing: observation.state",
        log_excerpt="KeyError: observation.state",
    )
    result = logs_only_failure_regex(failure, ThresholdsConfig(kind="thresholds"))
    assert result.top_factors
    assert result.top_factors[0] == AttributionFactor.data_dataset_format


def test_paired_episode_shift_detects_distribution_deviation_without_aggregate_drop() -> None:
    baseline = RunSummary(
        run_id="baseline",
        role=RunRole.baseline,
        platform=Platform.lerobot_libero,
        benchmark="libero",
        task_suite="libero_goal",
        task_ids=[4, 5],
        seed=1000,
        metrics=RunMetrics(success_rate=0.5, mean_reward=0.5, num_episodes=2, num_success=1, num_failure=1),
        cost=CostRecord(),
        manifest_path="manifest.json",
        episodes_path="episodes.jsonl",
        logs_path="logs.txt",
    )
    current = baseline.model_copy(
        update={
            "run_id": "current",
            "role": RunRole.current,
            "metrics": RunMetrics(success_rate=0.5, mean_reward=0.5, num_episodes=2, num_success=1, num_failure=1),
        }
    )
    replay = baseline.model_copy(update={"run_id": "replay", "role": RunRole.replay})
    baseline_episodes = [
        EpisodeRecord(episode_id=0, task_suite="libero_goal", task_id=4, seed=1000, success=True, reward=1.0),
        EpisodeRecord(episode_id=1, task_suite="libero_goal", task_id=5, seed=1001, success=False, reward=0.0),
    ]
    current_episodes = [
        EpisodeRecord(episode_id=0, task_suite="libero_goal", task_id=4, seed=1000, success=False, reward=0.0),
        EpisodeRecord(episode_id=1, task_suite="libero_goal", task_id=5, seed=1001, success=True, reward=1.0),
    ]
    replay_episodes = [
        EpisodeRecord(episode_id=0, task_suite="libero_goal", task_id=4, seed=1000, success=True, reward=1.0),
        EpisodeRecord(episode_id=1, task_suite="libero_goal", task_id=5, seed=1001, success=False, reward=0.0),
    ]
    deviation = detect_deviation(
        "unit_harness_case",
        baseline,
        current,
        ThresholdsConfig(kind="thresholds", reward_drop_abs=0.5),
        baseline_episodes=baseline_episodes,
        current_episodes=current_episodes,
        replay_episodes=replay_episodes,
    )
    assert deviation.detected is True
    assert deviation.metric_name == "paired_episode_outcome_mismatch_rate"
    assert deviation.current_value == 1.0


def test_case_config_rejects_mixed_run_request_and_existing_id() -> None:
    request = RunRequest(
        platform=Platform.maniskill,
        run_id="new_run",
        role=RunRole.baseline,
        suite="PickCube-v1",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        control_policy="random",
        obs_mode="state",
    )
    with pytest.raises(ValidationError):
        CaseConfig(
            kind="case",
            case=_case(),
            baseline_runs=[request],
            baseline_run_ids=["existing_run"],
            current_run_ids=["current"],
        )


def test_case_config_rejects_run_request_in_wrong_split() -> None:
    request = RunRequest(
        platform=Platform.maniskill,
        run_id="wrong_role_run",
        role=RunRole.current,
        suite="PickCube-v1",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        control_policy="random",
        obs_mode="state",
    )
    with pytest.raises(ValidationError, match="baseline_runs require role=baseline"):
        CaseConfig(
            kind="case",
            case=_case(),
            baseline_runs=[request],
            current_run_ids=["current"],
        )


def test_validation_maniskill_case_configs_load() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in [
        "validation_maniskill_action_scale_pickcube.yaml",
        "validation_maniskill_reset_seed_pickcube.yaml",
    ]:
        cfg = load_config(root / "configs" / "cases" / name)
        assert isinstance(cfg, CaseConfig)
        assert cfg.case.artifact_split == ArtifactSplit.validation
        assert cfg.baseline_runs
        assert cfg.current_runs
        assert cfg.replay_runs


def test_validation_lerobot_episode_length_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_eval_protocol_episode_length_goal_task0.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.artifact_split == ArtifactSplit.validation
    assert cfg.current_runs[0].episode_length == 10
    assert cfg.current_runs[0].injection.operator == InjectionOperator.eval_protocol_change_episode_length


def test_validation_lerobot_action_control_mode_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_action_control_mode_goal_task0.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.expected_factor == AttributionFactor.action_controller_interface
    assert cfg.current_runs[0].libero_control_mode == "absolute"
    assert cfg.current_runs[0].injection.operator == InjectionOperator.action_change_control_mode


def test_validation_lerobot_action_variant_case_configs_load() -> None:
    root = Path(__file__).resolve().parents[1]
    drop = load_config(root / "configs" / "cases" / "validation_lerobot_action_drop_postprocessor_goal_tasks457.yaml")
    reorder = load_config(root / "configs" / "cases" / "validation_lerobot_action_reorder_dimensions_goal_tasks457.yaml")
    assert isinstance(drop, CaseConfig)
    assert isinstance(reorder, CaseConfig)
    assert drop.current_runs[0].injection.operator == InjectionOperator.action_drop_postprocessor
    assert reorder.current_runs[0].action_dimension_permutation == [1, 0, 2, 3, 4, 5, 6]
    assert reorder.current_runs[0].injection.operator == InjectionOperator.action_reorder_dimensions


def test_validation_lerobot_observation_blackout_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_observation_image_blackout_goal_tasks457.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.expected_factor == AttributionFactor.observation_sensor_preprocessing
    assert cfg.current_runs[0].libero_image_blackout_value == 0.0
    assert cfg.current_runs[0].injection.operator == InjectionOperator.observation_image_blackout


def test_validation_lerobot_observation_state_blackout_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_observation_state_blackout_goal_tasks457.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.expected_factor == AttributionFactor.observation_sensor_preprocessing
    assert cfg.current_runs[0].libero_state_keys == ["observation.state"]
    assert cfg.current_runs[0].libero_state_blackout_value == 0.0
    assert cfg.current_runs[0].injection.operator == InjectionOperator.observation_state_blackout


def test_validation_lerobot_observation_state_noise_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_observation_state_noise_goal_tasks457.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.expected_factor == AttributionFactor.observation_sensor_preprocessing
    assert cfg.current_runs[0].libero_state_noise_std == 10.0
    assert cfg.current_runs[0].injection.operator == InjectionOperator.observation_state_noise


def test_validation_lerobot_dependency_mujoco37_case_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "cases" / "validation_lerobot_dependency_mujoco37_goal_tasks457.yaml")
    assert isinstance(cfg, CaseConfig)
    assert cfg.case.expected_factor == AttributionFactor.dependency_runtime_environment
    assert cfg.current_runs[0].libero_env == "evaltriage-lr-mujoco37"
    assert cfg.current_runs[0].mujoco_env == "evaltriage-lr-mujoco37"
    assert cfg.current_runs[0].injection.operator == InjectionOperator.runtime_switch_mujoco_env
    assert cfg.current_runs[0].injection.params["conda_env"] == "evaltriage-lr-mujoco37"


def test_observation_drop_image_key_injection_requires_single_camera() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_observation_drop_default_camera",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.observation_sensor_preprocessing,
            operator=InjectionOperator.observation_drop_image_key,
            params={"camera_name": "agentview_image"},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_observation_drop_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.observation_sensor_preprocessing,
            injected_factor=AttributionFactor.observation_sensor_preprocessing,
            injection_operator=InjectionOperator.observation_drop_image_key,
            rq1_factor_category=RQ1FactorCategory.observation_sensor_preprocessing,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::1316"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set libero_camera_name=agentview_image"):
        validate_case_operator_linkage(cfg)


def test_observation_blackout_injection_requires_value_match() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_observation_blackout_missing_value",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.observation_sensor_preprocessing,
            operator=InjectionOperator.observation_image_blackout,
            params={"value": 0.0},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_observation_blackout_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.rollout_behavior_anomaly,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.observation_sensor_preprocessing,
            injected_factor=AttributionFactor.observation_sensor_preprocessing,
            injection_operator=InjectionOperator.observation_image_blackout,
            rq1_factor_category=RQ1FactorCategory.observation_sensor_preprocessing,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::2533"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set libero_image_blackout_value=0.0"):
        validate_case_operator_linkage(cfg)


def test_observation_state_noise_injection_requires_std_match() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_observation_state_noise_missing_std",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        libero_state_keys=["observation.state"],
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.observation_sensor_preprocessing,
            operator=InjectionOperator.observation_state_noise,
            params={"keys": ["observation.state"], "std": 10.0},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_observation_state_noise_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.rollout_behavior_anomaly,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.observation_sensor_preprocessing,
            injected_factor=AttributionFactor.observation_sensor_preprocessing,
            injection_operator=InjectionOperator.observation_state_noise,
            rq1_factor_category=RQ1FactorCategory.observation_sensor_preprocessing,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::1007"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set libero_state_noise_std=10.0"):
        validate_case_operator_linkage(cfg)


def test_recovered_setup_factor_prefers_case_injected_factor_over_unrelated_diff() -> None:
    baseline = _summary("baseline", 1.0, 1.0)
    current = _summary("current", 0.0, 0.0)
    replay = _summary("replay", 1.0, 1.0)
    replay.role = RunRole.replay
    case = CaseRecord(
        case_id="unit_observation_case",
        platform=Platform.lerobot_libero,
        case_family=CaseFamily.setup_sensitive_factor,
        deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
        expected_factor=AttributionFactor.observation_sensor_preprocessing,
        injected_factor=AttributionFactor.observation_sensor_preprocessing,
        injection_operator=InjectionOperator.observation_drop_image_key,
        rq1_factor_category=RQ1FactorCategory.observation_sensor_preprocessing,
        rq1_evidence_refs=["github_issue::huggingface/lerobot::1316"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.validation,
    )
    deviation = DeviationRecord(
        case_id=case.case_id,
        baseline_run_ids=["baseline"],
        current_run_ids=["current"],
        symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        metric_name="success_rate",
        baseline_value=1.0,
        current_value=0.0,
        delta=1.0,
        threshold=0.5,
        detected=True,
    )
    diff = diff_manifests(
        case.case_id,
        {"run_id": "baseline", "action": {"control_mode": None}, "observation": {"preprocessing": []}},
        {
            "run_id": "current",
            "action": {"control_mode": "relative"},
            "observation": {"preprocessing": ["camera_name=agentview_image"]},
        },
    )
    diagnosis = diagnose_case(case, deviation, diff, baseline, current, [replay], ThresholdsConfig(kind="thresholds"))
    assert diagnosis.top_factors[0].factor == AttributionFactor.observation_sensor_preprocessing


def test_conflicting_replay_outcomes_force_unknown() -> None:
    baseline = _summary("baseline", 1.0, 1.0)
    current = _summary("current", 0.0, 0.0)
    recovered_replay = _summary("replay_recovered", 1.0, 1.0)
    recovered_replay.role = RunRole.replay
    failed_replay = _summary("replay_not_recovered", 0.0, 0.0)
    failed_replay.role = RunRole.replay
    deviation = DeviationRecord(
        case_id="unit_case",
        baseline_run_ids=["baseline"],
        current_run_ids=["current"],
        symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        metric_name="success_rate",
        baseline_value=1.0,
        current_value=0.0,
        delta=1.0,
        threshold=0.5,
        detected=True,
    )
    diff = ManifestDiff(
        case_id="unit_case",
        baseline_run_id="baseline",
        current_run_id="current",
        entries=[
            {
                "path": "injection.factor",
                "baseline_value": None,
                "current_value": "action_controller_interface",
                "factor": "action_controller_interface",
            }
        ],
    )
    diagnosis = diagnose_case(
        _case(),
        deviation,
        diff,
        baseline,
        current,
        [recovered_replay, failed_replay],
        ThresholdsConfig(kind="thresholds"),
    )
    assert diagnosis.status == DiagnosisStatus.unknown_engineering_factor
    assert diagnosis.unknown_reason is not None
    assert "conflicting replay outcomes" in diagnosis.unknown_reason
    assert "replay_recovered:replay_recovered" in diagnosis.decision_rules_fired
    assert "replay_not_recovered:replay_not_recovered" in diagnosis.decision_rules_fired


def test_unknown_case_can_reference_operator_context_without_expected_setup_status() -> None:
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="unknown_with_operator_context",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.unknown,
            deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
            expected_status=DiagnosisStatus.unknown_engineering_factor,
            injected_factor=AttributionFactor.action_controller_interface,
            injection_operator=InjectionOperator.action_change_control_mode,
            rq1_factor_category=RQ1FactorCategory.unknown_or_not_specified,
            rq1_support_level=RQ1SupportLevel.synthetic_stress,
            artifact_split=ArtifactSplit.validation,
            unknown_reason="conflicting replay outcomes",
        ),
        baseline_run_ids=["baseline"],
        current_run_ids=["current"],
    )
    from evaltriage.config import validate_case_operator_linkage

    validate_case_operator_linkage(cfg)


def test_episode_length_injection_requires_matching_run_field() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_episode_length_injection",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[0],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        episode_length=20,
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.evaluation_protocol_metric,
            operator=InjectionOperator.eval_protocol_change_episode_length,
            params={"episode_length": 10},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_episode_length_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.evaluation_protocol_metric,
            injected_factor=AttributionFactor.evaluation_protocol_metric,
            injection_operator=InjectionOperator.eval_protocol_change_episode_length,
            rq1_factor_category=RQ1FactorCategory.evaluation_protocol_metric,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::1316"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            coverage_status=None,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set episode_length=10"):
        validate_case_operator_linkage(cfg)


def test_lerobot_reset_injection_requires_disabled_init_states() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_lerobot_reset_injection",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[4, 5, 7],
        seed=1000,
        episodes=1,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        libero_init_states=True,
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.reset_or_initial_state,
            operator=InjectionOperator.reset_disable_fixed_init_state,
            params={"init_states": False},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_lerobot_reset_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.evaluation_instability_or_flakiness,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.reset_or_initial_state,
            injected_factor=AttributionFactor.reset_or_initial_state,
            injection_operator=InjectionOperator.reset_disable_fixed_init_state,
            rq1_factor_category=RQ1FactorCategory.reset_or_initial_state,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::3814"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set libero_init_states=False"):
        validate_case_operator_linkage(cfg)


def test_harness_batch_size_injection_requires_matching_run_field() -> None:
    request = RunRequest(
        platform=Platform.lerobot_libero,
        run_id="bad_harness_batch_size_injection",
        role=RunRole.current,
        suite="libero_goal",
        task_ids=[4, 5, 7],
        seed=1000,
        episodes=2,
        output_root=DEFAULT_OUTPUT_ROOT,
        policy_path=Path("/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044"),
        eval_batch_size=1,
        injection=InjectionManifest(
            enabled=True,
            factor=AttributionFactor.evaluation_script_harness,
            operator=InjectionOperator.evaluation_script_modify_harness_flag,
            params={"flag": "eval.batch_size", "value": 2},
        ),
    )
    cfg = CaseConfig(
        kind="case",
        case=CaseRecord(
            case_id="bad_harness_batch_size_case",
            platform=Platform.lerobot_libero,
            case_family=CaseFamily.setup_sensitive_factor,
            deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
            expected_status=DiagnosisStatus.likely_setup_sensitive_deviation,
            expected_factor=AttributionFactor.evaluation_script_harness,
            injected_factor=AttributionFactor.evaluation_script_harness,
            injection_operator=InjectionOperator.evaluation_script_modify_harness_flag,
            rq1_factor_category=RQ1FactorCategory.evaluation_script_harness,
            rq1_evidence_refs=["github_issue::huggingface/lerobot::2850"],
            rq1_support_level=RQ1SupportLevel.evidence_backed,
            artifact_split=ArtifactSplit.validation,
        ),
        baseline_run_ids=["baseline"],
        current_runs=[request],
    )
    from evaltriage.config import validate_case_operator_linkage

    with pytest.raises(ConfigError, match="must set eval_batch_size=2"):
        validate_case_operator_linkage(cfg)


def test_manifest_diff_ignores_volatile_run_fields() -> None:
    baseline = {
        "run_id": "baseline",
        "role": "baseline",
        "evaluation": {"command": "cmd baseline", "episode_length": None},
        "metrics": {"success_rate": 1.0, "mean_reward": 1.0},
        "cost": {"wall_clock_s": 10.0},
        "runtime_env": {"python": "3.12.1"},
    }
    current = {
        "run_id": "current",
        "role": "current",
        "evaluation": {"command": "cmd current", "episode_length": 10},
        "metrics": {"success_rate": 0.0, "mean_reward": 0.0},
        "cost": {"wall_clock_s": 11.0},
        "runtime_env": {"python": "3.12.1"},
    }
    diff = diff_manifests("unit_case", baseline, current)
    assert [entry.path for entry in diff.entries] == ["evaluation.episode_length"]
    assert diff.entries[0].factor == AttributionFactor.evaluation_protocol_metric


def test_manifest_diff_maps_runtime_env_to_dependency_factor() -> None:
    diff = diff_manifests(
        "unit_dependency_case",
        {"run_id": "baseline", "runtime_env": {"conda_env": "evaltriage-lr", "mujoco": "3.8.1"}},
        {"run_id": "current", "runtime_env": {"conda_env": "evaltriage-lr-mujoco37", "mujoco": "3.7.0"}},
    )
    assert [entry.path for entry in diff.entries] == ["runtime_env.conda_env", "runtime_env.mujoco"]
    assert {entry.factor for entry in diff.entries} == {AttributionFactor.dependency_runtime_environment}


def test_manifest_diff_maps_reset_fields_to_reset_factor() -> None:
    diff = diff_manifests(
        "unit_reset_case",
        {"run_id": "baseline", "reset": {"init_states": True}},
        {"run_id": "current", "reset": {"init_states": False}},
    )
    assert [entry.path for entry in diff.entries] == ["reset.init_states"]
    assert diff.entries[0].factor == AttributionFactor.reset_or_initial_state


def test_manifest_diff_maps_eval_batch_size_to_harness_factor() -> None:
    diff = diff_manifests(
        "unit_harness_case",
        {"run_id": "baseline", "evaluation": {"batch_size": 1}},
        {"run_id": "current", "evaluation": {"batch_size": 2}},
    )
    assert [entry.path for entry in diff.entries] == ["evaluation.batch_size"]
    assert diff.entries[0].factor == AttributionFactor.evaluation_script_harness


def test_manifest_diff_keeps_semantic_change_refs_as_regression_evidence() -> None:
    diff = diff_manifests(
        "unit_semantic_case",
        {"run_id": "baseline", "code": {"dirty": True, "semantic_change_refs": []}},
        {
            "run_id": "current",
            "code": {"dirty": True, "semantic_change_refs": ["rq2_true_regression::zero_action_output"]},
        },
    )
    assert [entry.path for entry in diff.entries] == ["code.semantic_change_refs"]
    assert diff.entries[0].factor == AttributionFactor.semantic_code_regression


def test_semantic_regression_without_recovery_diagnoses_true_regression() -> None:
    baseline = _summary("baseline", 1.0, 1.0).model_copy(update={"platform": Platform.lerobot_libero})
    current = _summary("current", 0.0, 0.0).model_copy(
        update={"platform": Platform.lerobot_libero, "role": RunRole.current}
    )
    replay = _summary("replay", 0.0, 0.0).model_copy(update={"platform": Platform.lerobot_libero, "role": RunRole.replay})
    case = CaseRecord(
        case_id="unit_semantic_case",
        platform=Platform.lerobot_libero,
        case_family=CaseFamily.true_regression,
        deviation_symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        expected_status=DiagnosisStatus.likely_true_regression,
        expected_factor=AttributionFactor.semantic_code_regression,
        injected_factor=AttributionFactor.semantic_code_regression,
        injection_operator=InjectionOperator.code_semantic_bug_flag,
        rq1_factor_category=RQ1FactorCategory.evaluation_script_harness,
        rq1_evidence_refs=["github_issue::huggingface/lerobot::2850"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.validation,
    )
    deviation = DeviationRecord(
        case_id=case.case_id,
        baseline_run_ids=["baseline"],
        current_run_ids=["current"],
        symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        metric_name="success_rate",
        baseline_value=1.0,
        current_value=0.0,
        delta=1.0,
        threshold=0.1,
        detected=True,
    )
    diff = ManifestDiff(
        case_id=case.case_id,
        baseline_run_id="baseline",
        current_run_id="current",
        entries=[
            {
                "path": "code.semantic_change_refs",
                "baseline_value": [],
                "current_value": ["rq2_true_regression::zero_action_output"],
                "factor": "semantic_code_regression",
            }
        ],
    )
    diagnosis = diagnose_case(case, deviation, diff, baseline, current, [replay], ThresholdsConfig(kind="thresholds"))
    assert diagnosis.status == DiagnosisStatus.likely_true_regression
    assert diagnosis.top_factors[0].factor == AttributionFactor.semantic_code_regression


def test_repeated_run_spread_diagnoses_flaky_status_without_manifest_diff() -> None:
    baseline = _summary("baseline", 1.0, 1.0).model_copy(update={"platform": Platform.lerobot_libero})
    baseline_2 = _summary("baseline_2", 0.7, 0.7).model_copy(update={"platform": Platform.lerobot_libero})
    current = _summary("current", 0.8, 0.8).model_copy(
        update={"platform": Platform.lerobot_libero, "role": RunRole.current}
    )
    replay = _summary("replay", 0.6, 0.6).model_copy(update={"platform": Platform.lerobot_libero, "role": RunRole.replay})
    thresholds = ThresholdsConfig(kind="thresholds", flaky_success_rate_std=0.2)
    deviation = detect_repeated_run_instability(
        "unit_flaky_case",
        [baseline, baseline_2],
        [current],
        [replay],
        thresholds,
    )
    case = CaseRecord(
        case_id="unit_flaky_case",
        platform=Platform.lerobot_libero,
        case_family=CaseFamily.flaky,
        deviation_symptom=DeviationSymptom.evaluation_instability_or_flakiness,
        expected_status=DiagnosisStatus.likely_flaky_evaluation,
        expected_factor=AttributionFactor.seed_or_randomness,
        rq1_factor_category=RQ1FactorCategory.seed_or_randomness,
        rq1_evidence_refs=["github_issue::Farama-Foundation/Metaworld::555"],
        rq1_support_level=RQ1SupportLevel.evidence_backed,
        artifact_split=ArtifactSplit.validation,
    )
    diagnosis = diagnose_case(
        case,
        deviation,
        ManifestDiff(case_id=case.case_id, baseline_run_id="baseline", current_run_id="current"),
        baseline,
        current,
        [replay],
        thresholds,
    )
    assert deviation.detected is True
    assert deviation.metric_name == "success_rate_spread"
    assert diagnosis.status == DiagnosisStatus.likely_flaky_evaluation


def test_episode_video_paths_are_finalized_after_staged_run_commit() -> None:
    episodes = [
        EpisodeRecord(
            episode_id=0,
            task_suite="libero_goal",
            task_id=0,
            seed=1000,
            success=True,
            reward=1.0,
            video_path="/formal/runs/.staging_run/raw/videos/eval_episode_0.mp4",
        )
    ]
    finalized = _finalize_episode_paths(episodes, Path("/formal/runs/.staging_run"), Path("/formal/runs/final_run"))
    assert finalized[0].video_path == "/formal/runs/final_run/raw/videos/eval_episode_0.mp4"
