"""CI-safe governance receipts (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "examples"))

from agent_lib import run_governance_receipts, JsonlLog  # noqa: E402
from gax.registry import Registry  # noqa: E402


def test_governance_receipts(tmp_path) -> None:
    reg = Registry()
    log = JsonlLog(tmp_path / "governance.jsonl")
    summary = run_governance_receipts(reg, log)
    assert summary["all_pass"] is True
    assert summary["audit_correlation"]["all_correlated"] is True
