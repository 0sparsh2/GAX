"""
`gax mcp import` — turn any MCP server into pinned GAX commands.

Registering an MCP server by hand does not scale to an ecosystem of thousands.
This connects to a server, enumerates `tools/list`, and writes one manifest per
tool with the tool's schema hash recorded as `mcp_pin`.

Two properties worth stating plainly:

**Import is a review step, not an approval.** Every imported command is written
with `side_effects: destructive` unless the tool is confidently read-only, because
we cannot know what a stranger's tool does. That means the default dev capability
(ceiling `read`) cannot invoke it. A human raises the ceiling per command after
reading what it actually does. Guessing "probably safe" here would hand agents
uninspected capability, which is the thing GAX exists to prevent.

**The pin is what makes import safe.** Without it, importing a third-party server
would just relocate the tool-poisoning problem into your registry. See `mcp_pin`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from gax.mcp_client import McpStdioClient
from gax.mcp_pin import canonical_tool, pin_tool
from gax.paths import USER_MANIFESTS_DIR

# Tool-name prefixes that are read-only with high confidence. Anything else is
# imported as destructive and must be downgraded deliberately.
# Stored without a separator; `_normalize_tool_name` strips separators before
# matching, so `get_env`, `get-env`, and `getEnv` are all recognized. Real servers
# use all three conventions — @modelcontextprotocol/server-everything advertises
# `get-env`, and matching only `get_` silently classified it destructive.
_READ_PREFIXES = (
    "get", "list", "read", "search", "find", "fetch", "query",
    "describe", "show", "view", "count", "check",
)

# Exact names that are unambiguously read-only but do not start with a read verb.
# Exact-match, not substring: `tree` is safe, `prune_tree` is not.
_READ_EXACT = frozenset({"directorytree", "tree", "stat", "ls", "pwd", "whoami"})

# Any of these anywhere in a tool name forces `destructive`, and is checked before
# the read verbs. This is the safety net for vendor-namespaced names: without it,
# `firecrawl_monitor_delete` could be classified read because some other word in
# it looked safe. Over-inclusive on purpose — a false `destructive` costs a human
# one review; a false `read` hands an agent uninspected capability.
_WRITE_WORDS = frozenset({
    "create", "update", "delete", "remove", "write", "put", "post", "patch",
    "set", "add", "insert", "upsert", "drop", "truncate", "purge", "prune",
    "destroy", "kill", "stop", "start", "restart", "run", "exec", "execute",
    "invoke", "call", "send", "publish", "deploy", "apply", "install",
    "uninstall", "move", "rename", "copy", "upload", "edit", "modify",
    "merge", "push", "commit", "revert", "reset", "scale", "toggle",
    "trigger", "interact", "crawl", "scrape", "extract", "agent",
    "replace", "clear", "flush", "archive", "restore", "rollback",
    "cancel", "approve", "reject", "close", "open", "lock", "unlock",
    "grant", "revoke", "enable", "disable", "subscribe", "unsubscribe",
})

_SEPARATORS = re.compile(r"[-_\s.]+")

_SAFE_NAME = re.compile(r"[^a-z0-9_]+")


def infer_side_effects(tool_name: str) -> str:
    """
    Conservative guess at a tool's danger level.

    Read-only only when the name says so unambiguously; everything else is
    `destructive`. Erring toward danger means an import can never silently widen
    what an existing capability may do.
    """
    words = _tool_words(tool_name)
    if not words:
        return "destructive"
    if "".join(words) in _READ_EXACT:
        return "read"

    # Any mutating verb anywhere disqualifies, checked first. `firecrawl_monitor_delete`
    # contains a read verb (`monitor` is not one, but `list` appears in siblings) and
    # must never be classified read on the strength of another word.
    if any(w in _WRITE_WORDS for w in words):
        return "destructive"

    # Vendors namespace their tools (`firecrawl_search`, `firecrawl_monitor_list`),
    # so the leading word is often the product name rather than a verb. Accept a
    # read verb anywhere, having already excluded mutating verbs above.
    if any(w in _READ_PREFIXES for w in words):
        return "read"
    return "destructive"


def _tool_words(tool_name: str) -> list[str]:
    """
    Split a tool name into lowercase words across the conventions servers use:
    `get_env`, `get-env`, and `getEnv` all yield ['get', 'env'].
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(tool_name))
    return [w for w in _SEPARATORS.split(spaced.lower()) if w]


def command_id(server_id: str, tool_name: str) -> str:
    """`mcp.<server>.<tool>` — namespaced so two servers can share a tool name."""
    server = _SAFE_NAME.sub("_", server_id.lower()).strip("_")
    tool = _SAFE_NAME.sub("_", tool_name.lower()).strip("_")
    return f"mcp.{server}.{tool}"


