from __future__ import annotations

from typing import Any

from gax.caps import cap_allows_command, cap_allows_scopes
from gax.opa_policy import check_opa_or_yaml
from gax.policy_bundle import PolicyDenied
from gax.registry import CommandManifest

__all__ = ["PolicyDenied", "check_invoke"]


def check_invoke(
    claims: dict[str, Any],
    manifest: CommandManifest,
    args: dict[str, Any] | None = None,
) -> None:
    if not cap_allows_command(claims, manifest.command):
        raise PolicyDenied(f"capability does not allow command: {manifest.command}")
    if not cap_allows_scopes(claims, manifest.required_scopes):
        raise PolicyDenied(
            f"missing scopes: {manifest.required_scopes}; held: {claims.get('scopes')}"
        )
    check_opa_or_yaml(claims, manifest, args or {})
