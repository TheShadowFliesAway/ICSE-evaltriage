"""RQ3 factor attribution and abstention metrics."""

from __future__ import annotations


def factor_metrics(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for bucket in ["all", "completed_rollout", "failed_run"]:
        bucket_rows = rows if bucket == "all" else [r for r in rows if r.get("matrix_bucket") == bucket]
        out.extend(_factor_metrics_for_bucket(bucket_rows, bucket))
    return out


def _factor_metrics_for_bucket(rows: list[dict], bucket: str) -> list[dict]:
    factor_rows = [r for r in rows if r.get("expected_factor") and r.get("expected_status") != "unknown_engineering_factor"]
    top1_total = len(factor_rows)
    top1_correct = sum(1 for r in factor_rows if r.get("expected_factor") == r.get("evaltriage_top1_factor"))
    top3_correct = sum(1 for r in factor_rows if r.get("expected_factor") in (r.get("evaltriage_top3_factors") or []))
    rr_vals = [float(r["reciprocal_rank"]) for r in factor_rows if r.get("reciprocal_rank") not in (None, "")]
    unknown_rows = [r for r in rows if r.get("expected_status") == "unknown_engineering_factor"]
    abstain_correct = sum(1 for r in unknown_rows if r.get("evaltriage_status") == "unknown_engineering_factor")
    over_attribution = sum(1 for r in unknown_rows if r.get("over_attribution_error"))
    out = [
        {"metric": "top1_factor_accuracy", "bucket": bucket, "value": top1_correct / top1_total if top1_total else None, "n": top1_total},
        {"metric": "top3_factor_accuracy", "bucket": bucket, "value": top3_correct / top1_total if top1_total else None, "n": top1_total},
        {"metric": "mrr", "bucket": bucket, "value": sum(rr_vals) / top1_total if top1_total else None, "n": top1_total},
        {"metric": "unsupported_unknown_factor_rate", "bucket": bucket, "value": len(unknown_rows) / len(rows) if rows else None, "n": len(rows)},
        {
            "metric": "unknown_abstention_correctness",
            "bucket": bucket,
            "value": abstain_correct / len(unknown_rows) if unknown_rows else None,
            "n": len(unknown_rows),
        },
        {
            "metric": "over_attribution_error_rate",
            "bucket": bucket,
            "value": over_attribution / len(unknown_rows) if unknown_rows else None,
            "n": len(unknown_rows),
        },
    ]
    factors = sorted({r.get("expected_factor") for r in factor_rows if r.get("expected_factor")})
    for factor in factors:
        subset = [r for r in factor_rows if r.get("expected_factor") == factor]
        correct = sum(1 for r in subset if r.get("expected_factor") == r.get("evaltriage_top1_factor"))
        out.append(
            {
                "metric": "per_factor_top1_accuracy",
                "bucket": bucket,
                "factor": factor,
                "value": correct / len(subset),
                "n": len(subset),
            }
        )
    return out
