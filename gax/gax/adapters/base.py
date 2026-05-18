from __future__ import annotations

from typing import Any

from gax.adapters import exec_adapter, http_adapter, mock_adapter, mcp_bridge
from gax.registry import CommandManifest


def run_adapter(
    manifest: CommandManifest,
    args: dict[str, Any],
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if manifest.adapter == "exec":
        return exec_adapter.run(manifest, args, tenant_id=tenant_id)
    if manifest.adapter == "mock":
        return mock_adapter.run(manifest, args)
    if manifest.adapter == "mcp":
        return mcp_bridge.run(manifest, args, tenant_id=tenant_id)
    if manifest.adapter == "http":
        return http_adapter.run(manifest, args, tenant_id=tenant_id)
    raise RuntimeError(f"unknown adapter: {manifest.adapter}")
