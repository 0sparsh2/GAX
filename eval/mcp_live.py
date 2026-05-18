"""Live MCP probe — real tools/list size via shared gax.mcp_client + tiktoken."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gax"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from token_count import count_json  # noqa: E402
from gax.mcp_client import McpStdioClient, github_mcp_env  # noqa: E402


def default_github_server_cmd() -> list[str]:
    return ["npx", "-y", "@modelcontextprotocol/server-github"]


def probe_live_mcp() -> dict:
    try:
        github_mcp_env()
    except ValueError as e:
        return {"ok": False, "skipped": True, "reason": str(e)}

    client = McpStdioClient(default_github_server_cmd(), env=github_mcp_env(), timeout=90)
    try:
        tools = client.list_tools()
        blob = json.dumps(tools, ensure_ascii=False)
        return {
            "ok": True,
            "tool_count": len(tools),
            "schema_tokens": count_json(tools),
            "schema_bytes": len(blob.encode("utf-8")),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        client.close()
