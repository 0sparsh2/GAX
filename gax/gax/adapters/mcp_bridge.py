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
        out["owner"] = owner
        out["repo"] = name
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


def _normalize_list_pulls(raw: Any) -> dict[str, Any]:
    """Map GitHub MCP list_pull_requests output to gh.pr.list envelope shape."""
    rows: list[Any]
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        if "items" in raw and isinstance(raw["items"], list):
            rows = raw["items"]
        elif "pull_requests" in raw:
            rows = raw["pull_requests"]
        else:
            rows = [raw]
    else:
        rows = []

    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        user = row.get("user") or row.get("author") or {}
        login = user.get("login") if isinstance(user, dict) else str(user or "unknown")
        items.append(
            {
                "number": row.get("number") or row.get("pull_number"),
                "title": row.get("title", ""),
                "state": str(row.get("state", "OPEN")).upper(),
                "url": row.get("html_url") or row.get("url", ""),
                "author": login,
                "draft": bool(row.get("draft") or row.get("isDraft")),
            }
        )
    return {"items": items}


def _normalize(manifest: CommandManifest, raw: Any) -> dict[str, Any]:
    if manifest.command == "mcp.github.list_pulls":
        return _normalize_list_pulls(raw)
    if isinstance(raw, dict):
        return raw
    return {"result": raw}


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

    client = McpStdioClient(_server_cmd(cfg), env=env, timeout=float(cfg.get("timeout", 120)))
    try:
        raw = client.call_tool(tool_name, _map_args(manifest, args))
        return _normalize(manifest, raw)
    finally:
        client.close()
