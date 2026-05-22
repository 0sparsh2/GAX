"""GAX ablation modalities for eval (feedback #3)."""

from __future__ import annotations

import json
from typing import Any

from session_transcript import Transcript, gax_raw_turn, gax_turn

DOC_STUB_TOKENS = 120


def run_gax_ablation_no_cap(
    task: dict[str, Any],
    registry: Any,
    default_cap: str,
    *,
    row_fn: Any,
    gax_invoke: Any,
    gax_transcript_tokens: Any,
) -> dict[str, Any]:
    """
    Policy ablation: use permissive cap on policy_denied task — invoke succeeds
    where restricted cap correctly denies.
    """
    if task.get("id") != "policy_denied":
        return row_fn(
            task_id=task["id"],
            modality="gax_ablation_no_cap",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            notes="only applicable to policy_denied task",
            category=task.get("category", ""),
        )

    cmd = task["gax_command"]
    args = dict(task.get("gax_args") or {})
    env, code, latency = gax_invoke(registry, default_cap, cmd, args)
    ok = code == 0 and bool(env.get("ok"))
    return row_fn(
        task_id=task["id"],
        modality="gax_ablation_no_cap",
        tokens=gax_transcript_tokens(cmd, env),
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=env.get("v") == 1,
        error_kind=None if ok else (env.get("error") or {}).get("kind"),
        notes="ablation: permissive cap — policy does not deny (contrast gax restricted cap)",
        category=task.get("category", ""),
    )


def run_gax_ablation_no_envelope(
    task: dict[str, Any],
    registry: Any,
    cap: str,
    *,
    row_fn: Any,
    gax_invoke: Any,
) -> dict[str, Any]:
    """Ablation: same invoke, agent sees raw JSON data blob not envelope v1."""
    if task.get("gax_only") and task.get("id") in ("unknown_command", "policy_denied"):
        return row_fn(
            task_id=task["id"],
            modality="gax_ablation_no_envelope",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            notes="skipped for gax-only error tasks",
            category=task.get("category", ""),
        )
    if not task.get("gax_command"):
        return row_fn(
            task_id=task["id"],
            modality="gax_ablation_no_envelope",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            category=task.get("category", ""),
        )

    cmd = task["gax_command"]
    args = dict(task.get("gax_args") or {})
    env, code, latency = gax_invoke(registry, cap, cmd, args)
    ok = code == 0 and bool(env.get("ok"))
    raw = json.dumps(env.get("data") or env, ensure_ascii=False)
    t = Transcript()
    gax_raw_turn(
        t,
        system="You invoke GAX but receive raw JSON blobs.",
        doc_stub=f"gax doc {cmd}",
        command=f"gax {cmd}",
        raw_output=raw,
    )
    err = (env.get("error") or {}) if isinstance(env.get("error"), dict) else {}
    return row_fn(
        task_id=task["id"],
        modality="gax_ablation_no_envelope",
        tokens=t.total_tokens(),
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=False,
        error_kind=err.get("kind") if not ok else None,
        notes="ablation: no envelope v1 in context (raw data only)",
        category=task.get("category", ""),
    )


def run_gax_ablation_schema_preload(
    task: dict[str, Any],
    registry: Any,
    cap: str,
    *,
    row_fn: Any,
    gax_invoke: Any,
    gax_transcript_tokens: Any,
    schema_tokens: int,
) -> dict[str, Any]:
    """Ablation: lazy gax doc + full MCP schema tax preloaded (naive MCP cost on GAX path)."""
    if not task.get("gax_command") or task.get("category") == "discovery":
        return row_fn(
            task_id=task["id"],
            modality="gax_ablation_schema_preload",
            tokens=0,
            latency_ms=0,
            ok=True,
            skipped=True,
            category=task.get("category", ""),
        )

    cmd = task["gax_command"]
    args = dict(task.get("gax_args") or {})
    env, code, latency = gax_invoke(registry, cap, cmd, args)
    ok = code == 0 and bool(env.get("ok"))
    base = gax_transcript_tokens(cmd, env)
    err = (env.get("error") or {}) if isinstance(env.get("error"), dict) else {}
    return row_fn(
        task_id=task["id"],
        modality="gax_ablation_schema_preload",
        tokens=base + schema_tokens,
        latency_ms=latency,
        ok=ok,
        audit_id=env.get("audit_id"),
        structured_envelope=env.get("v") == 1,
        error_kind=err.get("kind") if not ok else None,
        notes=f"ablation: +{schema_tokens} tok schema preload (43-tool fixture)",
        category=task.get("category", ""),
    )
