"""Probe multiple MCP servers for tools/list schema token cost."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from token_count import count_json

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent


def load_server_catalog() -> list[dict[str, Any]]:
    spec = yaml.safe_load((EVAL_DIR / "fixtures" / "mcp_servers.yaml").read_text())
    servers = []
    for s in spec.get("servers") or []:
        row = dict(s)
        cmd = list(row.get("cmd") or [])
        if cmd and cmd[0] == "python" and len(cmd) > 1:
            rel = cmd[1]
            if rel.startswith("eval/"):
                cmd[1] = str(ROOT / rel)
            row["cmd"] = cmd
        servers.append(row)
    return servers


def _server_env(server: dict[str, Any]) -> dict[str, str] | None:
    env_kind = server.get("env")
    if env_kind == "github_token":
        from gax.mcp_client import github_mcp_env

        try:
            return github_mcp_env()
        except ValueError as e:
            return {"_error": str(e)}
    return {}


def probe_server(server: dict[str, Any], *, timeout: float = 90.0) -> dict[str, Any]:
    sid = server["id"]
    if server.get("requires_token"):
        if not (
            os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        ):
            return {
                "id": sid,
                "label": server.get("label", sid),
                "ok": False,
                "skipped": True,
                "reason": "GITHUB_TOKEN required",
            }

    env = _server_env(server)
    if isinstance(env, dict) and env.get("_error"):
        return {
            "id": sid,
            "ok": False,
            "skipped": True,
            "reason": env["_error"],
        }

    from gax.mcp_client import McpStdioClient

    cmd = list(server["cmd"])
    client = McpStdioClient(cmd, env=env if env else None, timeout=timeout)
    try:
        tools = client.list_tools()
        return {
            "id": sid,
            "label": server.get("label", sid),
            "ok": True,
            "tool_count": len(tools),
            "schema_tokens": count_json(tools),
            "schema_bytes": len(
                __import__("json").dumps(tools, ensure_ascii=False).encode("utf-8")
            ),
            "bridge_gax_command": server.get("bridge_gax_command"),
            "fixture_schema_tokens": server.get("fixture_schema_tokens"),
        }
    except Exception as e:
        return {
            "id": sid,
            "label": server.get("label", sid),
            "ok": False,
            "error": str(e),
        }
    finally:
        client.close()


def probe_catalog_all(*, mock_only: bool = False) -> list[dict[str, Any]]:
    """
    Probe MCP servers in fixtures/mcp_servers.yaml.

    mock_only (CI): probe mock_* stdio servers; token servers use fixtures;
    skip live npx servers without fixtures.
    """
    results: list[dict[str, Any]] = []
    for server in load_server_catalog():
        sid = server["id"]
        if mock_only and server.get("requires_token"):
            ft = server.get("fixture_schema_tokens")
            results.append(
                {
                    "id": sid,
                    "label": server.get("label", sid),
                    "ok": bool(ft),
                    "skipped": True,
                    "reason": "mock-only: Scalekit-class fixture (no live probe)",
                    "tool_count": server.get("fixture_tool_count"),
                    "schema_tokens": ft or 0,
                    "fixture_schema_tokens": ft,
                    "bridge_gax_command": server.get("bridge_gax_command"),
                }
            )
            continue
        if mock_only and not sid.startswith("mock_"):
            results.append(
                {
                    "id": sid,
                    "label": server.get("label", sid),
                    "ok": False,
                    "skipped": True,
                    "reason": "mock-only: skip live npx MCP probe",
                    "bridge_gax_command": server.get("bridge_gax_command"),
                }
            )
            continue
        results.append(probe_server(server))
    return results


def run_mcp_server_naive_row(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    probe: dict[str, Any],
    *,
    row_fn: Any,
    mcp_naive_fn: Any,
) -> dict[str, Any]:
    """Per-server naive MCP modality: mcp_live_<server_id>."""
    sid = probe.get("id", "unknown")
    modality = f"mcp_live_{sid}"
    if not probe.get("ok"):
        return row_fn(
            task_id=task["id"],
            modality=modality,
            tokens=0,
            latency_ms=0,
            ok=False,
            skipped=True,
            notes=probe.get("reason") or str(probe.get("error", "probe failed")),
            category=task.get("category", ""),
        )
    schema = int(
        probe.get("schema_tokens")
        or probe.get("fixture_schema_tokens")
        or 0
    )
    row = mcp_naive_fn(task, cli_row, variant=sid, schema_tokens=schema)
    row["modality"] = modality
    row["notes"] = (
        f"MCP {probe.get('label', sid)}: {probe.get('tool_count')} tools, "
        f"{schema} schema tok/session"
    )
    return row
