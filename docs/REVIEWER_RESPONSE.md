# Reviewer feedback — status and planned work

Maps common review comments to repo artifacts and **what we fixed vs what is queued**. Aligns evaluation story with [eval/METHODOLOGY.md](../eval/METHODOLOGY.md) (no weighted composite).

| # | Feedback | Status | Where addressed / next |
|---|----------|--------|----------------------|
| **1** | Headline numbers are borrowed (Scalekit, Anthropic, Cloudflare), not our 75-trial study | **Documented** | [PUBLIC_NARRATIVE.md](./PUBLIC_NARRATIVE.md) §3; [mcp_vs_cli_benchmarks_2026/report.md](../mcp_vs_cli_benchmarks_2026/report.md) labeled synthesis |
| **2** | Our eval does not prove “GAX wins overall”; CLI wins tokens; harness is simulated | **Documented** | [live-run-summary.md](../eval/results/live-run-summary.md); METHODOLOGY; narrative §3–4 |
| **2b** | “Why not gh + logging proxy?” | **Documented** | [PUBLIC_NARRATIVE.md](./PUBLIC_NARRATIVE.md) §4 |
| **3** | Novelty vs optimized MCP; need comparisons + ablations | **Queued** (Track B) | Ablation tasks: no caps, no envelope, full schema preload; compare CLI Agent Spec, MCP gateway |
| **4** | Internal inconsistency (composite 0.986 in old docs) | **Fixed** | `research/11-project-completion.md`, `GAX_positioning_vs_benchmarks.json`, `report.md` updated in Task A |
| **5** | Enterprise claims partly prototype | **Documented** | Roadmap labels; narrative §5; no overclaim in README eval section |

## Evaluation story (single source of truth)

1. **External:** Scalekit / Anthropic / Cloudflare — cited, not replicated.
2. **Harness:** Separate metrics + Pareto axes; simulated transcripts; optional `--live-mcp`.
3. **Agent:** `examples/agent_runs/SAMPLE_RUN/` — real LLM, governance, audit correlation.

Do **not** use weighted composite scores in new docs. Historical composite in git before May 2026 is **deprecated**.

## Planned ablations (feedback #3)

| Variant | Purpose |
|---------|---------|
| GAX without capability enforcement | Isolate governance value |
| GAX without envelope (raw adapter dump) | Isolate structure value |
| GAX with full schema preload | Isolate lazy discovery value |
| `gax_mcp_bridge` vs naive `mcp_live` | Same backend, schema in vs out of prompt |

## Planned comparisons (feedback #3)

- [CLI Agent Spec](https://github.com/cli-agent-spec/cli-agent-spec) — structured CLI failures vs ACSP envelope
- Anthropic programmatic MCP / Cloudflare Code Mode — token mitigations vs ACSP control plane
- MCP gateway schema filtering (Scalekit ~90% claim) — filter vs lazy discovery + caps
