"""
gax-mcp — expose GAX as an MCP server (stdio JSON-RPC).

Any MCP client (Claude Code, Cursor, OpenAI Agent SDK) gets governed shell
execution with zero GAX-specific integration:

    claude mcp add gax -- gax-mcp

**Why three tools and not one per command.** A naive MCP server publishes one tool
per capability, so a 43-command registry costs ~44k tokens of schema before the
first turn. GAX publishes exactly three — `gax_search`, `gax_doc`, `gax_invoke` —
and keeps the registry behind them. That is the same shape as Anthropic's Tool
Search / `defer_loading` pattern, so this composes with the platform fix rather
than competing with it: the client's own tool-search sees a constant-size surface
no matter how many commands are registered.

**The governance boundary is unchanged.** `gax_invoke` calls the same
`gax.executor.invoke` as the CLI and the daemon, so capability checks, scope
checks, and policy all run *before* any adapter, and every invoke emits an
`audit_id`. An MCP client cannot reach a command that is not in the registry, and
cannot bypass the capability check by phrasing the request differently — the model
only ever proposes a command name plus args.

Transport is stdio JSON-RPC 2.0 written against the stdlib, mirroring
`gax.mcp_client`, so adding an MCP server adds no dependency.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from gax.executor import invoke
from gax.registry import Registry

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "gax"
SERVER_VERSION = "0.4"

# Below this, a reranker's distribution is spread across several commands.
LOW_CONFIDENCE = 0.5

# JSON-RPC 2.0 reserved codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

TOOLS: list[dict[str, Any]] = [
    {
        "name": "gax_search",
        "description": (
            "Search registered GAX commands by keyword. Use this first to find a "
            "command; it returns names and one-line descriptions only, not full "
            "schemas. Only commands returned here can be invoked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords, e.g. 'pull requests' or 'pods'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "gax_doc",
        "description": (
            "Get arguments, required scopes, and side effects for one GAX command. "
            "Call this after gax_search and before gax_invoke."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command id, e.g. 'gh.pr.list'.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "gax_invoke",
        "description": (
            "Invoke a registered GAX command. The request is checked against the "
            "capability token, required scopes, and policy BEFORE any backend runs; "
            "denials return ok=false with an error.kind. Every call returns an "
            "audit_id. Unregistered commands cannot be invoked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command id, e.g. 'gh.pr.list'.",
                },
                "args": {
                    "type": "object",
                    "description": "Arguments per gax_doc.",
                },
                "surface": {
                    "type": "string",
                    "enum": ["model", "human", "full"],
                    "description": "Projection; 'model' truncates for the LLM.",
                },
            },
            "required": ["command"],
        },
    },
]


class GaxMcpServer:
    """MCP protocol surface over the GAX registry and executor."""

    def __init__(
        self,
        registry: Registry | None = None,
        *,
        capability: str | None = None,
    ) -> None:
        self._registry = registry or Registry()
        # Read GAX_CAP lazily at call time if not injected, so a capability minted
        # after the server starts is still picked up.
        self._capability = capability

    # -- tool implementations ---------------------------------------------

    def _cap(self) -> str | None:
        return self._capability or os.environ.get("GAX_CAP") or None

    def tool_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        limit = int(args.get("limit") or 5)
        result = self._registry.search_scored(query, limit=limit)
        out: dict[str, Any] = {
            "query": query,
            "results": [
                {
                    "command": h.manifest.command,
                    "description": h.manifest.description,
                    "category": h.manifest.category,
                }
                for h in result.hits
            ],
        }
        # Only rerankers with a calibrated distribution report confidence. Below
        # the threshold the query was genuinely ambiguous — asking the user is
        # cheaper than invoking the wrong command and recovering.
        if result.confidence is not None:
            out["confidence"] = round(result.confidence, 3)
            if result.confidence < LOW_CONFIDENCE:
                out["hint"] = (
                    "Low confidence: several commands fit. Ask the user which "
                    "they mean, or call gax_doc on the top candidates."
                )
        if result.no_match:
            # The reranker judged, confidently, that nothing registered does this.
            # Say so plainly: rephrasing will not help, and guessing a command
            # would be worse than telling the user.
            out["hint"] = (
                "No registered command does this. Tell the user it is not "
                "available rather than trying other commands."
            )
        elif not result.hits:
            out["hint"] = "No match. Rephrase with the resource and action, e.g. 'delete pod'."
        return out

    def tool_doc(self, args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", ""))
        doc = self._registry.doc_stub(command)
        if not doc:
            return {
                "error": "not_found",
                "message": f"unknown command: {command}",
                "hint": "use gax_search to list registered commands",
            }
        return doc

    def tool_invoke(self, args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", ""))
        call_args = dict(args.get("args") or {})
        surface = str(args.get("surface") or "model")
        envelope, _exit_code = invoke(
            self._registry,
            command=command,
            args=call_args,
            surface=surface,
            capability=self._cap(),
        )
        return envelope

    def call_tool(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Return (payload, is_error). is_error drives MCP's isError flag."""
        if name == "gax_search":
            return self.tool_search(args), False
        if name == "gax_doc":
            result = self.tool_doc(args)
            return result, bool(result.get("error"))
        if name == "gax_invoke":
            envelope = self.tool_invoke(args)
            # A policy denial is a legitimate protocol-level result, but flagging it
            # as isError makes clients surface it instead of treating it as data.
            return envelope, not bool(envelope.get("ok"))
        raise ValueError(f"unknown tool: {name}")

    # -- JSON-RPC dispatch -------------------------------------------------

    def handle(self, req: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one request. Returns None for notifications (no id)."""
        method = req.get("method")
        rid = req.get("id")
        params = req.get("params") or {}

        # Notifications carry no id and must never get a response.
        if rid is None:
            return None

        if method == "initialize":
            return _result(
                rid,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )

        if method == "tools/list":
            return _result(rid, {"tools": TOOLS})

        if method == "tools/call":
            name = str(params.get("name", ""))
            args = dict(params.get("arguments") or {})
            try:
                payload, is_error = self.call_tool(name, args)
            except ValueError as e:
                return _error(rid, METHOD_NOT_FOUND, str(e))
            except Exception as e:  # adapter blew up — report, don't crash the server
                return _result(
                    rid,
                    {
                        "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                        "isError": True,
                    },
                )
            return _result(
                rid,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
                    ],
                    "isError": is_error,
                },
            )

        if method == "ping":
            return _result(rid, {})

        return _error(rid, METHOD_NOT_FOUND, f"unknown method: {method}")


def _result(rid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def serve(
    stdin: Any = None,
    stdout: Any = None,
    *,
    registry: Registry | None = None,
) -> None:
    """Run the stdio loop until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = GaxMcpServer(registry=registry)

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _write(stdout, _error(None, PARSE_ERROR, "invalid JSON"))
            continue
        if not isinstance(req, dict):
            _write(stdout, _error(None, INVALID_REQUEST, "request must be an object"))
            continue
        try:
            resp = server.handle(req)
        except Exception as e:  # never let one bad request kill the session
            _write(stdout, _error(req.get("id"), INTERNAL_ERROR, str(e)))
            continue
        if resp is not None:
            _write(stdout, resp)


def _write(stream: Any, msg: dict[str, Any]) -> None:
    stream.write(json.dumps(msg, ensure_ascii=False) + "\n")
    stream.flush()


def main() -> None:
    """Console entry point: `gax-mcp`."""
    serve()


if __name__ == "__main__":
    main()
