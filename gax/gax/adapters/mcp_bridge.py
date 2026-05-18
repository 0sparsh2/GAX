"""MCP → GAX adapter: one registered command → one MCP tool call."""

from __future__ import annotations

from typing import Any

from gax.mcp_client import McpStdioClient, github_mcp_env
from gax.registry import CommandManifest


def _mcp_cfg(manifest: CommandManifest) -> dict[str, Any]:
    return dict((manifest.raw or {}).get("mcp") or {})


def _server_cmd(cfg: dict[str, Any]) -> list[str]:
    cmd = cfg.get("server_command", "npx")
    args = list(cfg.get("server_args") or ["-y", "@modelcontextprotocol/server-github"])
    return [str(cmd), *[str(a) for a in args]]


def _map_args(manifest: CommandManifest, args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    repo = args.get("repo")
    if isinstance(repo, str) and "/" in repo:
        owner, name = repo.split("/", 1)
        out.setdefault("owner", owner)
        out.setdefault("repo", name)
    mapping = (manifest.raw or {}).get("mcp_arg_map") or {}
    if mapping:
        mapped: dict[str, Any] = {}
        for src, dst in mapping.items():
            if src in out:
                mapped[str(dst)] = out[src]
        for k, v in out.items():
            mapped.setdefault(k, v)
        out = mapped
    return out


def run(
    manifest: CommandManifest,
    args: dict[str, Any],
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    cfg = _mcp_cfg(manifest)
    tool_name = str(cfg.get("tool_name", ""))
    if not tool_name:
        raise RuntimeError(f"mcp.tool_name missing in manifest {manifest.command}")

    env = dict(cfg.get("env") or {})
    if "github" in manifest.command or "server-github" in " ".join(_server_cmd(cfg)):
        env.update(github_mcp_env())

    client = McpStdioClient(_server_cmd(cfg), env=env, timeout=float(cfg.get("timeout", 90)))
    try:
        result = client.call_tool(tool_name, _map_args(manifest, args))
    finally:
        client.close()

    if isinstance(result, dict):
        return result
    return {"result": result}
