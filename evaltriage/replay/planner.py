"""Budget-aware replay planner."""

from __future__ import annotations

from ..schemas import AttributionFactor, DeviationRecord, ManifestDiff, ReplayPlan, ReplayStep, ReplayType


FACTOR_REPLAY = {
    AttributionFactor.seed_or_randomness: ReplayType.restore_seed_or_init,
    AttributionFactor.reset_or_initial_state: ReplayType.restore_seed_or_init,
    AttributionFactor.object_scene_task_initialization: ReplayType.restore_seed_or_init,
    AttributionFactor.action_controller_interface: ReplayType.restore_action_interface,
    AttributionFactor.observation_sensor_preprocessing: ReplayType.restore_observation_pipeline,
    AttributionFactor.checkpoint_config_compatibility: ReplayType.restore_checkpoint_config,
    AttributionFactor.evaluation_protocol_metric: ReplayType.restore_eval_protocol,
    AttributionFactor.evaluation_script_harness: ReplayType.restore_eval_protocol,
    AttributionFactor.dependency_runtime_environment: ReplayType.restore_runtime_env,
    AttributionFactor.simulator_physics_rendering: ReplayType.restore_runtime_env,
    AttributionFactor.data_dataset_format: ReplayType.restore_dataset_format,
}


def plan_replay(case_id: str, deviation: DeviationRecord, manifest_diff: ManifestDiff, budget: str) -> ReplayPlan:
    steps: list[ReplayStep] = []
    seen: set[AttributionFactor] = set()
    for entry in manifest_diff.entries:
        if entry.factor is None:
            continue
        try:
            factor = AttributionFactor(entry.factor)
        except ValueError:
            continue
        if factor in seen or factor not in FACTOR_REPLAY:
            continue
        seen.add(factor)
        steps.append(
            ReplayStep(
                replay_id=f"replay_{len(steps)}_{factor.value}",
                replay_type=FACTOR_REPLAY[factor],
                target_factor=factor,
                reason=f"manifest diff at {entry.path}",
                estimated_episodes=None,
                params={"diff_path": entry.path},
            )
        )
    if not steps and deviation.detected:
        steps.append(
            ReplayStep(
                replay_id="replay_same_manifest",
                replay_type=ReplayType.rerun_same_manifest,
                reason="deviation detected but manifest diff has no attributable factor",
            )
        )
    return ReplayPlan(case_id=case_id, budget=budget, steps=steps)
