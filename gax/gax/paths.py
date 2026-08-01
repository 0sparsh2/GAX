from __future__ import annotations

from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent  # .../gax/gax
_REPO_ROOT = _PKG_DIR.parent  # .../gax  (repo checkout only)


def _data_dir(name: str) -> Path:
    """
    Locate a bundled data directory.

    Installed wheels carry these *inside* the package (`gax/gax/manifests`), while
    a repo checkout keeps the editable sources one level up (`gax/manifests`, next
    to `gax/gax`).

    The repo copy wins when both exist. `sync_package_data.py` leaves a build
    artifact at `gax/gax/<name>/`, and preferring it would silently shadow the
    sources — editing `config/policy.yaml` would appear to do nothing until the
    next sync. In an installed wheel there is no repo copy, so the packaged one
    is used.
    """
    repo_copy = _REPO_ROOT / name
    if repo_copy.exists() and repo_copy != _PKG_DIR / name:
        return repo_copy
    return _PKG_DIR / name


MANIFESTS_DIR = _data_dir("manifests")
SCHEMAS_DIR = _data_dir("schemas")
CONFIG_DIR = _data_dir("config")
PROFILES_DIR = _data_dir("profiles")
GAX_HOME = Path.home() / ".gax"
# User-installed commands (profiles, hand-written manifests). Loaded after the
# packaged set and wins on conflict, so upgrades never clobber local commands.
USER_MANIFESTS_DIR = GAX_HOME / "manifests"
CONFIG_PATH = GAX_HOME / "config.json"
AUDIT_PATH = GAX_HOME / "audit.jsonl"
PID_PATH = GAX_HOME / "gaxd.pid"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9477


def ensure_gax_home() -> Path:
    GAX_HOME.mkdir(parents=True, exist_ok=True)
    return GAX_HOME
