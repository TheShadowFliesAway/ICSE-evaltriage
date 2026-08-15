"""Replay execution helpers.

Replay execution delegates to evaltriage-run via RunRequest. It does not create
synthetic replay outcomes.
"""

from __future__ import annotations

from ..runners.executor import execute_run
from ..schemas import ReplayPlan, RunRequest, RunSummary


def execute_replay_plan(plan: ReplayPlan, run_requests: dict[str, RunRequest]) -> list[RunSummary]:
    summaries = []
    for step in plan.steps:
        if step.run_id is None:
            continue
        if step.run_id not in run_requests:
            raise RuntimeError(f"missing replay run request for {step.run_id}")
        summaries.append(execute_run(run_requests[step.run_id]))
    return summaries
