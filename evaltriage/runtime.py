"""Runtime capture helpers."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .paths import LEROBOT_ROOT, PROJECT_ROOT
from .schemas import CodeManifest, RuntimeEnvManifest


def _run(cmd: list[str], cwd: Path | None = None) -> str | None:
    try:
        return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def git_commit(path: Path) -> str | None:
    return _run(["git", "rev-parse", "HEAD"], cwd=path)


def git_dirty(path: Path) -> bool:
    out = _run(["git", "status", "--porcelain"], cwd=path)
    return bool(out)


def capture_code_manifest() -> CodeManifest:
    return CodeManifest(
        evaltriage_commit=git_commit(PROJECT_ROOT),
        lerobot_commit=git_commit(LEROBOT_ROOT),
        dirty=git_dirty(PROJECT_ROOT) or git_dirty(LEROBOT_ROOT),
    )


def _module_version(name: str) -> str | None:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", None) or getattr(mod, "version", None)
    except Exception:
        return None


def _torch_info() -> tuple[str | None, str | None, str | None, str | None]:
    try:
        import torch

        torch_v = torch.__version__
        cuda_v = torch.version.cuda
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        max_mem = None
        return torch_v, cuda_v, gpu, max_mem
    except Exception:
        return None, None, None, None


def capture_runtime_env() -> RuntimeEnvManifest:
    torch_v, cuda_v, gpu, _ = _torch_info()
    driver = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], None)
    if driver and "\n" in driver:
        driver = driver.splitlines()[0]
    return RuntimeEnvManifest(
        conda_env=os.environ.get("CONDA_DEFAULT_ENV"),
        python=sys.version.split()[0],
        torch=torch_v,
        cuda=cuda_v,
        gpu=gpu,
        driver=driver,
        mujoco=_module_version("mujoco"),
        robosuite=_module_version("robosuite"),
        mani_skill=_module_version("mani_skill"),
        os=f"{platform.system()} {platform.release()}",
    )


def max_gpu_mem_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return float(torch.cuda.max_memory_allocated(0) / (1024 * 1024))
    except Exception:
        return None
    return None


def base_env(cuda_visible_devices: str = "0") -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("HF_HOME", "/data/project/zjx/cache/huggingface")
    env.setdefault("HF_HUB_CACHE", "/data/project/zjx/cache/huggingface/hub")
    env.setdefault("HUGGINGFACE_HUB_CACHE", "/data/project/zjx/cache/huggingface/hub")
    env.setdefault("HF_XET_CACHE", "/data/project/zjx/cache/huggingface/xet")
    env.setdefault("HF_ASSETS_CACHE", "/data/project/zjx/cache/huggingface/assets")
    env.setdefault("TORCH_HOME", "/data/project/zjx/cache/torch")
    env.setdefault("XDG_CACHE_HOME", "/data/project/zjx/cache")
    env.setdefault("PIP_CACHE_DIR", "/data/project/zjx/cache/pip")
    env.setdefault("MS_ASSET_DIR", "/data/project/zjx/assets/maniskill")
    env.setdefault("LIBERO_CONFIG_PATH", "/data/project/zjx/assets/libero/config")
    env.setdefault("MUJOCO_GL", "egl")
    env["CUDA_VISIBLE_DEVICES"] = os.environ.get("EVALTRIAGE_CUDA_VISIBLE_DEVICES", cuda_visible_devices)
    return env


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None
