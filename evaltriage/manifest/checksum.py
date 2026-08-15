"""Checksum helpers for manifest collection."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(paths: list[Path]) -> str | None:
    h = hashlib.sha256()
    found = False
    for path in sorted(paths):
        digest = sha256_file(path)
        if digest:
            found = True
            h.update(str(path.name).encode())
            h.update(digest.encode())
    return h.hexdigest() if found else None
