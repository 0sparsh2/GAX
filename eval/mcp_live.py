"""Minimal MCP stdio client: tools/list size + optional tools/call."""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def mcp_session(
    server_cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Run initialize + tools/list; return tool count and token estimate."""
    proc_env = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        server_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=proc_env,
    )
    assert proc.stdin and proc.stdout

    def send(req: dict[str, Any]) -> dict[str, Any]:
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            msg = json.loads(line)
            if msg.get("id") == req.get("id"):
                return msg
        return {"error": "timeout"}

    init = send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gax-eval", "version": "0.1"},
            },
        }
    )
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    if "error" in tools:
        return {"ok": False, "error": tools, "init": init}
    result = tools.get("result") or {}
    tool_list = result.get("tools") or []
    schema_blob = json.dumps(tool_list)
    return {
        "ok": True,
        "tool_count": len(tool_list),
        "schema_tokens_estimated": _estimate_tokens(schema_blob),
        "schema_bytes": len(schema_blob),
        "init": init.get("result", {}),
    }


def default_github_server_cmd() -> list[str]:
    return ["npx", "-y", "@modelcontextprotocol/server-github"]


def probe_live_mcp() -> dict[str, Any]:
    if not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "Set GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN for live MCP",
        }
    env = {}
    tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = tok
    try:
        return mcp_session(default_github_server_cmd(), env=env, timeout=45.0)
    except Exception as e:
        return {"ok": False, "error": str(e)}
