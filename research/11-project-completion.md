# Project completion summary (May 2026)

## Deliverables

| Area | Location |
|------|----------|
| GAX reference impl | `gax/` v0.4.0 |
| Research hub | `research/` |
| Benchmark deep-research | `mcp_vs_cli_benchmarks_2026/report.md` (synthesis, not new 75-trial study) |
| ACSP specification | `docs/acsp/ACSP-1.0.md` |
| Public narrative | `docs/PUBLIC_NARRATIVE.md` |
| Evaluation | `eval/run_comparison.py`, `eval/METHODOLOGY.md` |
| Real LLM agent proof | `examples/agent_runs/SAMPLE_RUN/` |
| Migration research | `gax_implementation_migration_2026/report.md` |

## Evaluation conclusion (current — no weighted composite)

Per [eval/METHODOLOGY.md](../eval/METHODOLOGY.md) and [eval/results/live-run-summary.md](../eval/results/live-run-summary.md):

| Axis | Leader in our harness |
|------|------------------------|
| **Lowest median tokens** | `cli` (~104) |
| **Audit-id + structured envelope** | `gax`, `gax_mcp_bridge`, `gax_plan` |
| **Naive MCP schema tax** | `mcp_naive_43` ~44k tokens/session (fixture) |

**We do not claim “GAX wins overall.”** We claim GAX is a **third surface** when you need CLI-shaped invocations, MCP-class governance, and envelope v1 in one protocol — without naive MCP schema preload.

**Deprecated:** Earlier docs that cited weighted composite (~0.986 gax vs ~0.68 cli) are **obsolete**; do not use in submissions.

## Evidence types

1. **External synthesis** — Scalekit, Anthropic, Cloudflare ([benchmark report](../mcp_vs_cli_benchmarks_2026/report.md)).
2. **Harness** — 18 tasks, simulated transcripts, separate metrics, optional `--live-mcp`.
3. **Agent receipts** — `SAMPLE_RUN`: real LLM, governance, audit correlation.

## Reproduce

```bash
cd gax && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python ../eval/run_comparison.py --live-mcp   # optional GITHUB_TOKEN
python ../examples/agent_pr_triage.py       # optional LLM keys
pytest tests/test_acsp_envelope_conformance.py -q
```
