"""
Evaluation metrics — no proprietary weighted 'composite' that favors GAX.

We report primary metrics separately and document known bias (GAX is our implementation).
See eval/METHODOLOGY.md and eval/frameworks.yaml.

Two design rules, added after an internal review found the aggregation was quietly
doing favorable work that the prose disclaimed:

1. **Success is decomposed** (W2). A single `success_rate` that rewrites expected
   failures to `ok=True` reports 1.0 for every modality and therefore measures
   nothing. We split it into three orthogonal axes — see `primary_metrics`.

2. **Token comparisons are paired** (W1). Each modality runs a different subset of
   the suite (`cli` has no equivalent for mock/discovery tasks), so a global median
   per modality compares different task sets. `paired_comparison` restricts to tasks
   where both modalities produced a real row.

Governance properties (`audit_id_rate`, `structured_envelope_rate`) are architectural
constants, not measurements: CLI is 0% and GAX ~100% because that is what each design
*is*. They are reported under `by_design_properties`, away from measured results.
"""

from __future__ import annotations

import statistics
from typing import Any

# Error kinds raised by gaxd *before* any adapter runs. Distinct from
# `adapter_error`, which means the backend was actually reached.
PRE_INVOKE_ERROR_KINDS = frozenset(
    {"policy_denied", "capability_invalid", "not_found"}
)


def _has_enforcement_layer(modality: str) -> bool:
    """
    Whether a modality even has a pre-invoke enforcement step to evaluate.

    Raw `cli` and naive MCP transcripts have none by design, so `fail_closed` is
    not-applicable for them rather than a failure. `cli_logged_proxy` logs only
    after the command ran, so it does not qualify either — that is precisely the
    distinction the proxy comparison exists to draw.
    """
    return modality.startswith("gax")


def primary_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """
    Observable metrics per run. Three orthogonal success axes (W2):

    - `completed`: the operation ran to a successful result on its own terms.
      Uses `ok_raw` when present so expected-failure rewriting cannot inflate it.
    - `expected_outcome`: the result matched what the task declared, including
      tasks where failure was the point.
    - `fail_closed`: enforcement fired before the adapter ran. Only meaningful for
      rows that were *supposed* to be blocked; `None` elsewhere so it never
      silently counts as a pass.
    """
    ok_raw = row.get("ok_raw")
    if ok_raw is None:
        # Row predates the ok_raw field, or was never adjusted.
        ok_raw = row.get("ok")
    skipped = bool(row.get("skipped"))
    error_kind = row.get("error_kind")

    completed = bool(ok_raw) and not skipped
    expected_outcome = bool(row.get("ok")) and not skipped

    # fail_closed is only meaningful for modalities that HAVE an enforcement layer.
    # Scoring `cli` as 0.0 would imply it failed a test it never sat: raw shell has
    # no pre-invoke check by design, so the honest value is "not applicable".
    fail_closed: bool | None = None
    if (
        row.get("expected_failure")
        and not skipped
        and _has_enforcement_layer(str(row.get("modality", "")))
    ):
        fail_closed = error_kind in PRE_INVOKE_ERROR_KINDS

    return {
        "task_id": row.get("task_id"),
        "modality": row.get("modality"),
        "completed": completed,
        "expected_outcome": expected_outcome,
        "fail_closed": fail_closed,
        "skipped": skipped,
        "tokens": int(row.get("tokens", 0)),
        "latency_ms": float(row.get("latency_ms", 0)),
        "has_audit_id": bool(row.get("audit_id")),
        "structured_envelope": bool(row.get("structured_envelope")),
        "error_kind": error_kind,
        "derivation": row.get("derivation", "measured"),
        "is_mock": bool(row.get("is_mock")),
    }


