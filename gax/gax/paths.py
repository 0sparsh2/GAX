from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = _PKG_ROOT / "manifests"
SCHEMAS_DIR = _PKG_ROOT / "schemas"
GAX_HOME = Path.home() / ".gax"
CONFIG_PATH = GAX_HOME / "config.json"
AUDIT_PATH = GAX_HOME / "audit.jsonl"
PID_PATH = GAX_HOME / "gaxd.pid"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9477


def ensure_gax_home() -> Path:
    GAX_HOME.mkdir(parents=True, exist_ok=True)
    return GAX_HOME
