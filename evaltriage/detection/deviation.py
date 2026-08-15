"""Deviation detection over real run summaries and episode evidence."""

from __future__ import annotations

from ..schemas import DeviationRecord, DeviationSymptom, EpisodeRecord, ExecutionStatus, RunSummary, ThresholdsConfig


def detect_failure_deviation(
    case_id: str,
    baseline: RunSummary,
    current: RunSummary,
    replay: RunSummary | None = None,
) -> DeviationRecord:
    baseline_completed = baseline.execution_status == ExecutionStatus.completed
    current_failed = current.execution_status == ExecutionStatus.failed
    replay_completed = replay is not None and replay.execution_status == ExecutionStatus.completed
    detected = bool(baseline_completed and current_failed and (replay is None or replay_completed))
    evidence = [
        (
            "execution_status "
            f"baseline={baseline.execution_status.value} current={current.execution_status.value} "
            f"replay={replay.execution_status.value if replay else None}"
        )
    ]
    if replay is not None and not replay_completed:
        evidence.append("replay did not restore a completed evaluation")
    return DeviationRecord(
        case_id=case_id,
        baseline_run_ids=[baseline.run_id],
        current_run_ids=[current.run_id],
        symptom=DeviationSymptom.evaluation_crash_or_failure,
        metric_name="execution_status",
        baseline_value=1.0 if baseline_completed else 0.0,
        current_value=0.0 if current_failed else 1.0,
        delta=1.0 if detected else 0.0,
        threshold=None,
        detected=detected,
        evidence=evidence,
    )


def detect_repeated_run_instability(
    case_id: str,
    baseline_runs: list[RunSummary],
    current_runs: list[RunSummary],
    replay_runs: list[RunSummary],
    thresholds: ThresholdsConfig,
) -> DeviationRecord:
    summaries = [*baseline_runs, *current_runs, *replay_runs]
    completed = [summary for summary in summaries if summary.execution_status == ExecutionStatus.completed]
    rates = [summary.metrics.success_rate for summary in completed if summary.metrics.success_rate is not None]
    if len(rates) < 2:
        return DeviationRecord(
            case_id=case_id,
            baseline_run_ids=[summary.run_id for summary in baseline_runs],
            current_run_ids=[summary.run_id for summary in [*current_runs, *replay_runs]],
            symptom=DeviationSymptom.evaluation_instability_or_flakiness,
            metric_name="success_rate_spread",
            baseline_value=None,
            current_value=None,
            delta=None,
            threshold=thresholds.flaky_success_rate_std,
            detected=False,
            evidence=[
                "same_manifest_repeated_run_instability unavailable: fewer than two completed success_rate values"
            ],
        )
    spread = max(rates) - min(rates)
    detected = spread >= thresholds.flaky_success_rate_std
    rate_text = ", ".join(
        f"{summary.run_id}={summary.metrics.success_rate}"
        for summary in completed
        if summary.metrics.success_rate is not None
    )
    return DeviationRecord(
        case_id=case_id,
        baseline_run_ids=[summary.run_id for summary in baseline_runs],
        current_run_ids=[summary.run_id for summary in [*current_runs, *replay_runs]],
        symptom=DeviationSymptom.evaluation_instability_or_flakiness,
        metric_name="success_rate_spread",
        baseline_value=min(rates),
        current_value=max(rates),
        delta=spread,
        threshold=thresholds.flaky_success_rate_std,
        detected=detected,
        evidence=[
            (
                "same_manifest_repeated_run_instability "
                f"runs={len(rates)} spread={spread} threshold={thresholds.flaky_success_rate_std}"
            ),
            f"success_rates: {rate_text}",
        ],
    )


def detect_success_rate_deviation(
    case_id: str,
    baseline: RunSummary,
    current: RunSummary,
    thresholds: ThresholdsConfig,
) -> DeviationRecord:
    b = baseline.metrics.success_rate
    c = current.metrics.success_rate
    delta = None if b is None or c is None else b - c
    detected = bool(delta is not None and delta >= thresholds.success_rate_drop_abs)
    return DeviationRecord(
        case_id=case_id,
        baseline_run_ids=[baseline.run_id],
        current_run_ids=[current.run_id],
        symptom=DeviationSymptom.success_rate_drop_or_mismatch,
        metric_name="success_rate",
        baseline_value=b,
        current_value=c,
        delta=delta,
        threshold=thresholds.success_rate_drop_abs,
        detected=detected,
        evidence=[f"success_rate baseline={b} current={c} delta={delta} threshold={thresholds.success_rate_drop_abs}"],
    )


