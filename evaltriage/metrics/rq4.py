"""RQ4 cost metrics."""

from __future__ import annotations


def cost_metrics(rows: list[dict]) -> list[dict]:
    numeric = [
        "rerun_count",
        "episode_count",
        "failed_run_count",
        "gpu_minutes",
        "wall_clock_minutes",
        "diagnosis_latency_s",
        "pipeline_overhead_s",
        "affected_task_replay_cost_ratio",
    ]
    out = []
    for key in numeric:
        vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
        out.append({"metric": key, "mean": sum(vals) / len(vals) if vals else None, "n": len(vals)})
    return out
