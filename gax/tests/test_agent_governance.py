"""CI-safe governance receipts (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "examples"))

from agent_lib import (  # noqa: E402
    RunReceipt,
    analyze_transcript_for_proof,
    mint_agent_cap,
    run_governance_receipts,
    run_recovery_probe,
    JsonlLog,
)
from gax.registry import Registry  # noqa: E402


def test_governance_receipts(tmp_path) -> None:
    reg = Registry()
    log = JsonlLog(tmp_path / "governance.jsonl")
    summary = run_governance_receipts(reg, log)
    assert summary["all_pass"] is True
    assert summary["audit_correlation"]["all_correlated"] is True


def test_recovery_probe_sets_proof_flag(tmp_path) -> None:
    reg = Registry()
    transcript = JsonlLog(tmp_path / "transcript.jsonl")
    receipt = RunReceipt(
        run_id="test",
        run_dir=tmp_path,
        repo="octocat/Hello-World",
        model="test",
    )
    cap = mint_agent_cap()
    summary = run_recovery_probe(reg, cap, receipt, transcript, "octocat/Hello-World")
    assert summary["pass"] is True
    assert summary["first_error_kind"] == "adapter_error"
    proof = analyze_transcript_for_proof(transcript.path)
    assert proof["recovery_after_error"] is True
