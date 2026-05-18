#!/usr/bin/env python3
"""Full evaluation pipeline: unit tests + comparison + optional live MCP."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAX = ROOT / "gax"
EVAL = ROOT / "eval"
OUT = EVAL / "results"

sys.path.insert(0, str(EVAL))
from load_env import load_repo_env  # noqa: E402

load_repo_env(ROOT)


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    py = GAX / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    report: dict = {"steps": [], "bias_disclosure": "GAX self-assessment — no composite winner"}

    code, out = run([str(py), "-m", "pytest", "-q"], cwd=GAX)
    report["steps"].append({"name": "pytest", "ok": code == 0, "code": code})
    if code != 0:
        print(out)
        _write(report)
        return code

    code, out = run([str(py), str(EVAL / "run_comparison.py")], cwd=ROOT)
    report["steps"].append({"name": "comparison_v2", "ok": code == 0, "code": code})
    if code != 0:
        print(out)

    import os

    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        code2, _ = run(
            [str(py), str(EVAL / "run_comparison.py"), "--live-mcp"],
            cwd=ROOT,
        )
        report["steps"].append(
            {"name": "comparison_live_mcp", "ok": code2 == 0, "code": code2}
        )

    comp_path = OUT / "comparison.json"
    if comp_path.exists():
        comp = json.loads(comp_path.read_text())
        report["aggregate_by_modality"] = comp.get("aggregate_by_modality")
        report["pareto_winners"] = comp.get("pareto_winners_per_axis")
        report["task_count"] = comp.get("task_count")
        report["token_counter"] = comp.get("token_counter")

    _write(report)
    print(json.dumps(report.get("aggregate_by_modality"), indent=2))
    print(f"Full report: {OUT / 'full_eval.json'}")
    return 0 if all(s.get("ok") for s in report["steps"]) else 1


def _write(report: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "full_eval.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    sys.exit(main())
