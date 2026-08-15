#!/usr/bin/env python3
"""Build RQ1 evidence tables from the frozen JSONL evidence file.

This script intentionally performs only deterministic table construction. It
does not rerun GitHub mining, call an LLM, or modify the source JSONL.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSONL = ROOT / "rq1_evidence.jsonl"
TABLE_DIR = ROOT / "tables"
FIGURE_DIR = ROOT / "figures"
SUMMARY_MD = ROOT / "EvalTriage_RQ1_tables.md"

EXPECTED_TOTAL = 473
EXPECTED_ROLE_COUNTS = {
    "deviation_and_factor": 258,
    "deviation_only": 144,
    "factor_only": 71,
}
PIPELINE_COUNTS = [
    ("GitHub keyword mining candidates", 2714),
    ("Stage-1 LLM relevance screening", 641),
    ("Manual classification retained evidence records", 473),
]

REQUIRED_FIELDS = [
    "candidate_id",
    "project",
    "repo",
    "source_type",
    "number",
    "title",
    "url",
    "state",
    "evidence_role",
    "primary_deviation_symptom",
    "primary_factor_category",
    "primary_affected_phase",
]

INDEX_FIELDS = [
    "candidate_id",
    "project",
    "repo",
    "source_type",
    "number",
    "state",
    "title",
    "url",
    "evidence_role",
    "primary_deviation_symptom",
    "primary_factor_category",
    "primary_affected_phase",
    "deviation_symptoms",
    "factor_categories",
    "affected_phases",
    "symptom_evidence_quote",
    "factor_evidence_quote",
    "phase_evidence_quote",
    "created_at",
    "updated_at",
    "closed_at",
    "comment_count",
]

FACTOR_CASE_MAPPING = {
    "seed_or_randomness": (
        "rerun_same_manifest; restore_seed_or_init",
        "LeRobot+LIBERO; ManiSkill",
        "flaky; setup_sensitive_factor",
        "core_planned",
    ),
    "reset_or_initial_state": (
        "reset.disable_fixed_init_state; restore_seed_or_init",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "object_scene_task_initialization": (
        "reset.disable_fixed_init_state; maniskill.change_object_pose",
        "ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "simulator_physics_rendering": (
        "runtime.switch_mujoco_env",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "dependency_runtime_environment": (
        "runtime.switch_mujoco_env",
        "LeRobot+LIBERO",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "action_controller_interface": (
        "action.scale_multiplier; action.drop_postprocessor; action.reorder_dimensions",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "observation_sensor_preprocessing": (
        "observation.swap_camera_keys; observation.image_flip; observation.drop_image_key",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "checkpoint_config_compatibility": (
        "checkpoint.remove_processor_stats; checkpoint.config_feature_mismatch",
        "LeRobot+LIBERO",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "evaluation_protocol_metric": (
        "eval_protocol.change_episode_length; eval_protocol.change_success_aggregation",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "evaluation_script_harness": (
        "eval_protocol.change_episode_length; evaluation_script.modify_harness_flag",
        "LeRobot+LIBERO; ManiSkill",
        "setup_sensitive_factor; true_regression",
        "core_planned",
    ),
    "ci_regression_evaluation": (
        "code.semantic_bug_flag; evaltriage-aggregate regression report",
        "Artifact/precomputed metrics",
        "true_regression",
        "supporting_context",
    ),
    "data_dataset_format": (
        "dataset.remove_feature_column; dataset.corrupt_video_or_parquet_reference",
        "LeRobot dataset",
        "setup_sensitive_factor",
        "core_planned",
    ),
    "training_evaluation_interaction": (
        "code.semantic_bug_flag; checkpoint.remove_processor_stats",
        "LeRobot+LIBERO",
        "setup_sensitive_factor; true_regression",
        "planned_extension",
    ),
    "unknown_or_not_specified": (
        "manifest.hide_factor_fields",
        "LeRobot+LIBERO; ManiSkill",
        "unknown",
        "core_planned",
    ),
}


def is_unknown(category: str | None) -> bool:
    return bool(category) and "unknown" in category


def clean_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return " ".join(str(value).replace("\r\n", "\n").replace("\r", "\n").split())


def short_text(value: str, limit: int = 180) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def md_escape(value: str) -> str:
    return clean_cell(value).replace("|", "\\|").replace("\n", "<br>")


def md_table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(str(cell)) for cell in row) + " |")
    return "\n".join(lines)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc
    return rows


def validate_rows(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_TOTAL:
        raise ValueError(f"Expected {EXPECTED_TOTAL} rows, found {len(rows)}")

    ids = [row.get("candidate_id") for row in rows]
    duplicate_ids = [cid for cid, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise ValueError(f"Duplicate candidate_id values: {duplicate_ids[:10]}")

    missing = defaultdict(list)
    for row in rows:
        cid = row.get("candidate_id", "<missing candidate_id>")
        for field in REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                missing[field].append(cid)
    if missing:
        details = "; ".join(f"{field}: {ids[:3]}" for field, ids in missing.items())
        raise ValueError(f"Missing required fields: {details}")

    role_counts = Counter(row.get("evidence_role") for row in rows)
    if dict(role_counts) != EXPECTED_ROLE_COUNTS:
        raise ValueError(
            "Unexpected evidence_role counts: "
            f"expected {EXPECTED_ROLE_COUNTS}, found {dict(role_counts)}"
        )


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_cell(row.get(field, "")) for field in fieldnames})


def build_evidence_index(rows: list[dict]) -> list[dict]:
    return [{field: row.get(field, "") for field in INDEX_FIELDS} for row in rows]


def build_taxonomy_counts(rows: list[dict]) -> list[dict]:
    specs = [
        ("evidence_role", "evidence_role", False),
        ("primary_deviation_symptom", "primary_deviation_symptom", False),
        ("primary_factor_category", "primary_factor_category", False),
        ("primary_affected_phase", "primary_affected_phase", False),
        ("deviation_symptoms_multi", "deviation_symptoms", True),
        ("factor_categories_multi", "factor_categories", True),
        ("affected_phases_multi", "affected_phases", True),
    ]
    output = []
    for taxonomy_type, field, is_multi in specs:
        items_by_category = defaultdict(list)
        for row in rows:
            values = row.get(field) or []
            if not is_multi:
                values = [values]
            for value in values:
                items_by_category[value].append(row)

        total = sum(len(items) for items in items_by_category.values())
        non_unknown_total = sum(
            len(items) for category, items in items_by_category.items() if not is_unknown(category)
        )
        for category, items in sorted(
            items_by_category.items(), key=lambda item: (-len(item[1]), str(item[0]))
        ):
            if is_unknown(category):
                percent_excluding_unknown = ""
            elif non_unknown_total:
                percent_excluding_unknown = f"{len(items) / non_unknown_total * 100:.2f}"
            else:
                percent_excluding_unknown = ""
            output.append(
                {
                    "taxonomy_type": taxonomy_type,
                    "category": category,
                    "count": len(items),
                    "percent_of_all": f"{len(items) / total * 100:.2f}" if total else "0.00",
                    "percent_excluding_unknown": percent_excluding_unknown,
                    "example_candidate_ids": ";".join(
                        row["candidate_id"] for row in items[:5]
                    ),
                }
            )
    return output


def most_common_value(values: Iterable[str]) -> str:
    counter = Counter(value for value in values if value)
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def build_project_breakdown(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["project"], row["repo"])].append(row)

    output = []
    for (project, repo), items in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        role_counts = Counter(row["evidence_role"] for row in items)
        source_counts = Counter(row["source_type"] for row in items)
        state_counts = Counter(row["state"] for row in items)
        unknown_count = sum(
            1 for row in items if row["primary_factor_category"] == "unknown_or_not_specified"
        )
        output.append(
            {
                "project": project,
                "repo": repo,
                "total_evidence": len(items),
                "issue_count": source_counts.get("issue", 0),
                "pr_count": source_counts.get("pr", 0),
                "open_count": state_counts.get("open", 0),
                "closed_count": state_counts.get("closed", 0),
                "deviation_and_factor_count": role_counts.get("deviation_and_factor", 0),
                "deviation_only_count": role_counts.get("deviation_only", 0),
                "factor_only_count": role_counts.get("factor_only", 0),
                "unknown_primary_factor_count": unknown_count,
                "unknown_primary_factor_percent": f"{unknown_count / len(items) * 100:.2f}",
                "top_primary_deviation_symptom": most_common_value(
                    row["primary_deviation_symptom"] for row in items
                ),
                "top_primary_factor_category": most_common_value(
                    row["primary_factor_category"] for row in items
                ),
                "top_primary_affected_phase": most_common_value(
                    row["primary_affected_phase"] for row in items
                ),
            }
        )
    return output


def build_pivot_matrix(
    rows: list[dict],
    row_field: str,
    column_field: str,
    row_label: str,
) -> tuple[list[str], list[dict]]:
    row_values = Counter(row[row_field] for row in rows)
    column_values = Counter(row[column_field] for row in rows)
    ordered_rows = [value for value, _ in row_values.most_common()]
    ordered_columns = [value for value, _ in column_values.most_common()]
    pair_counts = Counter((row[row_field], row[column_field]) for row in rows)

    fieldnames = [row_label, *ordered_columns, "row_total"]
    output = []
    for row_value in ordered_rows:
        record = {row_label: row_value}
        row_total = 0
        for column_value in ordered_columns:
            count = pair_counts.get((row_value, column_value), 0)
            record[column_value] = count
            row_total += count
        record["row_total"] = row_total
        output.append(record)
    return fieldnames, output


def representative_score(row: dict, category: str) -> tuple:
    role_score = {
        "deviation_and_factor": 100,
        "factor_only": 60,
        "deviation_only": 20,
    }.get(row.get("evidence_role"), 0)
    symptom_quote = bool((row.get("symptom_evidence_quote") or "").strip())
    factor_quote = bool((row.get("factor_evidence_quote") or "").strip())
    phase_quote = bool((row.get("phase_evidence_quote") or "").strip())
    needed_quote = symptom_quote if category == "unknown_or_not_specified" else factor_quote
    quote_score = 40 * needed_quote + 10 * symptom_quote + 10 * factor_quote + 5 * phase_quote
    title_score = min(len(row.get("title") or ""), 120)
    comment_score = min(int(row.get("comment_count") or 0), 10)
    closed_score = 5 if row.get("state") == "closed" else 0
    # Negative candidate_id keeps ordering deterministic after score sorting.
    return (
        role_score + quote_score + title_score / 20 + comment_score + closed_score,
        row.get("updated_at") or "",
        row.get("candidate_id") or "",
    )


def choose_representatives(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["primary_factor_category"]].append(row)

    output = []
    factor_counts = Counter(row["primary_factor_category"] for row in rows)
    for category, items in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        if category == "unknown_or_not_specified":
            quote_ready = [
                row for row in items if (row.get("symptom_evidence_quote") or "").strip()
            ]
        else:
            quote_ready = [
                row for row in items if (row.get("factor_evidence_quote") or "").strip()
            ]
        pool = quote_ready or items
        chosen = sorted(
            pool,
            key=lambda row: representative_score(row, category),
            reverse=True,
        )[:3]
        for rank, row in enumerate(chosen, start=1):
            output.append(
                {
                    "factor_category": category,
                    "rq1_count": factor_counts[category],
                    "representative_rank": rank,
                    "candidate_id": row["candidate_id"],
                    "project": row["project"],
                    "repo": row["repo"],
                    "source_type": row["source_type"],
                    "number": row["number"],
                    "title": row["title"],
                    "url": row["url"],
                    "evidence_role": row["evidence_role"],
                    "primary_deviation_symptom": row["primary_deviation_symptom"],
                    "primary_affected_phase": row["primary_affected_phase"],
                    "symptom_evidence_quote": short_text(row.get("symptom_evidence_quote") or ""),
                    "factor_evidence_quote": short_text(row.get("factor_evidence_quote") or ""),
                    "phase_evidence_quote": short_text(row.get("phase_evidence_quote") or ""),
                }
            )
    return output


def build_case_mapping(rows: list[dict], reps: list[dict]) -> list[dict]:
    factor_counts = Counter(row["primary_factor_category"] for row in rows)
    rep_ids = defaultdict(list)
    for row in reps:
        rep_ids[row["factor_category"]].append(row["candidate_id"])

    output = []
    for factor, count in sorted(factor_counts.items(), key=lambda item: (-item[1], item[0])):
        operator, benchmark, family, status = FACTOR_CASE_MAPPING.get(
            factor,
            (
                "manifest.hide_factor_fields",
                "LeRobot+LIBERO; ManiSkill",
                "unknown",
                "needs_manual_mapping",
            ),
        )
        output.append(
            {
                "factor_category": factor,
                "rq1_count": count,
                "representative_candidate_ids": ";".join(rep_ids.get(factor, [])[:3]),
                "planned_evaltriage_operator": operator,
                "planned_benchmark": benchmark,
                "rq2_rq4_case_family": family,
                "coverage_status": status,
            }
        )
    return output


def write_markdown(
    rows: list[dict],
    taxonomy_counts: list[dict],
    project_breakdown: list[dict],
    reps: list[dict],
    case_mapping: list[dict],
) -> None:
    total = len(rows)
    role_counts = Counter(row["evidence_role"] for row in rows)
    symptom_counts = Counter(row["primary_deviation_symptom"] for row in rows)
    factor_counts = Counter(row["primary_factor_category"] for row in rows)
    phase_counts = Counter(row["primary_affected_phase"] for row in rows)
    unknown_count = factor_counts.get("unknown_or_not_specified", 0)
    missing_quotes = {
        "symptom_evidence_quote": sum(
            1 for row in rows if not (row.get("symptom_evidence_quote") or "").strip()
        ),
        "factor_evidence_quote": sum(
            1 for row in rows if not (row.get("factor_evidence_quote") or "").strip()
        ),
        "phase_evidence_quote": sum(
            1 for row in rows if not (row.get("phase_evidence_quote") or "").strip()
        ),
    }

    primary_taxonomy_sums = {
        taxonomy_type: sum(
            int(row["count"])
            for row in taxonomy_counts
            if row["taxonomy_type"] == taxonomy_type
        )
        for taxonomy_type in [
            "evidence_role",
            "primary_deviation_symptom",
            "primary_factor_category",
            "primary_affected_phase",
        ]
    }

    top_projects = project_breakdown[:15]
    top_pairs = Counter(
        (row["primary_deviation_symptom"], row["primary_factor_category"])
        for row in rows
    ).most_common(12)

    reps_by_factor = defaultdict(list)
    for row in reps:
        reps_by_factor[row["factor_category"]].append(row)

    input_sha256 = hashlib.sha256(INPUT_JSONL.read_bytes()).hexdigest()
    lines = [
        "# EvalTriage RQ1 Evidence Tables",
        "",
        f"输入文件 SHA256：`{input_sha256}`",
        "",
        "## 0. 当前结论",
        "",
        f"- RQ1 frozen input 为 `rq1_evidence.jsonl`，共 `{total}` 条 GitHub issue / PR evidence。",
        "- 本次整理只做确定性统计和表格生成，不重新 mining，不重新调用 LLM。",
        f"- `unknown_or_not_specified` 有 `{unknown_count}` 条，占 `{unknown_count / total * 100:.2f}%`；它不是无效样本，而是表示文本报告了 evaluation deviation，但缺少足够证据归因到具体 factor。",
        "- 本文件用于论文 RQ1 结果小节、RQ2-RQ4 fault injection 设计和 artifact 复算。",
        "",
        "## 1. Evidence Mining Pipeline",
        "",
        md_table(["Stage", "Count"], PIPELINE_COUNTS),
        "",
        "## 2. Evidence Role 分布",
        "",
        md_table(
            ["Evidence Role", "Count", "Percent"],
            [
                (role, count, f"{count / total * 100:.2f}%")
                for role, count in role_counts.most_common()
            ],
        ),
        "",
        "## 3. Primary Deviation Symptom",
        "",
        md_table(
            ["Primary Symptom", "Count", "Percent"],
            [
                (category, count, f"{count / total * 100:.2f}%")
                for category, count in symptom_counts.most_common()
            ],
        ),
        "",
        "## 4. Primary Engineering Factor",
        "",
        md_table(
            ["Primary Factor", "Count", "Percent"],
            [
                (category, count, f"{count / total * 100:.2f}%")
                for category, count in factor_counts.most_common()
            ],
        ),
        "",
        "## 5. Primary Affected Phase",
        "",
        md_table(
            ["Primary Phase", "Count", "Percent"],
            [
                (category, count, f"{count / total * 100:.2f}%")
                for category, count in phase_counts.most_common()
            ],
        ),
        "",
        "## 6. Project Coverage",
        "",
        md_table(
            [
                "Project",
                "Repo",
                "Total",
                "Deviation+Factor",
                "Deviation Only",
                "Factor Only",
                "Unknown Factor %",
            ],
            [
                (
                    row["project"],
                    row["repo"],
                    row["total_evidence"],
                    row["deviation_and_factor_count"],
                    row["deviation_only_count"],
                    row["factor_only_count"],
                    row["unknown_primary_factor_percent"] + "%",
                )
                for row in top_projects
            ],
        ),
        "",
        "## 7. Top Symptom x Factor Cells",
        "",
        md_table(
            ["Primary Symptom", "Primary Factor", "Count", "Percent"],
            [
                (symptom, factor, count, f"{count / total * 100:.2f}%")
                for (symptom, factor), count in top_pairs
            ],
        ),
        "",
        "## 8. RQ1 Factor 到 EvalTriage Case 的映射",
        "",
        md_table(
            [
                "Factor",
                "RQ1 Count",
                "Planned Operator",
                "Benchmark",
                "Case Family",
                "Coverage",
            ],
            [
                (
                    row["factor_category"],
                    row["rq1_count"],
                    row["planned_evaltriage_operator"],
                    row["planned_benchmark"],
                    row["rq2_rq4_case_family"],
                    row["coverage_status"],
                )
                for row in case_mapping
            ],
        ),
        "",
        "## 9. Representative Evidence",
        "",
    ]

    for factor, count in factor_counts.most_common():
        lines.extend([f"### {factor} (`n={count}`)", ""])
        factor_reps = reps_by_factor[factor]
        lines.append(
            md_table(
                ["Rank", "Project", "Issue / PR", "Role", "Primary Symptom", "Quote"],
                [
                    (
                        row["representative_rank"],
                        row["project"],
                        f"[{row['candidate_id']}]({row['url']})",
                        row["evidence_role"],
                        row["primary_deviation_symptom"],
                        row["factor_evidence_quote"]
                        or row["symptom_evidence_quote"]
                        or row["phase_evidence_quote"],
                    )
                    for row in factor_reps
                ],
            )
        )
        lines.append("")

    lines.extend(
        [
            "## 10. 数据质量检查",
            "",
            md_table(
                ["Check", "Value"],
                [
                    ("Total records", total),
                    ("Unique candidate_id", len({row["candidate_id"] for row in rows})),
                    ("Missing symptom_evidence_quote", missing_quotes["symptom_evidence_quote"]),
                    ("Missing factor_evidence_quote", missing_quotes["factor_evidence_quote"]),
                    ("Missing phase_evidence_quote", missing_quotes["phase_evidence_quote"]),
                    ("Primary evidence_role sum", primary_taxonomy_sums["evidence_role"]),
                    (
                        "Primary deviation symptom sum",
                        primary_taxonomy_sums["primary_deviation_symptom"],
                    ),
                    (
                        "Primary factor category sum",
                        primary_taxonomy_sums["primary_factor_category"],
                    ),
                    (
                        "Primary affected phase sum",
                        primary_taxonomy_sums["primary_affected_phase"],
                    ),
                ],
            ),
            "",
            "## 11. 输出文件",
            "",
            md_table(
                ["File", "Purpose"],
                [
                    ("tables/rq1_evidence_index.csv", "一行一个 GitHub issue / PR evidence。"),
                    ("tables/rq1_taxonomy_counts.csv", "taxonomy 计数和百分比。"),
                    ("tables/rq1_project_breakdown.csv", "项目 / repo 维度分布。"),
                    ("tables/rq1_symptom_factor_matrix.csv", "primary symptom x primary factor 交叉表。"),
                    ("tables/rq1_factor_phase_matrix.csv", "primary factor x primary affected phase 交叉表。"),
                    ("tables/rq1_representative_evidence.csv", "每个 factor 的代表性 evidence。"),
                    ("tables/rq1_case_mapping.csv", "RQ1 factor 到 EvalTriage case/operator 的映射。"),
                ],
            ),
        ]
    )

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(INPUT_JSONL)
    validate_rows(rows)

    evidence_index = build_evidence_index(rows)
    taxonomy_counts = build_taxonomy_counts(rows)
    project_breakdown = build_project_breakdown(rows)
    symptom_factor_fields, symptom_factor_matrix = build_pivot_matrix(
        rows,
        "primary_deviation_symptom",
        "primary_factor_category",
        "primary_deviation_symptom",
    )
    factor_phase_fields, factor_phase_matrix = build_pivot_matrix(
        rows,
        "primary_factor_category",
        "primary_affected_phase",
        "primary_factor_category",
    )
    representatives = choose_representatives(rows)
    case_mapping = build_case_mapping(rows, representatives)

    write_csv(TABLE_DIR / "rq1_evidence_index.csv", INDEX_FIELDS, evidence_index)
    write_csv(
        TABLE_DIR / "rq1_taxonomy_counts.csv",
        [
            "taxonomy_type",
            "category",
            "count",
            "percent_of_all",
            "percent_excluding_unknown",
            "example_candidate_ids",
        ],
        taxonomy_counts,
    )
    write_csv(
        TABLE_DIR / "rq1_project_breakdown.csv",
        [
            "project",
            "repo",
            "total_evidence",
            "issue_count",
            "pr_count",
            "open_count",
            "closed_count",
            "deviation_and_factor_count",
            "deviation_only_count",
            "factor_only_count",
            "unknown_primary_factor_count",
            "unknown_primary_factor_percent",
            "top_primary_deviation_symptom",
            "top_primary_factor_category",
            "top_primary_affected_phase",
        ],
        project_breakdown,
    )
    write_csv(
        TABLE_DIR / "rq1_symptom_factor_matrix.csv",
        symptom_factor_fields,
        symptom_factor_matrix,
    )
    write_csv(
        TABLE_DIR / "rq1_factor_phase_matrix.csv",
        factor_phase_fields,
        factor_phase_matrix,
    )
    write_csv(
        TABLE_DIR / "rq1_representative_evidence.csv",
        [
            "factor_category",
            "rq1_count",
            "representative_rank",
            "candidate_id",
            "project",
            "repo",
            "source_type",
            "number",
            "title",
            "url",
            "evidence_role",
            "primary_deviation_symptom",
            "primary_affected_phase",
            "symptom_evidence_quote",
            "factor_evidence_quote",
            "phase_evidence_quote",
        ],
        representatives,
    )
    write_csv(
        TABLE_DIR / "rq1_case_mapping.csv",
        [
            "factor_category",
            "rq1_count",
            "representative_candidate_ids",
            "planned_evaltriage_operator",
            "planned_benchmark",
            "rq2_rq4_case_family",
            "coverage_status",
        ],
        case_mapping,
    )

    write_markdown(rows, taxonomy_counts, project_breakdown, representatives, case_mapping)

    primary_sums = {
        taxonomy_type: sum(
            int(row["count"])
            for row in taxonomy_counts
            if row["taxonomy_type"] == taxonomy_type
        )
        for taxonomy_type in [
            "evidence_role",
            "primary_deviation_symptom",
            "primary_factor_category",
            "primary_affected_phase",
        ]
    }
    bad_sums = {
        taxonomy_type: value
        for taxonomy_type, value in primary_sums.items()
        if value != EXPECTED_TOTAL
    }
    if bad_sums:
        raise ValueError(f"Primary taxonomy count mismatch: {bad_sums}")

    print(f"Built RQ1 tables from {INPUT_JSONL}")
    print(f"Rows: {len(rows)}")
    print(f"Output directory: {TABLE_DIR}")
    print(f"Summary: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
