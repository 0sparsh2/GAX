#!/usr/bin/env python3
"""LangGraph-style 3-turn PR triage — publishable token comparison."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAX_ROOT = ROOT / "gax"
EVAL = ROOT / "eval"
sys.path.insert(0, str(GAX_ROOT))
sys.path.insert(0, str(EVAL))
from load_env import load_repo_env  # noqa: E402
from session_transcript import Transcript, cli_turn, gax_turn, mcp_naive_turn  # noqa: E402

load_repo_env(ROOT)
from token_count import count_tokens  # noqa: E402
from gax.caps import mint_capability  # noqa: E402
from gax.executor import invoke  # noqa: E402
from gax.registry import Registry  # noqa: E402

REPO = "octocat/Hello-World"
OUT_JSON = Path(__file__).parent / "results.json"
OUT_MD = Path(__file__).parent / "RESULTS.md"
SCHEMA_43 = 44026


def _has_token() -> bool:
    return bool(
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    )


def _gh(argv: list[str]) -> tuple[bool, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        return p.returncode == 0, (p.stdout or p.stderr or "")[:8000]
    except Exception as e:
        return False, str(e)


def run_cli() -> dict:
    t = Transcript()
    steps = [
        ["gh", "pr", "list", "--repo", REPO, "--limit", "5", "--json", "number,title,state"],
        ["gh", "pr", "view", "1", "--repo", REPO, "--json", "number,title,body"],
    ]
    ok = True
    for argv in steps:
        step_ok, out = _gh(argv)
        ok = ok and step_ok
        cli_turn(t, system="PR triage agent (CLI).", command=" ".join(argv), output=out)
    cli_turn(t, system="", command="echo workflow-complete", output="workflow-complete")
    return {"modality": "cli", "tokens": t.total_tokens(), "ok": ok}


def run_mcp_naive() -> dict:
    t = Transcript()
    t.add("system", "PR triage agent (MCP).")
    for tool in ["list_pull_requests", "get_pull_request"]:
        t.add("assistant", f"tools/call {tool}")
        t.add("tool", '{"mock": true}')
    t.add("assistant", "tools/call echo")
    t.add("tool", "workflow-complete")
    return {
        "modality": "mcp_naive_43",
        "tokens": t.total_tokens() + SCHEMA_43,
        "ok": True,
        "notes": f"includes {SCHEMA_43} schema tax/session (Scalekit fixture)",
    }


def run_gax() -> dict:
    reg = Registry()
    cap = mint_capability(
        commands=["gh.pr.list", "gh.pr.view", "demo.echo"],
        scopes=["github:pull_request:read", "demo:echo"],
    )
    t = Transcript()
    turns = [
        ("gh.pr.list", {"repo": REPO, "limit": 5, "state": "open"}),
        ("gh.pr.view", {"repo": REPO, "number": 1}),
        ("demo.echo", {"message": "workflow-complete"}),
    ]
    ok = True
    for i, (cmd, args) in enumerate(turns):
        env, code = invoke(reg, command=cmd, args=args, surface="model", capability=cap)
        step_ok = code == 0 and bool(env.get("ok"))
        ok = ok and step_ok
        gax_turn(
            t,
            system="PR triage agent (GAX)." if i == 0 else "",
            doc_stub=f"gax doc {cmd}",
            command=f"gax {cmd}",
            envelope=env,
        )
    return {"modality": "gax", "tokens": t.total_tokens(), "ok": ok}


def run_gax_mcp_bridge() -> dict | None:
    if not _has_token():
        return None
    reg = Registry()
    cap = mint_capability(
        commands=["mcp.github.list_pulls"],
        scopes=["github:pull_request:read"],
    )
    env, code = invoke(
        reg,
        command="mcp.github.list_pulls",
        args={"repo": REPO, "state": "open"},
        surface="model",
        capability=cap,
    )
    t = Transcript()
    gax_turn(
        t,
        system="PR triage via MCP bridge.",
        doc_stub="gax doc mcp.github.list_pulls",
        command="gax mcp.github.list_pulls",
        envelope=env,
    )
    return {
        "modality": "gax_mcp_bridge",
        "tokens": t.total_tokens(),
        "ok": code == 0 and bool(env.get("ok")),
        "audit_id": env.get("audit_id"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-bridge", action="store_true", help="Include live MCP bridge row")
    args = parser.parse_args()

    rows = [run_cli(), run_mcp_naive(), run_gax()]
    if args.with_bridge or _has_token():
        bridge = run_gax_mcp_bridge()
        if bridge:
            rows.append(bridge)

    payload = {
        "workflow": "3-turn PR triage (+ optional MCP bridge)",
        "repo": REPO,
        "token_counter": "tiktoken cl100k_base",
        "bias_disclosure": "Self-assessment by GAX authors",
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    lines = [
        "# Case study results: 3-turn PR triage\n",
        f"Repo: `{REPO}` · Counter: tiktoken cl100k_base\n",
        "| modality | tokens | ok | notes |",
        "|---|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['modality']} | {r['tokens']} | {r['ok']} | {r.get('notes', '')} |"
        )
    lines.append(f"\nRegenerate: `python eval/case_study/run_case_study.py`\n")
    OUT_MD.write_text("\n".join(lines) + "\n")

    print(OUT_MD.read_text())
    print(f"Wrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()
