# Evaluation methodology: CLI vs MCP vs GAX

## Goal

Measure **agent context cost** (tiktoken) and **outcome quality** (success, audit, structure) when the same logical work is done via CLI, naive MCP, or GAX.

## Bias disclosure

GAX is our protocol and reference implementation. We do **not** publish a team-weighted composite score. See [eval/METHODOLOGY.md](../eval/METHODOLOGY.md) and [eval/frameworks.yaml](../eval/frameworks.yaml).

## Harness

```bash
pip install -r eval/requirements.txt
cd gax && pip install -e ".[dev]"
python ../eval/run_comparison.py
export GITHUB_TOKEN=...
python ../eval/run_comparison.py --live-mcp
python ../eval/case_study/run_case_study.py
```

## Suite (v2)

18 tasks in `eval/tasks.yaml`: happy path, errors, policy denial, truncation, discovery, multi-turn, plan failure, MCP bridge.

## Modalities

| Modality | What it measures |
|----------|------------------|
| `cli` | `gh` subprocess; command + stdout in transcript |
| `mcp_naive_43` | Same + **~44k schema tax** (Scalekit fixture) |
| `mcp_live` | Real `tools/list` size when `--live-mcp` |
| `gax` | `gax doc` stub + envelope v1 |
| `gax_mcp_bridge` | Envelope over MCP (schema not in prompt) |
| `gax_plan` | Multi-step plan → one envelope |

## Primary metrics (separate axes)

- Median / mean tokens (`tiktoken` cl100k_base)
- Success rate (including expected failures on error tasks)
- Audit-id rate
- Structured-envelope rate

Pareto winners per axis are reported in `eval/results/comparison.md` without declaring an overall champion.

## Case study

[eval/case_study/README.md](../eval/case_study/README.md) — 3-turn PR triage with published token table.

## Limitations

- MCP schema tax uses published fixtures unless `--live-mcp`
- `gax_mcp_bridge` requires `GITHUB_TOKEN`
- Self-assessment; external benchmarks remain in `mcp_vs_cli_benchmarks_2026/`
