#!/usr/bin/env python3
"""Compare CLI vs simulated MCP vs GAX on token estimate, latency, governance, structure."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
GAX_ROOT = ROOT / "gax"
sys.path.insert(0, str(GAX_ROOT))

from gax.caps import mint_capability  # noqa: E402
from gax.executor import invoke  # noqa: E402
from gax.registry import Registry  # noqa: E402

OUT_DIR = Path(__file__).parent / "results"
FIXTURES = Path(__file__).parent / "fixtures" / "mcp_schema_tokens.json"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def score_row(row: dict[str, Any]) -> float:
    """Higher is better. Weights favor governance + structure + tokens + reliability."""
    w = {"tokens": 0.30, "reliability": 0.25, "governance": 0.25, "structure": 0.20}
    token_score = max(0.0, 1.0 - row["tokens_estimated"] / 50_000)
    return (
        w["tokens"] * token_score
        + w["reliability"] * row["reliability_score"]
        + w["governance"] * row["governance_score"]
        + w["structure"] * row["structure_score"]
    )


def run_cli(task: dict[str, Any]) -> dict[str, Any]:
    argv = task.get("cli_argv") or []
    if not argv:
        return {
            "modality": "cli",
            "ok": True,
            "latency_ms": 0,
            "tokens_estimated": 50,
            "output_preview": "n/a",
            "governance_score": 0.1,
            "structure_score": 0.3,
            "reliability_score": 1.0,
            "notes": "no cli equivalent",
        }
    start = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        ok = proc.returncode == 0
        out = proc.stdout or proc.stderr
    except Exception as e:
        ok = False
        out = str(e)
    latency = (time.perf_counter() - start) * 1000
    cmd_str = " ".join(argv)
    tokens = estimate_tokens(cmd_str) + estimate_tokens(out[:4000])
    return {
        "modality": "cli",
        "ok": ok,
        "latency_ms": round(latency, 2),
        "tokens_estimated": tokens,
        "output_preview": out[:200],
        "governance_score": 0.2,
        "structure_score": 0.5 if out.strip().startswith("[") or out.strip().startswith("{") else 0.3,
        "reliability_score": 1.0 if ok else 0.0,
        "notes": "ambient credentials; no audit_id",
    }


def run_mcp_live(task: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    """Use measured tools/list from live MCP server when probe succeeded."""
    if not probe.get("ok"):
        row = run_mcp_sim(task, "43")
        row["modality"] = "mcp_live_skipped"
        row["notes"] = probe.get("reason") or probe.get("error") or "live MCP unavailable"
        return row
    schema_tokens = int(probe["schema_tokens_estimated"])
    cli = run_cli(task)
    tokens = schema_tokens + cli["tokens_estimated"]
    return {
        "modality": "mcp_live",
        "ok": cli["ok"],
        "latency_ms": cli["latency_ms"] * 1.2,
        "tokens_estimated": tokens,
        "output_preview": cli["output_preview"],
        "governance_score": 0.75,
        "structure_score": 0.9,
        "reliability_score": 1.0 if cli["ok"] else 0.0,
        "notes": f"live tools/list: {probe['tool_count']} tools, ~{schema_tokens} schema tokens",
    }


def run_mcp_sim(task: dict[str, Any], variant: str = "43") -> dict[str, Any]:
    fixtures = json.loads(FIXTURES.read_text())
    key = "github_copilot_mcp_43_tools" if variant == "43" else "github_mcp_server_93_tools"
    schema_tokens = fixtures[key]["estimated_schema_tokens_per_session"]
    if variant == "93":
        schema_tokens = fixtures[key]["estimated_schema_tokens_idle"]

    # Backend work same as CLI; cost is schema + response in context
    cli = run_cli(task)
    tokens = schema_tokens + cli["tokens_estimated"]
    # Scalekit: 28% infra failure on remote MCP — model as reliability penalty
    reliability = 0.72
    return {
        "modality": f"mcp_naive_{variant}",
        "ok": cli["ok"],
        "latency_ms": cli["latency_ms"] * 1.15,
        "tokens_estimated": tokens,
        "output_preview": cli["output_preview"],
        "governance_score": 0.7,
        "structure_score": 0.85,
        "reliability_score": reliability,
        "notes": f"schema overhead {schema_tokens} tokens ({fixtures[key]['tool_count']} tools)",
    }


def run_gax(task: dict[str, Any], registry: Registry, cap: str) -> dict[str, Any]:
    doc_tokens = 100  # gax doc/search stub
    start = time.perf_counter()
    env, code = invoke(
        registry,
        command=task["gax_command"],
        args=dict(task.get("gax_args") or {}),
        surface="model",
        capability=cap,
    )
    latency = (time.perf_counter() - start) * 1000
    body = json.dumps(env)
    tokens = doc_tokens + estimate_tokens(body)
    has_audit = bool(env.get("audit_id"))
    structured = env.get("v") == 1 and "data" in env
    return {
        "modality": "gax",
        "ok": code == 0 and env.get("ok"),
        "latency_ms": round(latency, 2),
        "tokens_estimated": tokens,
        "output_preview": body[:200],
        "governance_score": 0.95 if has_audit else 0.5,
        "structure_score": 1.0 if structured else 0.4,
        "reliability_score": 1.0 if code == 0 else 0.0,
        "audit_id": env.get("audit_id"),
        "notes": "cap + policy + envelope v1 + projection",
    }


def run_gax_plan(registry: Registry, cap: str, repo: str) -> dict[str, Any]:
    from gax.plan import run_plan

    plan = {
        "name": "eval-plan",
        "steps": [
            {
                "parallel": [
                    {
                        "id": "echo",
                        "command": "demo.echo",
                        "args": {"message": "parallel-a"},
                    },
                    {
                        "id": "list",
                        "command": "gh.pr.list",
                        "args": {"repo": repo, "limit": 3},
                    },
                ]
            }
        ],
    }
    start = time.perf_counter()
    env, code = run_plan(registry, plan, capability=cap, surface="model")
    latency = (time.perf_counter() - start) * 1000
    body = json.dumps(env)
    return {
        "modality": "gax_plan",
        "ok": code == 0,
        "latency_ms": round(latency, 2),
        "tokens_estimated": 150 + estimate_tokens(body),
        "governance_score": 0.95,
        "structure_score": 1.0,
        "reliability_score": 1.0 if code == 0 else 0.0,
        "notes": "multi-step + parallel in one envelope",
    }


def run_gax_mcp_bridge(task: dict[str, Any], registry: Registry, cap: str) -> dict[str, Any]:
    """GAX command backed by MCP adapter (governance + no schema in agent prompt)."""
    if task["id"] != "pr_list":
        return {
            "modality": "gax_mcp_bridge",
            "ok": True,
            "latency_ms": 0,
            "tokens_estimated": 120,
            "governance_score": 0.95,
            "structure_score": 1.0,
            "reliability_score": 1.0,
            "composite_score": 0.0,
            "notes": "mcp bridge only wired for pr_list task",
        }
    import os

    if not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        return {
            "modality": "gax_mcp_bridge",
            "ok": False,
            "skipped": True,
            "latency_ms": 0,
            "tokens_estimated": 200,
            "governance_score": 0.95,
            "structure_score": 1.0,
            "reliability_score": 0.0,
            "composite_score": 0.0,
            "notes": "GITHUB_TOKEN required",
        }
    start = time.perf_counter()
    env, code = invoke(
        registry,
        command="mcp.github.list_pulls",
        args=dict(task.get("gax_args") or {}),
        surface="model",
        capability=cap,
    )
    latency = (time.perf_counter() - start) * 1000
    body = json.dumps(env)
    return {
        "modality": "gax_mcp_bridge",
        "ok": code == 0 and env.get("ok"),
        "latency_ms": round(latency, 2),
        "tokens_estimated": 120 + estimate_tokens(body),
        "governance_score": 0.95,
        "structure_score": 1.0,
        "reliability_score": 1.0 if code == 0 else 0.0,
        "audit_id": env.get("audit_id"),
        "notes": "GAX envelope over MCP adapter",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI vs MCP vs GAX evaluation")
    parser.add_argument(
        "--live-mcp",
        action="store_true",
        help="Probe @modelcontextprotocol/server-github tools/list (needs GITHUB_TOKEN)",
    )
    args = parser.parse_args()

    tasks_path = Path(__file__).parent / "tasks.yaml"
    spec = yaml.safe_load(tasks_path.read_text())
    registry = Registry()
    cap = mint_capability(
        commands=["demo.echo", "gh.pr.list", "gh.pr.view", "mcp.github.list_pulls"],
        scopes=["demo:echo", "github:pull_request:read"],
    )

    mcp_probe: dict[str, Any] = {}
    if args.live_mcp:
        from mcp_live import probe_live_mcp

        mcp_probe = probe_live_mcp()
        print("Live MCP probe:", json.dumps(mcp_probe, indent=2)[:500])

    rows: list[dict[str, Any]] = []
    for task in spec["tasks"]:
        tid = task["id"]
        rows.append({"task_id": tid, **run_cli(task)})
        rows.append({"task_id": tid, **run_mcp_sim(task, "43")})
        if args.live_mcp:
            rows.append({"task_id": tid, **run_mcp_live(task, mcp_probe)})
        rows.append({"task_id": tid, **run_gax(task, registry, cap)})
        if tid == "pr_list":
            rows.append({"task_id": tid, **run_gax_mcp_bridge(task, registry, cap)})

    rows.append(
        {
            "task_id": "parallel_plan",
            **run_gax_plan(registry, cap, spec["repo"]),
        }
    )

    for r in rows:
        r["composite_score"] = round(score_row(r), 4)

    by_mod: dict[str, list[float]] = {}
    for r in rows:
        by_mod.setdefault(r["modality"], []).append(r["composite_score"])
    summary = {
        m: round(sum(v) / len(v), 4) for m, v in by_mod.items()
    }
    winner = max(summary.items(), key=lambda x: x[1])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "tasks": spec["name"],
        "live_mcp_probe": mcp_probe if args.live_mcp else None,
        "rows": rows,
        "summary_mean_composite": summary,
        "winner": winner[0],
    }
    (OUT_DIR / "comparison.json").write_text(json.dumps(out, indent=2))

    md = [
        "# Evaluation: CLI vs MCP (simulated) vs GAX",
        "",
        f"**Mean composite score** (higher is better):",
        "",
    ]
    for m, s in sorted(summary.items(), key=lambda x: -x[1]):
        md.append(f"- **{m}**: {s}")
    md.append(f"\n**Leader:** {winner[0]} ({winner[1]})")
    md.append("\n## Scoring weights\n")
    md.append("- Tokens 30% | Reliability 25% | Governance 25% | Structure 20%\n")
    md.append("## Per-run\n| task | modality | ok | tokens | latency_ms | composite |\n")
    md.append("|---|---|---|---:|---:|---:|\n")
    for r in rows:
        md.append(
            f"| {r['task_id']} | {r['modality']} | {r['ok']} | {r['tokens_estimated']} | "
            f"{r['latency_ms']} | {r['composite_score']} |\n"
        )
    (OUT_DIR / "comparison.md").write_text("".join(md))
    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUT_DIR / 'comparison.json'} and comparison.md")


if __name__ == "__main__":
    # Allow `python eval/run_comparison.py` from repo root
    sys.path.insert(0, str(Path(__file__).parent))
    main()
