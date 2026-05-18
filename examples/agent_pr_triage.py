#!/usr/bin/env python3
"""
Real LLM agent on GAX — operational receipts, not a scripted fake demo.

Proves:
  - dynamic discovery (gax_search → gax_doc → gax_invoke)
  - envelope execution without MCP schema dumps
  - governance (denied / scope / expiry / audit correlation)
  - multi-step PR triage with error recovery

Requires: pip install -r examples/requirements-agent.txt
           OPENAI_API_KEY or ANTHROPIC_API_KEY in repo .env
           GITHUB_TOKEN for live gh.pr.* (optional: mock fallback)

Outputs: examples/agent_runs/<run_id>/
  - governance.jsonl
  - transcript.jsonl
  - manifest.json
  - summary.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = Path(__file__).resolve().parent
GAX_ROOT = ROOT / "gax"
sys.path.insert(0, str(GAX_ROOT))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(EXAMPLES))

from load_env import load_repo_env  # noqa: E402

from agent_lib import (  # noqa: E402
    AGENT_SYSTEM_PROMPT,
    LLM_TOOL_SPECS,
    JsonlLog,
    RunReceipt,
    analyze_transcript_for_proof,
    build_user_mission,
    dispatch_tool,
    mint_agent_cap,
    run_governance_receipts,
    verify_audit_ids,
)
from gax.registry import Registry  # noqa: E402

RUNS_DIR = Path(__file__).parent / "agent_runs"
MAX_TURNS = 24


def _pick_llm() -> tuple[str, str]:
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    return "", ""


def _run_openai(
    messages: list[dict[str, Any]],
    model: str,
) -> tuple[str, list[dict[str, Any]]]:
    from openai import OpenAI

    client = OpenAI()
    tools = [{"type": "function", "function": t} for t in LLM_TOOL_SPECS]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )
    msg = resp.choices[0].message
    text = msg.content or ""
    tool_calls: list[dict[str, Any]] = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            tool_calls.append(
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                }
            )
    return text, tool_calls


def _run_anthropic(
    messages: list[dict[str, Any]],
    model: str,
) -> tuple[str, list[dict[str, Any]]]:
    import anthropic

    client = anthropic.Anthropic()
    # Convert OpenAI-style messages to Anthropic (skip system in messages)
    system = ""
    anth_msgs: list[dict[str, Any]] = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
            continue
        if m["role"] == "tool":
            anth_msgs.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", ""),
                            "content": m["content"],
                        }
                    ],
                }
            )
        elif m["role"] == "assistant" and m.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    }
                )
            anth_msgs.append({"role": "assistant", "content": blocks})
        else:
            anth_msgs.append({"role": m["role"], "content": m.get("content") or ""})

    tools = [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in LLM_TOOL_SPECS
    ]
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=anth_msgs,
        tools=tools,
        temperature=0.2,
    )
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in resp.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(
                {"id": block.id, "name": block.name, "arguments": dict(block.input)}
            )
    return "\n".join(text_parts), tool_calls


def run_agent_loop(
    registry: Registry,
    capability: str,
    receipt: RunReceipt,
    transcript: JsonlLog,
    *,
    provider: str,
    model: str,
    repo: str,
    max_turns: int = MAX_TURNS,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": build_user_mission(repo)},
    ]
    transcript.write({"type": "system", "content": AGENT_SYSTEM_PROMPT})
    transcript.write({"type": "user", "content": build_user_mission(repo)})

    llm_fn = _run_openai if provider == "openai" else _run_anthropic
    final_answer = ""
    turn = 0

    while turn < max_turns:
        turn += 1
        text, tool_calls = llm_fn(messages, model)

        if text:
            transcript.write({"type": "assistant_text", "turn": turn, "content": text})
            if "FINAL_ANSWER" in text:
                final_answer = text
                transcript.write({"type": "final_answer", "turn": turn, "content": text})
                break

        if not tool_calls:
            messages.append({"role": "assistant", "content": text or "(no tools)"})
            if text:
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue the mission using gax_search/gax_doc/gax_invoke, or reply with FINAL_ANSWER.",
                    }
                )
            continue

        # Assistant message with tool calls (OpenAI format for both paths after first turn)
        messages.append(
            {
                "role": "assistant",
                "content": text or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            name = tc["name"]
            args = tc["arguments"]
            result = dispatch_tool(registry, capability, name, args)
            aid = result.get("audit_id")
            receipt.record_audit(aid)

            transcript.write(
                {
                    "type": "tool_call",
                    "turn": turn,
                    "tool": name,
                    "arguments": args,
                    "result": result,
                    "audit_id": aid,
                }
            )

            if name == "gax_invoke":
                env = result.get("envelope") or {}
                transcript.write(
                    {
                        "type": "gax_invoke_receipt",
                        "turn": turn,
                        "command": args.get("command"),
                        "audit_id": aid,
                        "ok": env.get("ok"),
                        "error_kind": (env.get("error") or {}).get("kind")
                        if isinstance(env.get("error"), dict)
                        else None,
                        "data_keys": list((env.get("data") or {}).keys()),
                    }
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False)[:12000],
                }
            )

    correlation = verify_audit_ids(receipt.audit_ids)
    proof = analyze_transcript_for_proof(transcript.path)

    return {
        "turns": turn,
        "final_answer": final_answer[:2000] if final_answer else None,
        "audit_correlation": correlation,
        "proof_flags": proof,
        "completed": proof.get("completed") or bool(final_answer),
    }


def write_summary(
    run_dir: Path,
    receipt: RunReceipt,
    governance: dict[str, Any],
    agent: dict[str, Any] | None,
) -> None:
    proof = (agent or {}).get("proof_flags") or {}
    lines = [
        "# Agent PR triage — operational receipts",
        "",
        f"**Run ID:** `{receipt.run_id}`",
        f"**Repo:** `{receipt.repo}`",
        f"**Model:** `{receipt.model}`",
        "",
        "## Governance (deterministic, real invoke + audit)",
        "",
        f"- All scenarios passed: **{governance.get('all_pass')}**",
        f"- Audit log correlation: **{governance.get('audit_correlation', {}).get('all_correlated')}**",
        "",
        "| Scenario | Pass | audit_id |",
        "|---|:---:|---|",
    ]
    for s in governance.get("scenarios") or []:
        lines.append(
            f"| {s['scenario']} | {s['pass']} | `{s.get('audit_id', '')}` |"
        )

    lines.extend(
        [
            "",
            "## Agent loop (LLM + GAX tools only)",
            "",
        ]
    )
    if agent:
        lines.extend(
            [
                f"- Completed: **{agent.get('completed')}**",
                f"- Turns: **{agent.get('turns')}**",
                f"- Discovery before first invoke: **{proof.get('discovery_before_first_invoke')}**",
                f"- Doc before first invoke: **{proof.get('doc_before_first_invoke')}**",
                f"- Recovery after error: **{proof.get('recovery_after_error')}**",
                f"- Tool calls: search={proof.get('gax_search_count')} doc={proof.get('gax_doc_count')} invoke={proof.get('gax_invoke_count')}",
                f"- Agent audit correlation: **{agent.get('audit_correlation', {}).get('all_correlated')}**",
                "",
                "### Audit IDs (agent invokes)",
                "",
            ]
        )
        for aid in receipt.audit_ids:
            lines.append(f"- `{aid}`")
        if agent.get("final_answer"):
            lines.extend(["", "### Final answer (excerpt)", "", "```", agent["final_answer"][:1500], "```"])
    else:
        lines.append("*Agent loop skipped (no OPENAI_API_KEY / ANTHROPIC_API_KEY).*")

    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `governance.jsonl` — governance scenarios",
            "- `transcript.jsonl` — full LLM + tool trace",
            "- `manifest.json` — run metadata",
            "",
            "## Verify audit log",
            "",
            "```bash",
            "grep aud_ ~/.gax/audit.jsonl | tail -20",
            "```",
            "",
        ]
    )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    load_repo_env(ROOT)
    parser = argparse.ArgumentParser(description="Real LLM agent on GAX with operational receipts")
    parser.add_argument("--repo", default=os.environ.get("AGENT_REPO", "octocat/Hello-World"))
    parser.add_argument("--governance-only", action="store_true")
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS)
    args = parser.parse_args()
    max_turns = args.max_turns

    provider, model = _pick_llm()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    receipt = RunReceipt(run_id=run_id, run_dir=run_dir, repo=args.repo, model=f"{provider}:{model}")
    registry = Registry()

    gov_log = JsonlLog(run_dir / "governance.jsonl")
    governance = run_governance_receipts(registry, gov_log)
    for s in governance.get("scenarios") or []:
        if s.get("pass"):
            receipt.governance_passed.append(s["scenario"])
        else:
            receipt.governance_failed.append(s["scenario"])
        if s.get("audit_id"):
            receipt.record_audit(s["audit_id"])

    agent_result: dict[str, Any] | None = None
    if not args.governance_only:
        if not provider:
            print(
                "ERROR: Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env to run the LLM agent loop.",
                file=sys.stderr,
            )
            print("Governance receipts were still written.", file=sys.stderr)
        else:
            cap = mint_agent_cap()
            os.environ["GAX_CAP"] = cap
            transcript = JsonlLog(run_dir / "transcript.jsonl")
            print(f"Running agent ({provider}/{model}) on {args.repo} …")
            agent_result = run_agent_loop(
                registry,
                cap,
                receipt,
                transcript,
                provider=provider,
                model=model,
                repo=args.repo,
                max_turns=max_turns,
            )

    manifest = {
        "run_id": run_id,
        "repo": args.repo,
        "model": receipt.model,
        "governance": governance,
        "agent": agent_result,
        "audit_ids": receipt.audit_ids,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    write_summary(run_dir, receipt, governance, agent_result)

    print(f"\nWrote receipts to {run_dir}")
    print(f"  summary.md")
    print(f"  governance.jsonl")
    if not args.governance_only and provider:
        print(f"  transcript.jsonl")

    if receipt.governance_failed:
        return 1
    if agent_result and not agent_result.get("completed"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
