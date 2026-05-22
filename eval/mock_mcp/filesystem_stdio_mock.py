#!/usr/bin/env python3
"""Minimal filesystem-like MCP stdio server for CI (no network)."""

from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file (mock)",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "write_file",
        "description": "Write a file (mock)",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        },
    },
    {
        "name": "list_directory",
        "description": "List directory (mock)",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
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
                    "serverInfo": {"name": "mock-fs-mcp", "version": "0.1"},
                },
            }
        )
        return
    if method == "tools/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        return
    if method == "tools/call":
        _send(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": "mock ok"}]},
            }
        )
        return
    _send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": method or "unknown"}})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            _handle(json.loads(line))
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    main()
