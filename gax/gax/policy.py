from __future__ import annotations

from typing import Any

from gax.caps import cap_allows_command, cap_allows_scopes
from gax.opa_policy import check_opa_or_yaml
from gax.policy_bundle import PolicyDenied
from gax.registry import CommandManifest
from gax.side_effects import capability_ceiling, exceeds_ceiling, normalize

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
    # Danger ceiling. Deliberately checked even when the command is on the
    # capability's allowlist: an allowlist edit should not be able to silently
    # promote a read-only token into one that can delete things.
    if exceeds_ceiling(claims, manifest.side_effects):
        raise PolicyDenied(
            f"side_effects '{normalize(manifest.side_effects)}' exceeds capability "
            f"ceiling '{capability_ceiling(claims)}': {manifest.command}"
        )
    check_opa_or_yaml(claims, manifest, args or {})
