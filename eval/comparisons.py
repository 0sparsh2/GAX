"""Comparison modalities: programmatic MCP, CLI Agent Spec, gh + logging proxy."""

from __future__ import annotations

import json
from typing import Any

from session_transcript import (
    Transcript,
    cli_agent_spec_turn,
    cli_logged_turn,
    programmatic_mcp_turn,
)

PROGRAMMATIC_MCP_SCHEMA_TOKENS = 1000  # Cloudflare Code Mode–class overhead (fixture)
CLI_AGENT_SPEC_REF = "https://github.com/cli-agent-spec/cli-agent-spec"


def run_programmatic_mcp(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    *,
    row_fn: Any,
) -> dict[str, Any]:
    """Anthropic / Code Mode pattern: code + minimal tool surface, not full tools/list."""
    if not task.get("cli_argv"):
        return row_fn(
            task_id=task["id"],
            modality="programmatic_mcp",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            notes="no CLI equivalent",
            category=task.get("category", ""),
        )

    cmd = " ".join(task["cli_argv"])
    out_preview = "ok" if cli_row.get("ok") else (cli_row.get("error_kind") or "error")
    code = (
        f"const result = await mcp.execute('github', {json.dumps({'argv': task['cli_argv']})});\n"
        f"return result;"
    )
    t = Transcript()
    tokens = programmatic_mcp_turn(
        t,
        system="You run MCP tools via code execution (search/execute only).",
        code_snippet=code,
        tool_output=str(out_preview),
        schema_tokens=PROGRAMMATIC_MCP_SCHEMA_TOKENS,
    )
    return row_fn(
        task_id=task["id"],
        modality="programmatic_mcp",
        tokens=tokens,
        latency_ms=float(cli_row["latency_ms"]) * 1.05,
        ok=bool(cli_row.get("ok")),
        notes=f"optimized MCP / code mode (~{PROGRAMMATIC_MCP_SCHEMA_TOKENS} tok overhead); ref Cloudflare/Anthropic",
        category=task.get("category", ""),
    )


def run_cli_agent_spec(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    *,
    row_fn: Any,
    run_cli_task: Any,
) -> dict[str, Any]:
    """Structured CLI result shape (CLI Agent Spec–style), not GAX envelope."""
    if not task.get("cli_argv"):
        return row_fn(
            task_id=task["id"],
            modality="cli_agent_spec",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            category=task.get("category", ""),
        )

    import subprocess
    import time

    argv = list(task["cli_argv"])
    start = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        ok = exit_code == 0
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = str(e)
        ok = False
    latency = (time.perf_counter() - start) * 1000

    t = Transcript()
    cli_agent_spec_turn(
        t,
        system="You run CLI commands; results use cli-agent-result/v1.",
        command=" ".join(argv),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )
    return row_fn(
        task_id=task["id"],
        modality="cli_agent_spec",
        tokens=t.total_tokens(),
        latency_ms=latency,
        ok=ok,
        notes=f"structured CLI wrapper ({CLI_AGENT_SPEC_REF})",
        category=task.get("category", ""),
    )


def run_cli_logged_proxy(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    *,
    row_fn: Any,
) -> dict[str, Any]:
    """gh + post-hoc audit log line — no pre-invoke policy/cap enforcement."""
    if not task.get("cli_argv"):
        return row_fn(
            task_id=task["id"],
            modality="cli_logged_proxy",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            category=task.get("category", ""),
        )

    import subprocess
    import time

    argv = list(task["cli_argv"])
    start = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        ok = proc.returncode == 0
        out = (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        ok = False
        out = str(e)
    latency = (time.perf_counter() - start) * 1000

    t = Transcript()
    cli_logged_turn(
        t,
        system="You may run shell; a proxy logs commands after execution.",
        command=" ".join(argv),
        output=out,
        audit_id="proxy_aud_posthoc",
    )
    return row_fn(
        task_id=task["id"],
        modality="cli_logged_proxy",
        tokens=t.total_tokens(),
        latency_ms=latency,
        ok=ok,
        notes="gh + logging proxy (post-hoc audit line, no cap/policy gate)",
        category=task.get("category", ""),
    )
