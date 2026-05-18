# Case study: LangGraph-style PR triage on a real GitHub repo

> **Note:** This script **simulates** agent transcripts for token counting. For a **real LLM** using GAX as the execution substrate, run [`examples/agent_pr_triage.py`](../../examples/agent_pr_triage.py) instead.

## Goal

Compare **CLI**, **naive MCP** (schema tax), and **GAX** token costs with **tiktoken** (`cl100k_base`) on the same logical 3-turn workflow.

## Workflow

1. **Turn 1:** List open PRs (`limit: 5`) on `octocat/Hello-World`
2. **Turn 2:** View PR #1
3. **Turn 3:** Echo a completion marker (stand-in for “post summary to user”)

## Run

```bash
cd gax && pip install -e ".[dev]"
pip install -r ../eval/requirements.txt
export GITHUB_TOKEN=ghp_...   # optional: without it, gh/mock paths still run for GAX

python ../eval/case_study/run_case_study.py
```

Outputs: `eval/case_study/results.json` and printed markdown table.

## What we measure

| Modality | Modeled agent context |
|----------|------------------------|
| `cli` | System + `gh` commands + stdout per turn |
| `mcp_naive_43` | System + **full tools/list (~44k tok)** + tool call + result per turn |
| `gax` | System + `gax doc` stub + command + envelope v1 per turn |

This is a **self-assessment** by the GAX authors. Independent references: Scalekit, Anthropic Code Mode, Cloudflare — see `mcp_vs_cli_benchmarks_2026/report.md`.

## Sample results (mock / no token)

When `gh` is unavailable, exec adapter falls back to mock data; token **ratios** between modalities remain valid because schema tax is applied only to MCP.

| Modality | Typical 3-turn tokens (order of magnitude) |
|----------|---------------------------------------------|
| cli | ~1–4k |
| gax | ~2–5k |
| mcp_naive_43 | ~45–50k (dominated by schema) |

Re-run locally for numbers on your machine; commit `results.json` only if you intend to publish reproducible figures.
