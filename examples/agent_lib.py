"""Shared GAX agent runtime: tools, governance receipts, audit correlation."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gax.audit import log_event  # noqa: F401 — ensure audit module loadable
from gax.caps import mint_capability
from gax.executor import invoke
from gax.paths import AUDIT_PATH
from gax.registry import Registry

ToolFn = Callable[..., dict[str, Any]]


@dataclass
class RunReceipt:
    run_id: str
    run_dir: Path
    repo: str
    model: str
    audit_ids: list[str] = field(default_factory=list)
    governance_passed: list[str] = field(default_factory=list)
    governance_failed: list[str] = field(default_factory=list)

    def record_audit(self, audit_id: str | None) -> None:
        if audit_id and audit_id not in self.audit_ids:
            self.audit_ids.append(audit_id)


class JsonlLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with self.path.open("a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def gax_search(registry: Registry, query: str) -> dict[str, Any]:
    hits = registry.search(query, limit=8)
    return {
        "query": query,
        "results": [
            {"command": m.command, "description": m.description, "category": m.category}
            for m in hits
        ],
    }


def gax_doc(registry: Registry, command: str) -> dict[str, Any]:
    doc = registry.doc_stub(command)
    if not doc:
        return {"ok": False, "error": "command_not_found", "command": command}
    return {"ok": True, "doc": doc}


def gax_invoke(
    registry: Registry,
    capability: str,
    command: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env, code = invoke(
        registry,
        command=command,
        args=args or {},
        surface="model",
        capability=capability,
    )
    return {
        "exit_code": code,
        "envelope": env,
        "audit_id": env.get("audit_id"),
        "ok": bool(env.get("ok")),
        "error_kind": (env.get("error") or {}).get("kind") if isinstance(env.get("error"), dict) else None,
    }


def verify_audit_ids(audit_ids: list[str]) -> dict[str, Any]:
    """Correlate receipt audit_ids with ~/.gax/audit.jsonl lines."""
    found: dict[str, dict[str, Any]] = {}
    missing = list(audit_ids)
    if AUDIT_PATH.exists():
        for line in AUDIT_PATH.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            aid = row.get("audit_id")
            if aid in missing:
                found[aid] = row
                missing.remove(aid)
    return {"found": found, "missing": missing, "all_correlated": len(missing) == 0}


def run_governance_receipts(registry: Registry, log: JsonlLog) -> dict[str, Any]:
    """
    Deterministic governance proofs (real invoke + audit, no LLM).
    """
    results: list[dict[str, Any]] = []

    # 1) Policy denied — command not on cap
    cap_denied = mint_capability(commands=["demo.echo"], scopes=["demo:echo"], ttl_seconds=300)
    r = gax_invoke(registry, cap_denied, "gh.pr.list", {"repo": "octocat/Hello-World", "limit": 2})
    results.append(
        {
            "scenario": "policy_denied_command",
            "expected": "policy_denied",
            "pass": r["error_kind"] == "policy_denied" and not r["ok"],
            "audit_id": r["audit_id"],
            "envelope_ok": r["ok"],
        }
    )
    log.write({"type": "governance", **results[-1], "invoke": r})

    # 2) Scope mismatch — command allowed but scopes insufficient
    cap_scope = mint_capability(
        commands=["gh.pr.list"],
        scopes=["demo:echo"],
        ttl_seconds=300,
    )
    r = gax_invoke(registry, cap_scope, "gh.pr.list", {"repo": "octocat/Hello-World", "limit": 2})
    results.append(
        {
            "scenario": "scope_mismatch",
            "expected": "policy_denied",
            "pass": r["error_kind"] == "policy_denied" and not r["ok"],
            "audit_id": r["audit_id"],
        }
    )
    log.write({"type": "governance", **results[-1], "invoke": r})

    # 3) Expired capability
    cap_exp = mint_capability(
        commands=["demo.echo"],
        scopes=["demo:echo"],
        ttl_seconds=1,
    )
    time.sleep(2)
    r = gax_invoke(registry, cap_exp, "demo.echo", {"message": "after-expiry"})
    results.append(
        {
            "scenario": "expired_cap",
            "expected": "capability_invalid",
            "pass": r["error_kind"] == "capability_invalid" and not r["ok"],
            "audit_id": r["audit_id"],
        }
    )
    log.write({"type": "governance", **results[-1], "invoke": r})

    # 4) Successful invoke — audit correlation baseline
    cap_ok = mint_capability(
        commands=["demo.echo", "gh.pr.list", "gh.pr.view"],
        scopes=["demo:echo", "github:pull_request:read"],
        ttl_seconds=3600,
    )
    r = gax_invoke(registry, cap_ok, "demo.echo", {"message": "governance-baseline-ok"})
    results.append(
        {
            "scenario": "allowed_invoke",
            "expected": "ok",
            "pass": r["ok"] and r["audit_id"] is not None,
            "audit_id": r["audit_id"],
        }
    )
    log.write({"type": "governance", **results[-1], "invoke": r})

    audit_ids = [x["audit_id"] for x in results if x.get("audit_id")]
    correlation = verify_audit_ids([a for a in audit_ids if a])

    summary = {
        "scenarios": results,
        "all_pass": all(x["pass"] for x in results),
        "audit_correlation": correlation,
    }
    log.write({"type": "governance_summary", **summary})
    return summary


def mint_agent_cap() -> str:
    return mint_capability(
        commands=["gh.pr.list", "gh.pr.view", "demo.echo"],
        scopes=["demo:echo", "github:pull_request:read"],
        ttl_seconds=7200,
    )


def run_recovery_probe(
    registry: Registry,
    capability: str,
    receipt: RunReceipt,
    transcript: JsonlLog,
    repo: str,
) -> dict[str, Any]:
    """
    Deterministic invoke failure + recovery on the agent capability (real GAX, no LLM).
    Omits required `repo` on first gh.pr.list, then retries with repo.
    """
    transcript.write(
        {
            "type": "recovery_probe_start",
            "repo": repo,
            "note": "Deterministic adapter_error then successful retry (before LLM loop).",
        }
    )
    steps: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    turn = 0

    def _record(tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
        nonlocal turn
        turn += 1
        aid = result.get("audit_id")
        if aid:
            receipt.record_audit(aid)
        entry: dict[str, Any] = {
            "type": "tool_call",
            "phase": "recovery_probe",
            "turn": turn,
            "tool": tool,
            "arguments": arguments,
            "result": result,
            "audit_id": aid,
        }
        transcript.write(entry)
        steps.append((tool, arguments, result))
        if tool == "gax_invoke":
            env = result.get("envelope") or {}
            transcript.write(
                {
                    "type": "gax_invoke_receipt",
                    "phase": "recovery_probe",
                    "turn": turn,
                    "command": arguments.get("command"),
                    "audit_id": aid,
                    "ok": env.get("ok"),
                    "error_kind": result.get("error_kind"),
                    "data_keys": list((env.get("data") or {}).keys()),
                }
            )

    _record("gax_search", {"query": "list pull requests"}, gax_search(registry, "list pull requests"))
    _record("gax_doc", {"command": "gh.pr.list"}, gax_doc(registry, "gh.pr.list"))
    _record(
        "gax_invoke",
        {"command": "gh.pr.list", "args": {"state": "open"}},
        gax_invoke(registry, capability, "gh.pr.list", {"state": "open"}),
    )
    _record(
        "gax_invoke",
        {"command": "gh.pr.list", "args": {"repo": repo, "state": "open", "limit": 3}},
        gax_invoke(
            registry,
            capability,
            "gh.pr.list",
            {"repo": repo, "state": "open", "limit": 3},
        ),
    )

    failed_result = steps[2][2]
    recovered_result = steps[3][2]
    summary = {
        "pass": not failed_result.get("ok") and bool(recovered_result.get("ok")),
        "first_invoke_ok": bool(failed_result.get("ok")),
        "first_error_kind": failed_result.get("error_kind"),
        "retry_invoke_ok": bool(recovered_result.get("ok")),
        "retry_audit_id": recovered_result.get("audit_id"),
    }
    transcript.write({"type": "recovery_probe_summary", **summary})
    return summary


LLM_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "gax_search",
        "description": (
            "Discover registered GAX commands by keyword. "
            "Call this when you do not yet know the command id. "
            "Do not guess command names."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms, e.g. 'list pull requests'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gax_doc",
        "description": "Fetch documentation and argument schema for one GAX command id returned by gax_search.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command id, e.g. gh.pr.list"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "gax_invoke",
        "description": (
            "Execute a GAX command. Returns envelope v1 JSON with audit_id. "
            "On failure, read error.kind and retry with a different approach."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "args": {"type": "object", "description": "Arguments per gax_doc"},
            },
            "required": ["command", "args"],
        },
    },
]


def dispatch_tool(
    registry: Registry,
    capability: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if name == "gax_search":
        return gax_search(registry, str(arguments.get("query", "")))
    if name == "gax_doc":
        return gax_doc(registry, str(arguments.get("command", "")))
    if name == "gax_invoke":
        return gax_invoke(
            registry,
            capability,
            str(arguments.get("command", "")),
            dict(arguments.get("args") or {}),
        )
    return {"ok": False, "error": f"unknown_tool:{name}"}


AGENT_SYSTEM_PROMPT = """You are an operations agent that may ONLY act through three tools:
gax_search, gax_doc, and gax_invoke.

