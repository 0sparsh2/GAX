"""MCP → GAX adapter: one registered command → one MCP tool call."""

from __future__ import annotations

from typing import Any

from gax.mcp_client import McpStdioClient, github_mcp_env
from gax.mcp_pin import PinMismatch, find_tool, verify_pin
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
    if manifest.command in ("mcp.github.list_pulls", "mcp.github.list_pulls.mock"):
        if isinstance(raw, dict) and isinstance(raw.get("result"), list):
            raw = raw["result"]
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
    cmd_line = " ".join(_server_cmd(cfg))
    needs_github = cfg.get("require_github_token")
    if needs_github is None:
        needs_github = "server-github" in cmd_line or "@modelcontextprotocol/server-github" in cmd_line
    if needs_github:
        env.update(github_mcp_env())

    client = McpStdioClient(_server_cmd(cfg), env=env, timeout=float(cfg.get("timeout", 120)))
    try:
        _enforce_pin(manifest, client, tool_name)
        raw = client.call_tool(tool_name, _map_args(manifest, args))
        return _normalize(manifest, raw)
    finally:
        client.close()


def _enforce_pin(manifest: CommandManifest, client: McpStdioClient, tool_name: str) -> None:
    """
    Verify the live tool still matches the contract recorded at import, before
    calling it.

    Manifests written by hand predate pinning and have no `mcp_pin`; those keep
    working. Manifests produced by `gax mcp import` always carry one, and for
    those a mismatch fails closed — the tool call never happens. This is the
    difference between GAX and a proxy: a proxy forwards whatever the server now
    advertises.
    """
    expected = (manifest.raw or {}).get("mcp_pin")
    if not expected:
        return  # hand-written manifest; nothing was pinned to compare against

    live = find_tool(client.list_tools(), tool_name)
    if live is None:
        raise PinMismatch(
            tool=tool_name,
            expected=str(expected),
            actual="(tool absent)",
            changed=["tool no longer advertised by server"],
        )

    # Compare against exactly what was hashed at import. The manifest's own
    # `description` is truncated for display, so diffing against that would
    # mislabel an honest long description as tampered.
    imported = (manifest.raw or {}).get("mcp_pinned_tool")
    verify_pin(live, str(expected), expected_tool=imported)
