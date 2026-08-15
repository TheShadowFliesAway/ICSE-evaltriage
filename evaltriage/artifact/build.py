"""Build ICSE artifact directories from existing EvalTriage outputs."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _copytree_if_exists(src: Path | None, dst: Path) -> None:
    if src is None:
        return
    if not src.exists():
        raise RuntimeError(f"artifact input not found: {src}")
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_artifact(
    output_dir: str | Path,
    sample_runs_root: str | Path | None = None,
    sample_cases_root: str | Path | None = None,
    precomputed_metrics_dir: str | Path | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _copytree_if_exists(Path(sample_runs_root) if sample_runs_root else None, out / "sample_runs")
    _copytree_if_exists(Path(sample_cases_root) if sample_cases_root else None, out / "sample_cases")
    _copytree_if_exists(Path(precomputed_metrics_dir) if precomputed_metrics_dir else None, out / "precomputed_metrics")
    (out / "README.md").write_text(
        "# EvalTriage Artifact\n\n"
        "This artifact is generated from existing EvalTriage run/case/metrics outputs.\n"
        "Full GPU benchmark reruns are not required for table reproduction.\n"
    )
    (out / "environment.md").write_text(
        "# Environment\n\nSee `EvalTriage_resource_inventory.md` in the project root for the frozen resource inventory.\n"
    )
    scripts = out / "scripts"
    scripts.mkdir(exist_ok=True)
    (out / "reproduce_tables.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nrm -rf reproduced_metrics\ncp -r precomputed_metrics reproduced_metrics\n"
    )
    (scripts / "run_smoke.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "TS=$(date +%Y%m%d_%H%M%S)\n"
        "evaltriage-run \\\n"
        "  --platform lerobot_libero \\\n"
        "  --run-id smoke_lerobot_libero_${TS} \\\n"
        "  --role smoke \\\n"
        "  --suite libero_goal \\\n"
        "  --task-ids 0 \\\n"
        "  --seed 1000 \\\n"
        "  --episodes 1 \\\n"
        "  --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044\n"
        "evaltriage-run \\\n"
        "  --platform maniskill \\\n"
        "  --run-id smoke_maniskill_pickcube_${TS} \\\n"
        "  --role smoke \\\n"
        "  --suite PickCube-v1 \\\n"
        "  --task-ids 0 \\\n"
        "  --seed 1000 \\\n"
        "  --episodes 1 \\\n"
        "  --control-policy random \\\n"
        "  --obs-mode state\n"
    )
    os.chmod(out / "reproduce_tables.sh", 0o755)
    os.chmod(scripts / "run_smoke.sh", 0o755)
    return out
