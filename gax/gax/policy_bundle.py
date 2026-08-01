from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gax.paths import CONFIG_DIR
from gax.registry import CommandManifest

POLICY_PATH = CONFIG_DIR / "policy.yaml"


class PolicyDenied(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def load_policy(path: Path | None = None) -> dict[str, Any]:
    p = path or POLICY_PATH
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def check_policy_bundle(
    claims: dict[str, Any],
    manifest: CommandManifest,
    args: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
) -> None:
    policy = policy or load_policy()
    defaults = policy.get("defaults") or {}
    tenant_id = str(claims.get("tenant_id", "default"))
    tenant_rules = (policy.get("tenants") or {}).get(tenant_id) or (policy.get("tenants") or {}).get(
        "default", {}
    )

    # Tenant-level kill switch for destructive commands. The per-capability ceiling
    # (gax.side_effects) is the primary control; this is the blunt org-wide override
    # for tenants that must never run destructive commands regardless of who asks.
    # Tenant setting wins over the global default so a tenant can opt in explicitly.
    deny_destructive = tenant_rules.get(
        "deny_destructive", defaults.get("deny_destructive")
    )
    if deny_destructive and manifest.side_effects == "destructive":
        raise PolicyDenied(
            f"destructive commands disabled for tenant '{tenant_id}': {manifest.command}"
        )

    denied = set(tenant_rules.get("denied_commands") or [])
    if manifest.command in denied:
        raise PolicyDenied(f"command denied by policy: {manifest.command}")

    allowed = tenant_rules.get("allowed_commands")
    if allowed and manifest.command not in allowed and "*" not in allowed:
        raise PolicyDenied(f"command not in tenant allowlist: {manifest.command}")

    allowlist = tenant_rules.get("repo_allowlist") or []
    repo = args.get("repo")
    if allowlist and repo and repo not in allowlist:
        raise PolicyDenied(f"repo not in allowlist: {repo}")
