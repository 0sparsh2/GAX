#!/usr/bin/env python3
"""Full evaluation pipeline: unit tests + comparison + optional live MCP + report."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAX = ROOT / "gax"
EVAL = ROOT / "eval"
OUT = EVAL / "results"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    py = GAX / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    report: dict = {"steps": []}

    code, out = run([str(py), "-m", "pytest", "-q"], cwd=GAX)
    report["steps"].append({"name": "pytest", "ok": code == 0, "code": code})
    if code != 0:
        print(out)
        _write(report)
        return code

    code, out = run([str(py), str(EVAL / "run_comparison.py")], cwd=GAX)
    report["steps"].append({"name": "comparison", "ok": code == 0, "code": code})

    if __import__("os").environ.get("GITHUB_TOKEN") or __import__("os").environ.get(
        "GITHUB_PERSONAL_ACCESS_TOKEN"
    ):
        code2, _ = run([str(py), str(EVAL / "run_comparison.py"), "--live-mcp"], cwd=GAX)
        report["steps"].append({"name": "comparison_live_mcp", "ok": code2 == 0, "code": code2})

    comp = json.loads((OUT / "comparison.json").read_text())
    report["winner"] = comp.get("winner")
    report["summary"] = comp.get("summary_mean_composite")

    gax_ok = report["summary"].get("gax", 0) >= max(
        report["summary"].get("cli", 0),
        report["summary"].get("mcp_naive_43", 0),
    )
    report["gax_leads_composite"] = gax_ok

    _write(report)
    print(json.dumps(report["summary"], indent=2))
    print(f"gax_leads_composite={gax_ok}")
    print(f"Full report: {OUT / 'full_eval.json'}")
    return 0 if gax_ok else 1


def _write(report: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "full_eval.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    sys.exit(main())
