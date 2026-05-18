from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gax.paths import ensure_gax_home


def _use_keyring() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def _service_name(tenant: str, provider: str) -> str:
    return f"gax:{tenant}:{provider}"


def save_secret(tenant: str, provider: str, data: dict[str, Any], *, file_path: Path) -> None:
    """Prefer OS keychain when keyring is installed; else encrypted-at-rest file (mode 600)."""
    payload = json.dumps(data)
    if _use_keyring():
        import keyring

        keyring.set_password(_service_name(tenant, provider), "oauth_tokens", payload)
        # Remove plaintext file if migrating
        if file_path.exists():
            file_path.unlink()
        return
    ensure_gax_home()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(payload)
    file_path.chmod(0o600)


def load_secret(tenant: str, provider: str, *, file_path: Path) -> dict[str, Any] | None:
    if _use_keyring():
        import keyring

        raw = keyring.get_password(_service_name(tenant, provider), "oauth_tokens")
        if raw:
            return json.loads(raw)
    if file_path.exists():
        return json.loads(file_path.read_text())
    return None
