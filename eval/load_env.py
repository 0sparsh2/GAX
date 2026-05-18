"""Load repo-root .env into os.environ (does not override existing vars)."""

from __future__ import annotations

import os
from pathlib import Path


def load_repo_env(root: Path | None = None) -> bool:
    root = root or Path(__file__).resolve().parents[1]
    path = root / ".env"
    if not path.is_file():
        return False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
    return True
