"""Create paper robustness appendix tables from aggregate CSV outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PAPER_PREFIXES = ("paper_lerobot_full_", "paper_failure_")
ROBUST_PREFIXES = ("robust_lerobot_ep3_", "robust_failure_")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def filter_prefix(rows: Iterable[dict[str, str]], prefixes: tuple[str, ...]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("case_id", "").startswith(prefixes)]


def bool_value(value: object) -> bool:
    return str(value).lower() == "true"


def summary(rows: list[dict[str, str]], label: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row.get("bucket", ""), row.get("factor", ""))].append(row)
    for (bucket, factor), subset in sorted(groups.items()):
        detected = [row for row in subset if bool_value(row.get("detected"))]
        top1_hits = [row for row in detected if row.get("top1_factor") == row.get("factor")]
        conclusions = Counter(row.get("conclusion", "") for row in subset)
        out.append(
            {
                "split": label,
                "bucket": bucket,
                "factor": factor,
                "n_cases": len(subset),
                "detected_cases": len(detected),
                "top1_hits_detected": len(top1_hits),
                "top1_accuracy_detected": len(top1_hits) / len(detected) if detected else None,
                "top1_hits_all_cases": len(top1_hits),
                "top1_accuracy_all_cases": len(top1_hits) / len(subset) if subset else None,
                "conclusions": json.dumps(dict(conclusions), sort_keys=True),
            }
        )
    return out


def count_rows(paper: list[dict[str, str]], robust: list[dict[str, str]], combined: list[dict[str, str]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for label, rows in [("paper", paper), ("robustness", robust), ("combined", combined)]:
        bucket_counts = Counter(row.get("bucket", "") for row in rows)
        conclusion_counts = Counter(row.get("conclusion", "") for row in rows)
        factor_counts = Counter(row.get("factor", "") for row in rows)
        out.append(
            {
                "split": label,
                "n_cases": len(rows),
                "completed_rollout_cases": bucket_counts.get("completed_rollout", 0),
                "failed_run_cases": bucket_counts.get("failed_run", 0),
                "detected_cases": sum(1 for row in rows if bool_value(row.get("detected"))),
                "success_candidate_cases": conclusion_counts.get("success candidate", 0),
                "negative_calibration_cases": conclusion_counts.get("negative calibration", 0),
                "failure_supported_cases": conclusion_counts.get("failure-supported", 0),
                "n_factors": len([factor for factor in factor_counts if factor]),
                "factor_counts": json.dumps(dict(factor_counts), sort_keys=True),
                "conclusion_counts": json.dumps(dict(conclusion_counts), sort_keys=True),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", type=Path, required=True)
    args = parser.parse_args()

    rq1_path = args.metrics_dir / "rq1_factor_matrix.csv"
    rows = read_csv(rq1_path)
    paper = filter_prefix(rows, PAPER_PREFIXES)
    robust = filter_prefix(rows, ROBUST_PREFIXES)
    combined = paper + robust

    write_csv(args.metrics_dir / "robustness_factor_matrix.csv", robust)
    write_csv(args.metrics_dir / "combined_factor_matrix.csv", combined)
    write_csv(args.metrics_dir / "robustness_failure_matrix.csv", [row for row in robust if row.get("bucket") == "failed_run"])
    write_csv(args.metrics_dir / "combined_failure_matrix.csv", [row for row in combined if row.get("bucket") == "failed_run"])
    write_csv(args.metrics_dir / "robustness_summary.csv", summary(robust, "robustness"))
    write_csv(args.metrics_dir / "combined_summary.csv", summary(combined, "combined"))
    write_csv(args.metrics_dir / "robustness_counts_table.csv", count_rows(paper, robust, combined))


if __name__ == "__main__":
    main()
