"""Common runner payloads."""

from __future__ import annotations

from pydantic import BaseModel

from ..schemas import CostRecord, EpisodeRecord, RunMetrics, RuntimeEnvManifest


class RunnerExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stage: str = "runner",
        failure_kind: str = "exception",
        raw_output_path: str | None = None,
        cost: CostRecord | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stage = stage
        self.failure_kind = failure_kind
        self.raw_output_path = raw_output_path
        self.cost = cost or CostRecord()


class RunnerResult(BaseModel):
    command: list[str] | None = None
    raw_output_path: str | None = None
    effective_policy_path: str | None = None
    episodes: list[EpisodeRecord]
    metrics: RunMetrics
    cost: CostRecord
    benchmark: str
    runtime_env: RuntimeEnvManifest | None = None