def aggregate_by_modality(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Per-modality aggregates. No weighted score.

    NOTE: `median_tokens` here is over each modality's *own* task subset, so it is
    NOT a like-for-like comparison across modalities. Use `paired_comparison` for
    that. This aggregate is kept for per-modality distribution only.
    """
    by_mod: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("skipped"):
            continue
        by_mod.setdefault(r["modality"], []).append(r)

    out: dict[str, dict[str, Any]] = {}
    for mod, items in by_mod.items():
        tokens = sorted(x.get("tokens", 0) for x in items)
        n = len(items)
        completed = sum(1 for x in items if x.get("completed"))
        expected = sum(1 for x in items if x.get("expected_outcome"))
        audits = sum(1 for x in items if x.get("has_audit_id"))
        structured = sum(1 for x in items if x.get("structured_envelope"))

        # fail_closed only counts rows where blocking was the intended outcome.
        fc_rows = [x for x in items if x.get("fail_closed") is not None]
        fc_pass = sum(1 for x in fc_rows if x["fail_closed"])

        out[mod] = {
            "n": n,
            "task_ids": sorted(str(x.get("task_id")) for x in items),
            "completion_rate": round(completed / n, 4) if n else 0,
            "expected_outcome_rate": round(expected / n, 4) if n else 0,
            "fail_closed_rate": (
                round(fc_pass / len(fc_rows), 4) if fc_rows else None
            ),
            "fail_closed_n": len(fc_rows),
            "median_tokens": tokens[n // 2] if tokens else 0,
            "mean_tokens": round(sum(tokens) / n, 1) if n else 0,
            "mean_latency_ms": round(
                sum(x.get("latency_ms", 0) for x in items) / n, 2
            )
            if n
            else 0,
            "by_design_properties": {
                "audit_id_rate": round(audits / n, 4) if n else 0,
                "structured_envelope_rate": round(structured / n, 4) if n else 0,
            },
            "derivation": _dominant_derivation(items),
            "is_mock": all(x.get("is_mock") for x in items) if items else False,
        }
    return out


def _dominant_derivation(items: list[dict[str, Any]]) -> str:
    kinds = {x.get("derivation", "measured") for x in items}
    if len(kinds) == 1:
        return kinds.pop()
    return "mixed"


def paired_comparison(
    rows: list[dict[str, Any]],
    mod_a: str,
    mod_b: str,
) -> dict[str, Any]:
    """
    Compare two modalities on ONLY the tasks where both produced a real (non-skipped)
    row (W1).

    A global median per modality compares different task sets: `cli` skips every
    mock/discovery task, while `gax` runs them cheaply, which drags the GAX median
    down and understates its true cost. This restricts to the shared set.

    Returns per-task ratios plus the median ratio. `excluded` records what was
    dropped and why, so the omission is auditable rather than silent.
    """
    def _index(mod: str) -> dict[str, dict[str, Any]]:
        return {
            str(r["task_id"]): r
            for r in rows
            if r.get("modality") == mod and not r.get("skipped")
        }

    a_rows, b_rows = _index(mod_a), _index(mod_b)
    shared = sorted(set(a_rows) & set(b_rows))

    per_task = []
    for tid in shared:
        ta = a_rows[tid].get("tokens", 0)
        tb = b_rows[tid].get("tokens", 0)
        per_task.append(
            {
                "task_id": tid,
                f"{mod_a}_tokens": ta,
                f"{mod_b}_tokens": tb,
                "ratio": round(tb / ta, 3) if ta else None,
            }
        )
    per_task.sort(key=lambda r: r["ratio"] if r["ratio"] is not None else -1)

    a_tokens = [a_rows[t].get("tokens", 0) for t in shared]
    b_tokens = [b_rows[t].get("tokens", 0) for t in shared]
    ratios = [r["ratio"] for r in per_task if r["ratio"] is not None]

    excluded = [
        {"task_id": t, "present_in": mod_a, "missing_from": mod_b}
        for t in sorted(set(a_rows) - set(b_rows))
    ] + [
        {"task_id": t, "present_in": mod_b, "missing_from": mod_a}
        for t in sorted(set(b_rows) - set(a_rows))
    ]

    return {
        "modality_a": mod_a,
        "modality_b": mod_b,
        "n_paired": len(shared),
        f"median_tokens_{mod_a}": statistics.median(a_tokens) if a_tokens else 0,
        f"median_tokens_{mod_b}": statistics.median(b_tokens) if b_tokens else 0,
        "median_ratio": round(statistics.median(ratios), 3) if ratios else None,
        "ratio_range": (
            [min(ratios), max(ratios)] if ratios else None
        ),
        "per_task": per_task,
        "excluded": excluded,
        "note": (
            f"Paired on {len(shared)} tasks where both {mod_a} and {mod_b} produced a "
            f"real row. {len(excluded)} task(s) excluded as not comparable."
        ),
    }


def paired_matrix(
    rows: list[dict[str, Any]],
    pairs: list[tuple[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run `paired_comparison` over the modality pairs that carry the argument."""
    pairs = pairs or [
        ("cli", "gax"),
        ("cli", "gax_mcp_bridge"),
        ("gax", "mcp_live"),
        ("cli", "mcp_live"),
    ]
    out: dict[str, dict[str, Any]] = {}
    for a, b in pairs:
        result = paired_comparison(rows, a, b)
        if result["n_paired"]:
            out[f"{a}_vs_{b}"] = result
    return out


def pareto_summary(agg: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """
    Which modality wins each axis (ties allowed). Not an overall winner — avoids
    invented weights.

    Token axis is deliberately excluded: per-modality medians run over different
    task subsets, so ranking them would reintroduce the W1 defect. Token comparisons
    belong in `paired_comparison`.
    """
    if not agg:
        return {}
    axes = {
        "highest_completion_rate": lambda m: -agg[m]["completion_rate"],
        "highest_expected_outcome_rate": lambda m: -agg[m]["expected_outcome_rate"],
    }
    winners: dict[str, list[str]] = {}
    for axis, key_fn in axes.items():
        vals = {m: key_fn(m) for m in agg}
        best = min(vals.values())
        winners[axis] = [m for m, v in vals.items() if v == best]

    fc = {m: a for m, a in agg.items() if a.get("fail_closed_rate") is not None}
    if fc:
        best_fc = max(a["fail_closed_rate"] for a in fc.values())
        winners["highest_fail_closed_rate"] = [
            m for m, a in fc.items() if a["fail_closed_rate"] == best_fc
        ]
    return winners
