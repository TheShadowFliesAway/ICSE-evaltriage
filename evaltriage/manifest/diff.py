"""Manifest diff utilities used by replay and diagnosis."""

from __future__ import annotations

from typing import Any

from ..schemas import ManifestDiff, ManifestDiffEntry


FACTOR_PATH_HINTS = {
    "seed": "seed_or_randomness",
    "runtime_env": "dependency_runtime_environment",
    "policy": "checkpoint_config_compatibility",
    "code": "semantic_code_regression",
    "observation": "observation_sensor_preprocessing",
    "action": "action_controller_interface",
    "reset": "reset_or_initial_state",
    "evaluation": "evaluation_protocol_metric",
    "injection": "evaluation_script_harness",
}

EXACT_FACTOR_PATH_HINTS = {
    "evaluation.batch_size": "evaluation_script_harness",
    "evaluation.use_async_envs": "evaluation_script_harness",
}


IGNORED_DIFF_PATHS = {
    "run_id",
    "role",
    "evaluation.command",
    "cost.wall_clock_s",
    "cost.gpu_minutes",
    "cost.max_gpu_mem_mb",
    "metrics.success_rate",
    "metrics.mean_reward",
    "metrics.num_episodes",
    "metrics.num_success",
    "metrics.num_failure",
}

IGNORED_DIFF_PREFIXES = (
    "code.",
)

SEMANTIC_CODE_DIFF_PATHS = {
    "code.semantic_change_refs",
}


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(item, child))
        return out
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def diff_manifests(case_id: str, baseline: dict, current: dict) -> ManifestDiff:
    bflat = _flatten(baseline)
    cflat = _flatten(current)
    entries = []
    missing = []
    for key in sorted(set(bflat) | set(cflat)):
        if key in IGNORED_DIFF_PATHS or (
            any(key.startswith(prefix) for prefix in IGNORED_DIFF_PREFIXES)
            and key not in SEMANTIC_CODE_DIFF_PATHS
        ):
            continue
        if key not in bflat or key not in cflat:
            missing.append(key)
            continue
        if bflat[key] != cflat[key]:
            top = key.split(".", 1)[0]
            factor = EXACT_FACTOR_PATH_HINTS.get(key, FACTOR_PATH_HINTS.get(top))
            if key in SEMANTIC_CODE_DIFF_PATHS:
                factor = "semantic_code_regression"
            if top == "injection" and current.get("injection", {}).get("factor"):
                factor = current["injection"]["factor"]
            if key == "injection.operator" and cflat[key] == "code.semantic_bug_flag":
                factor = "semantic_code_regression"
            entries.append(
                ManifestDiffEntry(
                    path=key,
                    baseline_value=bflat[key],
                    current_value=cflat[key],
                    factor=factor,
                )
            )
    return ManifestDiff(
        case_id=case_id,
        baseline_run_id=str(baseline.get("run_id")),
        current_run_id=str(current.get("run_id")),
        entries=entries,
        missing_fields=missing,
    )
