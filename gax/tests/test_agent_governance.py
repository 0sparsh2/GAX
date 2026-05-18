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


def test_recovery_probe_sets_proof_flag(tmp_path, monkeypatch) -> None:
    # CI has `gh` but often no GITHUB_TOKEN — stub list so retry succeeds offline.
    from gax.adapters import exec_adapter

    def _gh_pr_list(args: dict, *, tenant_id: str | None = None) -> dict:
        if "repo" not in args:
            raise KeyError("repo")
        return {
            "items": [
                {
                    "number": 1,
                    "title": "[mock] Sample PR",
                    "state": "OPEN",
                    "url": "https://github.com/octocat/Hello-World/pull/1",
                    "author": "mock-user",
                    "draft": False,
                }
            ],
        }

    monkeypatch.setattr(exec_adapter, "_gh_available", lambda: True)
    monkeypatch.setattr(exec_adapter, "_gh_pr_list", _gh_pr_list)

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
