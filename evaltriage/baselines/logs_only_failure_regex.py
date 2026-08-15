"""Pre-registered failure-log-only baseline for crash/failure cases."""

from __future__ import annotations

from ..schemas import AttributionFactor, BaselineMethodResult, DiagnosisStatus, FailureRecord, ThresholdsConfig


PATTERNS: list[tuple[str, AttributionFactor, str]] = [
    ("missing_dataset_feature", AttributionFactor.data_dataset_format, "dataset preflight missing feature kind"),
    ("dataset required feature missing", AttributionFactor.data_dataset_format, "dataset preflight missing feature message"),
    ("observation key missing", AttributionFactor.observation_sensor_preprocessing, "policy observation mapping error"),
    ("keyerror: 'observation.state'", AttributionFactor.observation_sensor_preprocessing, "missing policy observation state key"),
    ("safetensors", AttributionFactor.checkpoint_config_compatibility, "checkpoint stats/loading error"),
    ("processor", AttributionFactor.checkpoint_config_compatibility, "processor config/loading error"),
    ("conda", AttributionFactor.dependency_runtime_environment, "conda/runtime launch error"),
    ("not found", AttributionFactor.dependency_runtime_environment, "runtime command or module missing"),
    ("segmentation fault", AttributionFactor.simulator_physics_rendering, "simulator process crash"),
    ("exit code 139", AttributionFactor.simulator_physics_rendering, "simulator segfault exit code"),
]


def logs_only_failure_regex(
    failure: FailureRecord | None,
    thresholds: ThresholdsConfig,
) -> BaselineMethodResult:
    if failure is None:
        return BaselineMethodResult(method="logs_only_failure_regex", not_applicable_reason="no failure.json")
    text = "\n".join(
        [
            failure.failure_kind,
            failure.stage,
            failure.message,
            failure.log_excerpt or "",
        ]
    ).lower()
    factors: list[AttributionFactor] = []
    evidence: list[str] = []
    for pattern, factor, reason in PATTERNS:
        if pattern in text and factor not in factors:
            factors.append(factor)
            evidence.append(f"pre_registered_pattern={pattern!r}; reason={reason}")
    if not factors:
        return BaselineMethodResult(
            method="logs_only_failure_regex",
            status=DiagnosisStatus.unknown_engineering_factor,
            confidence=0.2,
            evidence=["no known failure regex matched"],
        )
    return BaselineMethodResult(
        method="logs_only_failure_regex",
        status=DiagnosisStatus.likely_setup_sensitive_deviation,
        top_factors=factors[:3],
        confidence=thresholds.medium_confidence,
        evidence=evidence[:3],
    )