def build_manifest(
    *,
    server_id: str,
    server_command: str,
    server_args: list[str],
    tool: dict[str, Any],
    scope: str | None = None,
) -> dict[str, Any]:
    tool_name = str(tool.get("name", ""))
    side_effects = infer_side_effects(tool_name)
    cmd = command_id(server_id, tool_name)
    description = str(tool.get("description") or f"{tool_name} (imported from {server_id})")

    return {
        "command": cmd,
        "version": "1.0.0",
        "description": description[:300],
        "category": f"mcp/{server_id}",
        "adapter": "mcp",
        "required_scopes": [scope or f"mcp:{server_id}:use"],
        "side_effects": side_effects,
        "idempotent": side_effects == "read",
        "input_schema": tool.get("inputSchema") or {"type": "object"},
        "output_schema": {"type": "object"},
        "mcp": {
            "server_command": server_command,
            "server_args": server_args,
            "tool_name": tool_name,
        },
        # Frozen contract. Verified before every invoke; see gax/mcp_pin.py.
        "mcp_pin": pin_tool(tool),
        "mcp_pin_imported_from": server_id,
        # Exactly what was hashed. `description` above is truncated for display,
        # so diffing against it would mislabel an honest long description as
        # tampered. The pin is computed from this, so this is what a mismatch
        # must be compared against.
        "mcp_pinned_tool": canonical_tool(tool),
    }


def list_server_tools(
    server_command: str,
    server_args: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    client = McpStdioClient([server_command, *server_args], env=env, timeout=timeout)
    try:
        return client.list_tools()
    finally:
        client.close()


def import_server(
    *,
    server_id: str,
    server_command: str,
    server_args: list[str],
    env: dict[str, str] | None = None,
    target_dir: Path | None = None,
    force: bool = False,
    only: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Enumerate a server's tools and write pinned manifests.

    Existing manifests are skipped unless `force`, so re-importing never silently
    overwrites a command whose danger level a human has already reviewed and set.
    """
    tools = list_server_tools(server_command, server_args, env=env)
    if only:
        wanted = set(only)
        tools = [t for t in tools if t.get("name") in wanted]

    target = target_dir or USER_MANIFESTS_DIR
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, Any]] = []
    skipped: list[str] = []

    for tool in tools:
        if not tool.get("name"):
            continue
        manifest = build_manifest(
            server_id=server_id,
            server_command=server_command,
            server_args=server_args,
            tool=tool,
        )
        path = target / f"{manifest['command']}.yaml"
        if path.exists() and not force:
            skipped.append(manifest["command"])
            continue
        if not dry_run:
            path.write_text(yaml.safe_dump(manifest, sort_keys=False))
        written.append(
            {
                "command": manifest["command"],
                "tool": tool["name"],
                "side_effects": manifest["side_effects"],
                "pin": manifest["mcp_pin"],
            }
        )

    return {
        "server_id": server_id,
        "tool_count": len(tools),
        "written": written,
        "skipped": skipped,
        "target": str(target),
        "dry_run": dry_run,
    }


def verify_manifest_pins(
    manifests: list[dict[str, Any]],
    *,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Re-check stored pins against each server's live tools.

    Groups by server so one connection covers all of its commands.
    """
    from gax.mcp_pin import find_tool

    by_server: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for m in manifests:
        cfg = (m.get("mcp") or {})
        key = (str(cfg.get("server_command", "")), tuple(cfg.get("server_args") or []))
        by_server.setdefault(key, []).append(m)

    results: list[dict[str, Any]] = []
    for (command, args), group in by_server.items():
        try:
            tools = list_server_tools(command, list(args), env=env)
        except Exception as e:
            for m in group:
                results.append(
                    {"command": m.get("command"), "status": "unreachable", "detail": str(e)}
                )
            continue

        for m in group:
            tool_name = str((m.get("mcp") or {}).get("tool_name", ""))
            live = find_tool(tools, tool_name)
            if live is None:
                results.append(
                    {
                        "command": m.get("command"),
                        "status": "missing",
                        "detail": f"tool '{tool_name}' no longer advertised",
                    }
                )
                continue
            expected = m.get("mcp_pin")
            actual = pin_tool(live)
            if not expected:
                results.append(
                    {"command": m.get("command"), "status": "unpinned",
                     "detail": "manifest has no mcp_pin"}
                )
            elif actual == expected:
                results.append({"command": m.get("command"), "status": "ok", "detail": actual})
            else:
                results.append(
                    {
                        "command": m.get("command"),
                        "status": "mismatch",
                        "detail": f"expected {expected}, got {actual}",
                    }
                )
    return results
