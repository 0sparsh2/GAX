from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gax.registry import CommandManifest

POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.yaml"


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

    if defaults.get("deny_destructive") and manifest.side_effects == "destructive":
        raise PolicyDenied(f"destructive command blocked: {manifest.command}")

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
