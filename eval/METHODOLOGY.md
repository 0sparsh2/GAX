# Evaluation methodology

## Purpose

Measure how much **agent context** CLI, naive MCP, and GAX consume when performing the same logical work — and whether the operation **succeeds** with **auditable, structured** output.

## Bias disclosure (read this first)

- **GAX is our protocol and reference implementation.** We do not claim a neutral third-party score.
- We **do not** publish a single weighted “composite” score chosen by the GAX team (e.g. 30/25/25/20) as the headline result.
- Primary results are **separate metrics**: median tokens (tiktoken), success rate, audit-id rate, structured-envelope rate.
- **Pareto winners** per axis are reported without declaring an overall champion unless all axes align (they usually do not).
- External benchmarks (Scalekit, Anthropic, Cloudflare) remain the independent references for MCP vs CLI economics.

## Token counting

- **Default:** `tiktoken` `cl100k_base` (same family as GPT-4 / many agents).
- **Fallback:** `len(text)//4` if tiktoken is not installed.
- **Naive MCP** adds published schema overhead (43-tool Copilot MCP ~44,026 tokens/session per Scalekit) to per-task transcript cost — this models tool-list injection, not a live MCP server for every task.

## Modalities

| Modality | What it models |
|----------|----------------|
| `cli` | `gh` subprocess; command + stdout in transcript |
| `mcp_naive_43` | Same backend + full GitHub MCP schema tax (43 tools) |
| `mcp_live` | Optional: real `tools/list` byte size from `@modelcontextprotocol/server-github` |
| `gax` | `gax doc` stub + envelope (`surface=model`) |
| `gax_mcp_bridge` | GAX envelope over MCP tool call (schema not in agent prompt) |

## Task suite

18 tasks in `tasks.yaml`: happy path, errors, policy denial, truncation, multi-turn sessions, plan failure, discovery-only.

## Success criteria

| Metric | Definition |
|--------|------------|
| `success` | Operation completed as intended (`ok` and not `skipped`) |
| `has_audit_id` | GAX envelope includes `audit_id` |
| `structured_envelope` | Valid envelope v1 with `data` object |

## Running

```bash
pip install tiktoken   # strongly recommended
cd gax && pip install -e .
export GITHUB_TOKEN=...   # required for live gh + mcp_bridge integration tasks
python ../eval/run_comparison.py --live-mcp
```

## Case study (external workflow)

See [case_study/README.md](case_study/README.md) — LangGraph-style 3-turn agent on a real GitHub repo with published token tables.