def detect_deviation(
    case_id: str,
    baseline: RunSummary,
    current: RunSummary,
    thresholds: ThresholdsConfig,
    baseline_episodes: list[EpisodeRecord] | None = None,
    current_episodes: list[EpisodeRecord] | None = None,
    replay_episodes: list[EpisodeRecord] | None = None,
) -> DeviationRecord:
    success = detect_success_rate_deviation(case_id, baseline, current, thresholds)
    if success.detected:
        return success

    paired = detect_paired_episode_outcome_shift(
        case_id,
        baseline,
        current,
        thresholds,
        baseline_episodes=baseline_episodes,
        current_episodes=current_episodes,
        replay_episodes=replay_episodes,
        prior_evidence=success.evidence,
    )
    if paired is not None:
        return paired

    if thresholds.reward_drop_abs is None:
        return success

    b = baseline.metrics.mean_reward
    c = current.metrics.mean_reward
    delta = None if b is None or c is None else b - c
    detected = bool(delta is not None and delta >= thresholds.reward_drop_abs)
    if b is None or c is None:
        evidence = ["mean_reward comparison unavailable because one run is missing mean_reward"]
    else:
        evidence = [f"mean_reward baseline={b} current={c} delta={delta} threshold={thresholds.reward_drop_abs}"]
    return DeviationRecord(
        case_id=case_id,
        baseline_run_ids=[baseline.run_id],
        current_run_ids=[current.run_id],
        symptom=DeviationSymptom.reward_score_metric_mismatch,
        metric_name="mean_reward",
        baseline_value=b,
        current_value=c,
        delta=delta,
        threshold=thresholds.reward_drop_abs,
        detected=detected,
        evidence=[*success.evidence, *evidence],
    )


def _episode_key(episode: EpisodeRecord) -> tuple[int, int | None]:
    return episode.task_id, episode.seed


def detect_paired_episode_outcome_shift(
    case_id: str,
    baseline: RunSummary,
    current: RunSummary,
    thresholds: ThresholdsConfig,
    *,
    baseline_episodes: list[EpisodeRecord] | None,
    current_episodes: list[EpisodeRecord] | None,
    replay_episodes: list[EpisodeRecord] | None,
    prior_evidence: list[str],
) -> DeviationRecord | None:
    if not baseline_episodes or not current_episodes or not replay_episodes:
        return None
    baseline_by_key = {_episode_key(ep): ep for ep in baseline_episodes}
    current_by_key = {_episode_key(ep): ep for ep in current_episodes}
    replay_by_key = {_episode_key(ep): ep for ep in replay_episodes}
    common_keys = sorted(set(baseline_by_key) & set(current_by_key) & set(replay_by_key))
    if not common_keys:
        return None

    stable_keys = []
    shifted_keys = []
    for key in common_keys:
        b = baseline_by_key[key].success
        c = current_by_key[key].success
        r = replay_by_key[key].success
        if b != r:
            continue
        stable_keys.append(key)
        if b != c:
            shifted_keys.append(key)

    if not stable_keys or not shifted_keys:
        return None

    shift_rate = len(shifted_keys) / len(stable_keys)
    shifted_text = ", ".join(f"task={task_id}/seed={seed}" for task_id, seed in shifted_keys[:10])
    evidence = [
        *prior_evidence,
        (
            "paired_episode_outcome_shift "
            f"stable_pairs={len(stable_keys)} shifted_pairs={len(shifted_keys)} "
            f"shift_rate={shift_rate} shifted={shifted_text}"
        ),
        (
            "baseline/replay agree on paired episode outcomes while current differs; "
            "aggregate success_rate may be unchanged"
        ),
    ]
    return DeviationRecord(
        case_id=case_id,
        baseline_run_ids=[baseline.run_id],
        current_run_ids=[current.run_id],
        symptom=DeviationSymptom.rollout_behavior_anomaly,
        metric_name="paired_episode_outcome_mismatch_rate",
        baseline_value=0.0,
        current_value=shift_rate,
        delta=shift_rate,
        threshold=None,
        detected=True,
        evidence=evidence,
    )
