#!/usr/bin/env python3
"""
Compare CLI vs naive MCP (schema tax) vs GAX on real tiktoken counts.

No team-chosen weighted composite. See eval/METHODOLOGY.md and eval/scoring.py.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
GAX_ROOT = ROOT / "gax"
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(GAX_ROOT))
sys.path.insert(0, str(EVAL_DIR))

from load_env import load_repo_env  # noqa: E402
from scoring import aggregate_by_modality, pareto_summary, primary_metrics  # noqa: E402
from session_transcript import (  # noqa: E402
    Transcript,
    cli_turn,
    gax_turn,
    mcp_naive_turn,
)
from token_count import count_json, count_tokens  # noqa: E402
from gax.caps import mint_capability  # noqa: E402
from gax.executor import invoke  # noqa: E402
from gax.plan import load_plan, run_plan  # noqa: E402
from gax.registry import Registry  # noqa: E402

OUT_DIR = EVAL_DIR / "results"
FIXTURES = EVAL_DIR / "fixtures" / "mcp_schema_tokens.json"
DOC_STUB_TOKENS = 120
SEARCH_STUB_TOKENS = 95


def _has_github_token() -> bool:
    return bool(
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    )


def _schema_tokens(variant: str = "43") -> int:
    fixtures = json.loads(FIXTURES.read_text())
    key = (
        "github_copilot_mcp_43_tools"
        if variant == "43"
        else "github_mcp_server_93_tools"
    )
    row = fixtures[key]
    if variant == "93":
        return int(row["estimated_schema_tokens_idle"])
    return int(row["estimated_schema_tokens_per_session"])


def _default_cap(commands: list[str] | None = None) -> str:
    cmds = commands or [
        "demo.echo",
        "gh.pr.list",
        "gh.pr.view",
        "mcp.github.list_pulls",
        "kubectl.get.pods",
        "aws.s3.list",
        "jira.issue.get",
    ]
    return mint_capability(
        commands=cmds,
        scopes=[
            "demo:echo",
            "github:pull_request:read",
            "k8s:pods:read",
            "aws:s3:read",
            "jira:issue:read",
        ],
    )


def _row(
    *,
    task_id: str,
    modality: str,
    tokens: int,
    latency_ms: float,
    ok: bool,
    skipped: bool = False,
    audit_id: str | None = None,
    structured_envelope: bool = False,
    error_kind: str | None = None,
    notes: str = "",
    category: str = "",
    raw_output_chars: int | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "category": category,
        "modality": modality,
        "tokens": tokens,
        "latency_ms": round(latency_ms, 2),
        "ok": ok,
        "skipped": skipped,
        "audit_id": audit_id,
        "structured_envelope": structured_envelope,
        "error_kind": error_kind,
        "notes": notes,
        "raw_output_chars": raw_output_chars,
    }


def _gax_invoke(
    registry: Registry,
    cap: str,
    command: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any], int, float]:
    start = time.perf_counter()
    env, code = invoke(
        registry,
        command=command,
        args=args,
        surface="model",
        capability=cap,
    )
    latency = (time.perf_counter() - start) * 1000
    return env, code, latency


def _gax_transcript_tokens(
    command: str,
    env: dict[str, Any],
    *,
    doc_tokens: int = DOC_STUB_TOKENS,
) -> int:
    t = Transcript()
    gax_turn(
        t,
        system="You invoke registered GAX commands only.",
        doc_stub=f"gax doc {command} (~{doc_tokens} tok)",
        command=f"gax {command}",
        envelope=env,
    )
    return t.total_tokens()


def run_cli_task(task: dict[str, Any], argv: list[str] | None = None) -> dict[str, Any]:
    tid = task["id"]
    argv = argv if argv is not None else list(task.get("cli_argv") or [])
    if not argv:
        return _row(
            task_id=tid,
            modality="cli",
            tokens=count_tokens("n/a"),
            latency_ms=0,
            ok=True,
            notes="no cli equivalent",
            category=task.get("category", ""),
        )

    start = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        ok = proc.returncode == 0
        out = (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        ok = False
        out = str(e)
    latency = (time.perf_counter() - start) * 1000

    cap = int(task.get("transcript_cap_chars") or 8000)
    t = Transcript()
    cli_turn(
        t,
        system="You may run shell commands.",
        command=" ".join(argv),
        output=out[:cap],
    )
    return _row(
        task_id=tid,
        modality="cli",
        tokens=t.total_tokens(),
        latency_ms=latency,
        ok=ok,
        notes="ambient credentials; no audit_id",
        category=task.get("category", ""),
        raw_output_chars=len(out),
    )


def run_mcp_naive(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    *,
    variant: str = "43",
    schema_tokens: int | None = None,
) -> dict[str, Any]:
    schema = schema_tokens if schema_tokens is not None else _schema_tokens(variant)
    cmd = " ".join(task.get("cli_argv") or ["<no-cli>"])
    out_preview = "error" if not cli_row.get("ok") else "ok"
    t = Transcript()
    mcp_naive_turn(
        t,
        system="You have MCP tools.",
        schema_blob=f"[tools/list {variant} tools — see schema_tokens in results]",
        tool_call=cmd,
        output=out_preview,
    )
    # Published schema tax (Scalekit ~44k/session) — not the label string above
    total_tokens = t.total_tokens() + schema
    return _row(
        task_id=task["id"],
        modality=f"mcp_naive_{variant}",
        tokens=total_tokens,
        latency_ms=float(cli_row["latency_ms"]) * 1.12,
        ok=bool(cli_row.get("ok")),
        notes=f"schema tax {schema} tok/session (Scalekit fixture)",
        category=task.get("category", ""),
    )


def run_mcp_live_row(
    task: dict[str, Any],
    cli_row: dict[str, Any],
    probe: dict[str, Any],
) -> dict[str, Any]:
    if not probe.get("ok"):
        return _row(
            task_id=task["id"],
            modality="mcp_live",
            tokens=0,
            latency_ms=0,
            ok=False,
            skipped=True,
            notes=probe.get("reason") or str(probe.get("error", "live MCP unavailable")),
            category=task.get("category", ""),
        )
    schema = int(probe.get("schema_tokens") or probe.get("schema_tokens_estimated") or 0)
    return run_mcp_naive(task, cli_row, variant="live", schema_tokens=schema)


def run_gax_task(
    task: dict[str, Any],
    registry: Registry,
    cap: str,
    *,
    command: str | None = None,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cmd = command or task["gax_command"]
    argz = args if args is not None else dict(task.get("gax_args") or {})
    if task.get("repeat_message"):
        base = str(argz.get("message", ""))
        argz = {**argz, "message": base * int(task["repeat_message"])}

    env, code, latency = _gax_invoke(registry, cap, cmd, argz)
    ok = code == 0 and bool(env.get("ok"))
    err = (env.get("error") or {}) if isinstance(env.get("error"), dict) else {}
    return _row(
        task_id=task["id"],
        modality="gax",
        tokens=_gax_transcript_tokens(cmd, env),
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=env.get("v") == 1 and "data" in env,
        error_kind=err.get("kind") if not ok else None,
        notes="cap + policy + envelope v1",
        category=task.get("category", ""),
        raw_output_chars=len(json.dumps(env)),
    )


def run_gax_mcp_bridge_task(
    task: dict[str, Any],
    registry: Registry,
    cap: str,
) -> dict[str, Any]:
    if not task.get("mcp_bridge") and task.get("gax_command") != "mcp.github.list_pulls":
        return _row(
            task_id=task["id"],
            modality="gax_mcp_bridge",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            notes="mcp bridge not applicable",
            category=task.get("category", ""),
        )
    if not _has_github_token():
        return _row(
            task_id=task["id"],
            modality="gax_mcp_bridge",
            tokens=DOC_STUB_TOKENS,
            latency_ms=0,
            ok=False,
            skipped=True,
            notes="Set GITHUB_TOKEN for live MCP bridge",
            category=task.get("category", ""),
        )

    cmd = task.get("gax_command") or "mcp.github.list_pulls"
    args = dict(task.get("gax_args") or {})
    env, code, latency = _gax_invoke(registry, cap, cmd, args)
    ok = code == 0 and bool(env.get("ok"))
    err = (env.get("error") or {}) if isinstance(env.get("error"), dict) else {}
    return _row(
        task_id=task["id"],
        modality="gax_mcp_bridge",
        tokens=_gax_transcript_tokens(cmd, env),
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=env.get("v") == 1 and "data" in env,
        error_kind=err.get("kind") if not ok else None,
        notes="GAX envelope over MCP adapter (no schema in agent prompt)",
        category=task.get("category", ""),
    )


def run_discovery_task(task: dict[str, Any]) -> dict[str, Any]:
    if task.get("discovery_mode") == "search":
        text = f"gax search '{task.get('discovery_query', '')}' → 1 hit (~{SEARCH_STUB_TOKENS} tok)"
        tokens = count_tokens("You discover GAX commands lazily.") + count_tokens(text)
    else:
        cmd = task.get("discovery_command", "gh.pr.list")
        text = f"gax doc {cmd} — parameters, scopes, example (~{DOC_STUB_TOKENS} tok)"
        tokens = count_tokens("You discover GAX commands lazily.") + count_tokens(text)
    return _row(
        task_id=task["id"],
        modality="gax",
        tokens=tokens,
        latency_ms=0.5,
        ok=True,
        structured_envelope=False,
        notes="discovery only — no invoke",
        category=task.get("category", ""),
    )


def run_multi_turn(
    task: dict[str, Any],
    registry: Registry,
    cap: str,
    *,
    modality_prefix: str,
    run_fn,
) -> dict[str, Any]:
    """run_fn(command, args) -> (output_str, ok)"""
    t = Transcript()
    schema_added = False
    start = time.perf_counter()
    all_ok = True

    schema_tax = _schema_tokens("43")
    if modality_prefix.startswith("mcp"):
        t.add("system", "You have MCP tools.")
        schema_added = True

    turns = task.get("turns") or []
    cli_turns = task.get("cli_turns") or []

    for i, turn in enumerate(turns):
        cmd = turn["gax_command"]
        args = dict(turn.get("gax_args") or {})
        if modality_prefix == "gax":
            env, code, _ = _gax_invoke(registry, cap, cmd, args)
            ok = code == 0 and bool(env.get("ok"))
            gax_turn(
                t,
                system="You invoke registered GAX commands only." if i == 0 else "",
                doc_stub=f"gax doc {cmd}",
                command=f"gax {cmd}",
                envelope=env,
            )
            all_ok = all_ok and ok
        elif modality_prefix == "cli" and i < len(cli_turns):
            argv = cli_turns[i]
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
            ok = proc.returncode == 0
            out = (proc.stdout or "") + (proc.stderr or "")
            if i == 0:
                t.add("system", "You may run shell commands.")
            t.add("assistant", " ".join(argv))
            t.add("tool", out[:8000])
            all_ok = all_ok and ok
        elif modality_prefix.startswith("mcp"):
            argv = cli_turns[i] if i < len(cli_turns) else []
            out = "ok" if argv else ""
            if argv:
                proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
                out = (proc.stdout or proc.stderr or "")[:8000]
                all_ok = all_ok and proc.returncode == 0
            t.add("assistant", f"tools/call {argv[0] if argv else cmd}")
            t.add("tool", out)
            if not schema_added:
                schema_added = True

    latency = (time.perf_counter() - start) * 1000
    mod = modality_prefix if not modality_prefix.startswith("mcp") else "mcp_naive_43"
    tok = t.total_tokens()
    if mod == "mcp_naive_43":
        tok += schema_tax
    return _row(
        task_id=task["id"],
        modality=mod if mod != "gax" else "gax",
        tokens=tok,
        latency_ms=latency,
        ok=all_ok,
        notes=f"multi-turn ({len(turns)} steps)",
        category=task.get("category", ""),
    )


def run_plan_task(
    task: dict[str, Any],
    registry: Registry,
    cap: str,
) -> dict[str, Any]:
    plan_path = ROOT / str(task["plan_file"])
    plan = load_plan(str(plan_path))
    start = time.perf_counter()
    env, code = run_plan(registry, plan, capability=cap, surface="model")
    latency = (time.perf_counter() - start) * 1000
    ok = code == 0 and bool(env.get("ok"))
    err = (env.get("error") or {}) if isinstance(env.get("error"), dict) else {}
    t = Transcript()
    gax_turn(
        t,
        system="You run GAX plans.",
        doc_stub=f"gax plan run {plan.get('name', 'plan')}",
        command=f"gax plan run {plan_path.name}",
        envelope=env,
    )
    return _row(
        task_id=task["id"],
        modality="gax_plan",
        tokens=t.total_tokens(),
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=env.get("v") == 1,
        error_kind=err.get("kind") if not ok else None,
        notes="sequential/parallel plan",
        category=task.get("category", ""),
    )


def _apply_expected_outcome(task: dict[str, Any], row: dict[str, Any]) -> None:
    """Mark success when failure was the intended outcome (error-category tasks)."""
    expect = task.get("expect_ok") or {}
    mod = row["modality"]
    key = mod
    if mod.startswith("mcp_naive"):
        key = "mcp" if "mcp" in expect else mod
    if mod == "gax" or mod == "gax_plan":
        key = "gax"
    if mod == "cli":
        key = "cli"
    if key not in expect and mod not in expect:
        if mod.startswith("mcp_naive") and "cli" in expect:
            key = "cli"
        else:
            return
    wanted = expect.get(key, expect.get(mod))
    if wanted is None:
        return
    got_ok = bool(row.get("ok"))
    if wanted == got_ok:
        row["ok"] = True
        row["expected_outcome"] = True
    elif not wanted and not got_ok:
        ek = task.get("expect_error_kind")
        if ek and row.get("error_kind") == ek:
            row["ok"] = True
            row["expected_outcome"] = True


def process_task(
    task: dict[str, Any],
    registry: Registry,
    default_cap: str,
    *,
    live_mcp_probe: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    tid = task["id"]
    cat = task.get("category", "")
    cap = (
        mint_capability(commands=list(task["cap_commands"]), scopes=["demo:echo"])
        if task.get("cap_commands")
        else default_cap
    )
    rows: list[dict[str, Any]] = []

    if cat == "discovery":
        rows.append(run_discovery_task(task))
        return rows

    if cat == "multi_turn":
        rows.append(run_multi_turn(task, registry, cap, modality_prefix="gax", run_fn=None))
        rows.append(run_multi_turn(task, registry, cap, modality_prefix="cli", run_fn=None))
        rows.append(run_multi_turn(task, registry, cap, modality_prefix="mcp_naive_43", run_fn=None))
        return rows

    if cat == "plan":
        rows.append(run_plan_task(task, registry, cap))
        return rows

    if task.get("gax_only"):
        rows.append(run_gax_task(task, registry, cap))
        return rows

    cli_row = run_cli_task(task)
    if not task.get("cli_argv") and cat != "error":
        cli_row["skipped"] = True

    rows.append(cli_row)
    rows.append(run_mcp_naive(task, cli_row))
    if live_mcp_probe is not None:
        rows.append(run_mcp_live_row(task, cli_row, live_mcp_probe))

    gax_cmd = str(task.get("gax_command", ""))
    if not gax_cmd.startswith("mcp."):
        rows.append(run_gax_task(task, registry, cap))

    if task.get("mcp_bridge") or gax_cmd.startswith("mcp."):
        rows.append(run_gax_mcp_bridge_task(task, registry, cap))

    return rows


def main() -> None:
    load_repo_env(ROOT)
    parser = argparse.ArgumentParser(description="CLI vs MCP vs GAX evaluation (v2)")
    parser.add_argument(
        "--live-mcp",
        action="store_true",
        help="Probe live @modelcontextprotocol/server-github tools/list (needs GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--mock-only",
        action="store_true",
        help="Skip modalities that require GITHUB_TOKEN / live MCP",
    )
    args = parser.parse_args()

    spec = yaml.safe_load((EVAL_DIR / "tasks.yaml").read_text())
    registry = Registry()
    default_cap = _default_cap()

    mcp_probe: dict[str, Any] | None = None
    if args.live_mcp and not args.mock_only:
        from mcp_live import probe_live_mcp

        mcp_probe = probe_live_mcp()
        print("Live MCP probe:", json.dumps(mcp_probe, indent=2)[:600])

    all_rows: list[dict[str, Any]] = []
    for task in spec["tasks"]:
        if args.mock_only and task.get("requires_token"):
            continue
        for raw in process_task(
            task, registry, default_cap, live_mcp_probe=mcp_probe
        ):
            _apply_expected_outcome(task, raw)
            metrics = primary_metrics(raw)
            all_rows.append({**raw, **metrics})

    primary = [primary_metrics(r) for r in all_rows]
    agg = aggregate_by_modality(primary)
    pareto = pareto_summary(agg)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    enc = _encoding_name()
    out = {
        "suite": spec["name"],
        "task_count": len(spec["tasks"]),
        "token_counter": enc,
        "bias_disclosure": "Self-assessment by GAX authors; see eval/METHODOLOGY.md",
        "live_mcp_probe": mcp_probe,
        "rows": all_rows,
        "aggregate_by_modality": agg,
        "pareto_winners_per_axis": pareto,
    }
    (OUT_DIR / "comparison.json").write_text(json.dumps(out, indent=2))

    md = [
        "# Evaluation: CLI vs naive MCP vs GAX (v2)\n",
        f"**Tasks:** {len(spec['tasks'])} · **Token counter:** `{enc}`\n",
        "**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).\n",
        "\n## Aggregate by modality\n",
        "| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |\n",
        "|---|---:|---:|---:|---:|---:|\n",
    ]
    for mod, a in sorted(agg.items()):
        md.append(
            f"| {mod} | {a['n']} | {a['success_rate']} | {a['median_tokens']} | "
            f"{a['audit_id_rate']} | {a['structured_envelope_rate']} |\n"
        )
    md.append("\n## Pareto winners (per axis, ties allowed)\n")
    for axis, winners in pareto.items():
        md.append(f"- **{axis}**: {', '.join(winners)}\n")
    md.append("\n## Per-run sample\n| task | category | modality | ok | tokens | latency_ms |\n")
    md.append("|---|---|---|---:|---:|---:|\n")
    for r in all_rows[:40]:
        md.append(
            f"| {r['task_id']} | {r.get('category','')} | {r['modality']} | {r.get('success', r['ok'])} | "
            f"{r['tokens']} | {r['latency_ms']} |\n"
        )
    if len(all_rows) > 40:
        md.append(f"\n*…and {len(all_rows) - 40} more rows in comparison.json*\n")
    (OUT_DIR / "comparison.md").write_text("".join(md))

    print(json.dumps(agg, indent=2))
    print(f"Wrote {OUT_DIR / 'comparison.json'} and comparison.md")


def _encoding_name() -> str:
    try:
        import tiktoken  # noqa: F401

        return "tiktoken cl100k_base"
    except ImportError:
        return "char/4 fallback (pip install tiktoken)"


if __name__ == "__main__":
    main()
