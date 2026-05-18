#!/usr/bin/env python3
"""Minimal GitHub-like MCP stdio server for CI (no network, no token)."""

from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "list_pull_requests",
        "description": "List pull requests (mock)",
        "inputSchema": {
            "type": "object",
            "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        },
    }
]

MOCK_PRS = [
    {
        "number": 1,
        "title": "Mock PR",
        "state": "open",
        "html_url": "https://github.com/octocat/Hello-World/pull/1",
        "user": {"login": "mock-user"},
        "draft": False,
    }
]


def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _handle(req: dict) -> None:
    rid = req.get("id")
    method = req.get("method")
    if rid is None:
        return
    if method == "initialize":
        _send(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "mock-github-mcp", "version": "0.1"},
                },
            }
        )
        return
    if method == "tools/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        return
    if method == "tools/call":
        name = (req.get("params") or {}).get("name")
        if name == "list_pull_requests":
            body = json.dumps(MOCK_PRS)
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"content": [{"type": "text", "text": body}]},
                }
            )
            return
        _send(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": f"unknown tool: {name}"},
            }
        )
        return
    _send(
        {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"unknown method: {method}"},
        }
    )


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("method") == "notifications/initialized":
            continue
        if "method" in msg:
            _handle(msg)


if __name__ == "__main__":
    main()