You do NOT have a preloaded tool catalog. You must discover commands at runtime:
1) gax_search with relevant keywords
2) gax_doc for the chosen command id
3) gax_invoke with valid args

Rules:
- Never invent command names. Only invoke commands you discovered via gax_search/gax_doc.
- After each gax_invoke, inspect the envelope. If ok is false, use error.kind to recover (e.g. fix args, discover another command).
- Prefer surface=model semantics: you receive projected JSON, not raw CLI dumps or MCP schemas.
- Complete the user mission in multiple steps. Think step by step.

You cannot run shell, MCP, or gh directly — only GAX tools."""


def build_user_mission(repo: str) -> str:
    return f"""Repository: {repo}

Mission:
1) Discover how to list open pull requests on this repo using GAX (search → doc → invoke).
2) From the list, pick the PR that looks most stale or neglected (use titles/numbers; explain briefly).
3) Fetch full details for that PR (discover + invoke view command).
4) Summarize merge/review risk in 3–5 bullet points.
5) Draft a short, neutral GitHub review comment (polite, actionable). Post it via a GAX invoke (demo.echo is acceptable as a stand-in for "post comment" — pass the draft in message).

When finished, reply with FINAL_ANSWER and include the draft comment text."""


def analyze_transcript_for_proof(transcript_path: Path) -> dict[str, Any]:
    """Machine-checkable proof flags from transcript.jsonl."""
    lines = [json.loads(ln) for ln in transcript_path.read_text().splitlines() if ln.strip()]
    tool_calls = [l for l in lines if l.get("type") == "tool_call"]
    first_invoke_idx = next(
        (i for i, t in enumerate(tool_calls) if t.get("tool") == "gax_invoke"),
        None,
    )
    first_search_idx = next(
        (i for i, t in enumerate(tool_calls) if t.get("tool") == "gax_search"),
        None,
    )
    discovery_before_invoke = (
        first_search_idx is not None
        and first_invoke_idx is not None
        and first_search_idx < first_invoke_idx
    )
    had_doc_before_first_invoke = False
    if first_invoke_idx is not None:
        prior = {t.get("tool") for t in tool_calls[:first_invoke_idx]}
        had_doc_before_first_invoke = "gax_doc" in prior

    invokes = [t for t in tool_calls if t.get("tool") == "gax_invoke"]
    recovery_after_error = False
    seen_error = False
    for t in invokes:
        if not t.get("result", {}).get("ok"):
            seen_error = True
        elif seen_error:
            recovery_after_error = True
            break

    return {
        "tool_call_count": len(tool_calls),
        "gax_search_count": sum(1 for t in tool_calls if t.get("tool") == "gax_search"),
        "gax_doc_count": sum(1 for t in tool_calls if t.get("tool") == "gax_doc"),
        "gax_invoke_count": len(invokes),
        "discovery_before_first_invoke": discovery_before_invoke,
        "doc_before_first_invoke": had_doc_before_first_invoke,
        "recovery_after_error": recovery_after_error,
        "completed": any(l.get("type") == "final_answer" for l in lines),
    }
