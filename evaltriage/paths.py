"""Path helpers with EvalTriage output-root safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path("/home/ubuntu/zjx/EvalTriage")
LEROBOT_ROOT = Path("/home/ubuntu/zjx/lerobot")
DATA_ROOT = Path("/data/project/zjx")
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "runs" / "evaltriage"
DEFAULT_POLICY_PATH = DATA_ROOT / "checkpoints" / "lerobot" / "pi0_libero_finetuned_v044"
LIBERO_CONFIG_PATH = DATA_ROOT / "assets" / "libero" / "config"
MANISKILL_ASSET_DIR = DATA_ROOT / "assets" / "maniskill"
RQ1_ROOT = PROJECT_ROOT / "RQ1"


class PathSafetyError(ValueError):
    """Raised when a path would write outside the approved EvalTriage root."""


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_within_output_root(path: str | Path, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    resolved = resolve_path(path)
    root = resolve_path(output_root)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError(f"path {resolved} is outside output root {root}") from exc
    return resolved


def ensure_output_root(path: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    resolved = resolve_path(path)
    canonical = resolve_path(DEFAULT_OUTPUT_ROOT)
    try:
        resolved.relative_to(canonical)
    except ValueError as exc:
        raise PathSafetyError(f"output root {resolved} must be inside {canonical}") from exc
    return resolved


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    manifest: Path
    episodes: Path
    summary: Path
    logs: Path
    failure: Path
    raw_output_dir: Path


@dataclass(frozen=True)
class CasePaths:
    case_dir: Path
    case_json: Path
    deviation: Path
    manifest_diff: Path
    replay_plan: Path
    diagnosis: Path
    baselines: Path
    cost: Path


def run_paths(run_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> RunPaths:
    root = ensure_output_root(output_root)
    run_dir = ensure_within_output_root(root / "runs" / run_id, root)
    return RunPaths(
        run_dir=run_dir,
        manifest=run_dir / "manifest.json",
        episodes=run_dir / "episodes.jsonl",
        summary=run_dir / "summary.json",
        logs=run_dir / "logs.txt",
        failure=run_dir / "failure.json",
        raw_output_dir=run_dir / "raw",
    )


def case_paths(case_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> CasePaths:
    root = ensure_output_root(output_root)
    case_dir = ensure_within_output_root(root / "cases" / case_id, root)
    return CasePaths(
        case_dir=case_dir,
        case_json=case_dir / "case.json",
        deviation=case_dir / "deviation.json",
        manifest_diff=case_dir / "manifest_diff.json",
        replay_plan=case_dir / "replay_plan.json",
        diagnosis=case_dir / "diagnosis.json",
        baselines=case_dir / "baselines.json",
        cost=case_dir / "cost.json",
    )


def metrics_dir(timestamp: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    root = ensure_output_root(output_root)
    return ensure_within_output_root(root / "metrics" / timestamp, root)


def artifact_dir(timestamp: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    root = ensure_output_root(output_root)
    return ensure_within_output_root(root / "artifact" / timestamp, root)


def rq1_evidence_index_path() -> Path:
    return RQ1_ROOT / "tables" / "rq1_evidence_index.csv"


def rq1_case_mapping_path() -> Path:
    return RQ1_ROOT / "tables" / "rq1_case_mapping.csv"
