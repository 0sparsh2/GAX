"""Extended eval: ablations, comparisons, multi-MCP catalog."""

from __future__ import annotations

from typing import Any

from ablations import (
    run_gax_ablation_no_cap,
    run_gax_ablation_no_envelope,
    run_gax_ablation_schema_preload,
)
from comparisons import (
    run_cli_agent_spec,
    run_cli_logged_proxy,
    run_programmatic_mcp,
)
from mcp_catalog import probe_catalog_all, run_mcp_server_naive_row


def extended_rows_for_task(
    task: dict[str, Any],
    registry: Any,
    default_cap: str,
    cap: str,
    cli_row: dict[str, Any],
    *,
    row_fn: Any,
    gax_invoke: Any,
    gax_transcript_tokens: Any,
    schema_tokens_43: int,
    run_cli_task: Any,
    run_mcp_naive: Any,
    mcp_probes: list[dict[str, Any]],
    mock_only: bool,
) -> list[dict[str, Any]]:
    cat = task.get("category", "")
    if cat in ("discovery", "plan"):
        return []

    rows: list[dict[str, Any]] = []

    rows.append(
        run_gax_ablation_no_cap(
            task,
            registry,
            default_cap,
            row_fn=row_fn,
            gax_invoke=gax_invoke,
            gax_transcript_tokens=gax_transcript_tokens,
        )
    )
    rows.append(
        run_gax_ablation_no_envelope(
            task,
            registry,
            cap,
            row_fn=row_fn,
            gax_invoke=gax_invoke,
        )
    )
    rows.append(
        run_gax_ablation_schema_preload(
            task,
            registry,
            cap,
            row_fn=row_fn,
            gax_invoke=gax_invoke,
            gax_transcript_tokens=gax_transcript_tokens,
            schema_tokens=schema_tokens_43,
        )
    )

    has_cli = bool(task.get("cli_argv")) and not cli_row.get("skipped")
    if has_cli:
        rows.append(run_programmatic_mcp(task, cli_row, row_fn=row_fn))
        rows.append(
            run_cli_agent_spec(
                task,
                cli_row,
                row_fn=row_fn,
                run_cli_task=run_cli_task,
            )
        )
        rows.append(run_cli_logged_proxy(task, cli_row, row_fn=row_fn))

    if has_cli or task.get("mcp_bridge"):
        for probe in mcp_probes:
            rows.append(
                run_mcp_server_naive_row(
                    task,
                    cli_row,
                    probe,
                    row_fn=row_fn,
                    mcp_naive_fn=run_mcp_naive,
                )
            )

    return rows
