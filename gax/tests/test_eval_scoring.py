"""
Evaluator gates for W1 (paired comparison) and W2 (decomposed success metrics).

These guard the two defects found in the eval review — see docs/PLAN-2026H2.md.
The point is that a future refactor cannot silently reintroduce either:

- W1: comparing token medians across modalities that ran different task subsets
- W2: a success metric that reports 1.0 for everything because expected failures
  are rewritten to ok=True
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL_DIR))

from scoring import (  # noqa: E402
    aggregate_by_modality,
    paired_comparison,
    paired_matrix,
    pareto_summary,
    primary_metrics,
)


def _row(task_id, modality, tokens, **kw):
    base = {
        "task_id": task_id,
        "modality": modality,
        "tokens": tokens,
        "ok": kw.pop("ok", True),
        "latency_ms": 1.0,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# W2 — decomposed success metrics
# --------------------------------------------------------------------------


def test_expected_failure_does_not_inflate_completion():
    """A rewritten expected failure must not count as a completion."""
    row = _row(
        "policy_denied",
        "gax",
        115,
        ok=True,  # rewritten by _apply_expected_outcome
        ok_raw=False,  # what actually happened
        expected_failure=True,
        error_kind="policy_denied",
    )
    m = primary_metrics(row)
    assert m["completed"] is False, "expected failure must not count as completed"
    assert m["expected_outcome"] is True, "but it did match expectation"


def test_fail_closed_only_scored_on_rows_meant_to_be_blocked():
    """fail_closed is None where blocking was never the intent — never a free pass."""
    happy = primary_metrics(_row("pr_list", "gax", 100, ok=True, ok_raw=True))
    assert happy["fail_closed"] is None

    blocked = primary_metrics(
        _row(
            "policy_denied",
            "gax",
            115,
            ok=True,
            ok_raw=False,
            expected_failure=True,
            error_kind="policy_denied",
        )
    )
    assert blocked["fail_closed"] is True


def test_adapter_error_is_not_fail_closed():
    """
    An adapter_error means the backend was reached — enforcement did NOT fire
    before invoke, so it must not score as fail-closed.
    """
    m = primary_metrics(
        _row(
            "pr_list_invalid_repo",
            "gax",
            134,
            ok=True,
            ok_raw=False,
            expected_failure=True,
            error_kind="adapter_error",
        )
    )
    assert m["fail_closed"] is False


def test_ablation_no_cap_does_not_fail_closed():
    """
    The point of the no_cap ablation: with a permissive cap the invoke succeeds,
    so fail_closed_rate must be 0.0 while restricted gax is 1.0. If both read 1.0
    the ablation is not measuring anything.
    """
    rows = [
        primary_metrics(
            _row(
                "policy_denied",
                "gax",
                115,
                ok=True,
                ok_raw=False,
                expected_failure=True,
                error_kind="policy_denied",
            )
        ),
        primary_metrics(
            _row(
                "policy_denied",
                "gax_ablation_no_cap",
                282,
                ok=False,
                ok_raw=True,
                expected_failure=True,
                error_kind=None,
            )
        ),
    ]
    agg = aggregate_by_modality(rows)
    assert agg["gax"]["fail_closed_rate"] == 1.0
    assert agg["gax_ablation_no_cap"]["fail_closed_rate"] == 0.0


def test_fail_closed_not_applicable_without_enforcement_layer():
    """
    Raw cli has no pre-invoke check by design, so scoring it 0.0 would imply it
    failed a test it never sat. The honest value is not-applicable.
    """
    m = primary_metrics(
        _row(
            "pr_list_invalid_repo",
            "cli",
            61,
            ok=True,
            ok_raw=False,
            expected_failure=True,
        )
    )
    assert m["fail_closed"] is None

    # A post-hoc logging proxy logs only after the command ran — also not enforcement.
    proxy = primary_metrics(
        _row(
            "pr_list_invalid_repo",
            "cli_logged_proxy",
            159,
            ok=True,
            ok_raw=False,
            expected_failure=True,
        )
    )
    assert proxy["fail_closed"] is None


def test_governance_props_are_segregated_from_measured_results():
    """audit_id_rate is architectural, not measured — keep it out of the top level."""
    rows = [primary_metrics(_row("pr_list", "gax", 100, audit_id="aud_x"))]
    agg = aggregate_by_modality(rows)
    assert "audit_id_rate" not in agg["gax"]
    assert agg["gax"]["by_design_properties"]["audit_id_rate"] == 1.0


# --------------------------------------------------------------------------
# W1 — paired comparison
# --------------------------------------------------------------------------


def test_paired_excludes_non_overlapping_tasks():
    """gax-only tasks must not enter the token comparison."""
    rows = [
        primary_metrics(_row("shared_a", "cli", 100)),
        primary_metrics(_row("shared_a", "gax", 300)),
        primary_metrics(_row("gax_only", "gax", 10)),  # would drag the median down
    ]
    p = paired_comparison(rows, "cli", "gax")
    assert p["n_paired"] == 1
    assert p["median_ratio"] == 3.0
    assert [e["task_id"] for e in p["excluded"]] == ["gax_only"]


def test_paired_n_never_exceeds_smaller_modality():
    rows = [
        primary_metrics(_row("t1", "cli", 100)),
        primary_metrics(_row("t1", "gax", 200)),
        primary_metrics(_row("t2", "gax", 200)),
        primary_metrics(_row("t3", "gax", 200)),
    ]
    p = paired_comparison(rows, "cli", "gax")
    n_cli = sum(1 for r in rows if r["modality"] == "cli")
    n_gax = sum(1 for r in rows if r["modality"] == "gax")
    assert p["n_paired"] <= min(n_cli, n_gax)


def test_paired_ignores_skipped_rows():
    """A skipped row is not a real observation and cannot anchor a pair."""
    rows = [
        primary_metrics(_row("t1", "cli", 2, skipped=True)),
        primary_metrics(_row("t1", "gax", 200)),
    ]
    assert paired_comparison(rows, "cli", "gax")["n_paired"] == 0


def test_gax_costs_more_than_cli_on_paired_tasks():
    """
    Regression guard on the headline claim. The published 1.3× came from comparing
    different task subsets; every real paired task costs GAX more than CLI.
    If this ever drops to ~1.0, the set-mismatch defect is back.
    """
    import json

    results = EVAL_DIR / "results" / "comparison.json"
    if not results.exists():
        pytest.skip("run eval/run_comparison.py first")

    data = json.loads(results.read_text())
    paired = data.get("paired_by_modality_pair", {})
    cg = paired.get("cli_vs_gax")
    if not cg:
        pytest.skip("no cli/gax pairing in this run")

    assert cg["n_paired"] >= 4, "too few paired tasks to claim anything"
    assert cg["median_ratio"] > 2.0, (
        f"paired median ratio {cg['median_ratio']}× is implausibly low — "
        "check for task-set mismatch (W1)"
    )


def test_pareto_excludes_token_axis():
    """
    Ranking modalities by median tokens would reintroduce W1, since those medians
    run over different task subsets.
    """
    rows = [
        primary_metrics(_row("t1", "cli", 100)),
        primary_metrics(_row("t1", "gax", 300)),
    ]
    winners = pareto_summary(aggregate_by_modality(rows))
    assert not any("token" in axis for axis in winners)


def test_paired_matrix_skips_empty_pairs():
    rows = [primary_metrics(_row("t1", "cli", 100))]
    assert "cli_vs_gax" not in paired_matrix(rows)
