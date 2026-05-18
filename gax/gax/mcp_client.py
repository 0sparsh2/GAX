"""MCP JSON-RPC over stdio — shared by gaxd MCP adapter and eval."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any


class McpStdioClient:
    def __init__(
        self,
        server_cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._timeout = timeout
        self._id = 0
        self._lock = threading.Lock()
        proc_env = {**os.environ, **(env or {})}
        self._proc = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=proc_env,
        )
        assert self._proc.stdin and self._proc.stdout
        self._initialize()

    def _next_id(self) -> int:
        with self._lock:
            self._id += 1
            return self._id

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        rid = self._next_id()
        req: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            req["params"] = params
        assert self._proc.stdin
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            line = self._proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                break
            msg = json.loads(line)
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(json.dumps(msg["error"]))
                return msg.get("result") or {}
        raise TimeoutError(f"MCP request timed out: {method}")

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gax", "version": "0.4"},
            },
        )
        assert self._proc.stdin
        self._proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self._proc.stdin.flush()

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        return list(result.get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content") or []
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except json.JSONDecodeError:
                return {"text": texts[0]}
        return {"content": content}

    def close(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()


def github_mcp_env() -> dict[str, str]:
    tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise ValueError("GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN required for MCP GitHub server")
    return {"GITHUB_PERSONAL_ACCESS_TOKEN": tok}
