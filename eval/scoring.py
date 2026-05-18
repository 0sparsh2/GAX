"""
Evaluation metrics — no proprietary weighted 'composite' that favors GAX.

We report primary metrics separately and document known bias (GAX is our implementation).
See eval/METHODOLOGY.md and eval/frameworks.yaml.
"""

from __future__ import annotations

from typing import Any


def primary_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Observable metrics per run (higher success_rate is better; lower tokens is better)."""
    return {
        "task_id": row.get("task_id"),
        "modality": row.get("modality"),
        "success": bool(row.get("ok")) and not row.get("skipped"),
        "skipped": bool(row.get("skipped")),
        "tokens": int(row.get("tokens", 0)),
        "latency_ms": float(row.get("latency_ms", 0)),
        "has_audit_id": bool(row.get("audit_id")),
        "structured_envelope": bool(row.get("structured_envelope")),
        "error_kind": row.get("error_kind"),
    }


def aggregate_by_modality(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Median tokens, success rate, governance rate — no weighted score."""
    by_mod: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("skipped"):
            continue
        by_mod.setdefault(r["modality"], []).append(r)

    out: dict[str, dict[str, Any]] = {}
    for mod, items in by_mod.items():
        tokens = sorted(x.get("tokens", 0) for x in items)
        n = len(items)
        successes = sum(1 for x in items if x.get("success"))
        audits = sum(1 for x in items if x.get("has_audit_id"))
        structured = sum(1 for x in items if x.get("structured_envelope"))
        mid = tokens[n // 2] if tokens else 0
        out[mod] = {
            "n": n,
            "success_rate": round(successes / n, 4) if n else 0,
            "median_tokens": mid,
            "mean_tokens": round(sum(tokens) / n, 1) if n else 0,
            "audit_id_rate": round(audits / n, 4) if n else 0,
            "structured_envelope_rate": round(structured / n, 4) if n else 0,
            "mean_latency_ms": round(
                sum(x.get("latency_ms", 0) for x in items) / n, 2
            )
            if n
            else 0,
        }
    return out


def pareto_summary(agg: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """
    Which modality wins each axis (ties allowed).
    Not a overall winner — avoids invented weights.
    """
    if not agg:
        return {}
    axes = {
        "lowest_median_tokens": lambda m: agg[m]["median_tokens"],
        "highest_success_rate": lambda m: -agg[m]["success_rate"],
        "highest_audit_id_rate": lambda m: -agg[m]["audit_id_rate"],
        "highest_structured_envelope_rate": lambda m: -agg[m]["structured_envelope_rate"],
    }
    winners: dict[str, list[str]] = {}
    for axis, key_fn in axes.items():
        vals = {m: key_fn(m) for m in agg}
        best = min(vals.values())
        winners[axis] = [m for m, v in vals.items() if v == best]
    return winners
