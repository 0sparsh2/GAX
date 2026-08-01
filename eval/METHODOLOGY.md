# Evaluation methodology

## Purpose

Measure how much **agent context** CLI, naive MCP, and GAX consume when performing the same logical work — and whether the operation **succeeds** with **auditable, structured** output.

## Bias disclosure (read this first)

- **GAX is our protocol and reference implementation.** We do not claim a neutral third-party score.
- We **do not** publish a single weighted “composite” score chosen by the GAX team (e.g. 30/25/25/20) as the headline result.
- **Pareto winners** per axis are reported without declaring an overall champion unless all axes align (they usually do not).
- External benchmarks (Scalekit, Anthropic, Cloudflare) remain the independent references for MCP vs CLI economics.

### Two defects we found in our own aggregation (fixed)

An internal review found the aggregation quietly doing favorable work that this
document disclaimed. Both are fixed; both have regression tests in
`gax/tests/test_eval_scoring.py`.

**W1 — token medians compared different task sets.** Each modality runs its own
subset (`cli` has no equivalent for mock/discovery tasks), so a global median per
modality is not like-for-like. The 9 gax-only tasks are cheap mocks and discovery
stubs that dragged the GAX median down, publishing a **1.3×** ratio where the
paired figure is **~3.5×**.

→ **Token comparisons now use `paired_by_modality_pair`**, restricted to tasks where
both modalities produced a real row, reporting per-task ratios plus the median and
an explicit excluded-task list. `aggregate_by_modality` medians remain for
per-modality distribution only and are labelled as not head-to-head.

**W2 — `success_rate` reported 1.0 for everything.** Expected failures were rewritten
to `ok=True` (32 of 150 rows), so the metric measured nothing.

→ **Success is now three orthogonal axes**:

| Metric | Definition |
|--------|------------|
| `completion_rate` | Operation ran to a successful result on its own terms (uses un-rewritten `ok_raw`) |
| `expected_outcome_rate` | Result matched the task's declared expectation, including expected failures |
| `fail_closed_rate` | Enforcement fired *before* the adapter ran. Scoped to rows meant to be blocked; `None` for modalities with no enforcement layer, so raw `cli` is not scored 0.0 for a test it never sat |

`audit_id_rate` and `structured_envelope_rate` are **architectural constants, not
measurements** — CLI is 0% and GAX ~100% because that is what each design *is*. They
now live under `by_design_properties`, away from measured results.

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

See the three decomposed axes under [Bias disclosure](#two-defects-we-found-in-our-own-aggregation-fixed).
Every row also carries `ok_raw` (un-rewritten result), `adjusted`, and
`adjustment_reason`, so any expected-failure rewrite is auditable rather than silent.

## Running

```bash
pip install tiktoken   # strongly recommended
cd gax && pip install -e .
# Option A: repo-root .env with GITHUB_TOKEN=... (gitignored; auto-loaded by harness)
# Option B: export GITHUB_TOKEN=...
python ../eval/run_comparison.py --live-mcp

# Ablations + programmatic MCP / CLI Agent Spec / multi-MCP catalog
python ../eval/run_comparison.py --extended --mock-only   # CI
python ../eval/run_comparison.py --extended --live-mcp      # full
```

See [docs/ABLATIONS.md](../docs/ABLATIONS.md).

## Case study (external workflow)

See [case_study/README.md](case_study/README.md) — LangGraph-style 3-turn agent on a real GitHub repo with published token tables.
