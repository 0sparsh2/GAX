# Reviewer feedback — status and planned work

Maps common review comments to repo artifacts and **what we fixed vs what is queued**. Aligns evaluation story with [eval/METHODOLOGY.md](../eval/METHODOLOGY.md) (no weighted composite).

| # | Feedback | Status | Where addressed / next |
|---|----------|--------|----------------------|
| **1** | Headline numbers are borrowed (Scalekit, Anthropic, Cloudflare), not our 75-trial study | **Documented** | [PUBLIC_NARRATIVE.md](./PUBLIC_NARRATIVE.md) §3; [mcp_vs_cli_benchmarks_2026/report.md](../mcp_vs_cli_benchmarks_2026/report.md) labeled synthesis |
| **2** | Our eval does not prove “GAX wins overall”; CLI wins tokens; harness is simulated | **Documented** | [live-run-summary.md](../eval/results/live-run-summary.md); METHODOLOGY; narrative §3–4 |
| **2b** | “Why not gh + logging proxy?” | **Documented** | [PUBLIC_NARRATIVE.md](./PUBLIC_NARRATIVE.md) §4 |
| **3** | Novelty vs optimized MCP; need comparisons + ablations | **In progress** | `eval/run_comparison.py --extended`; [docs/ABLATIONS.md](./ABLATIONS.md); ablations + programmatic_mcp + cli_agent_spec + multi-MCP catalog |
| **4** | Internal inconsistency (composite 0.986 in old docs) | **Fixed** | `research/11-project-completion.md`, `GAX_positioning_vs_benchmarks.json`, `report.md` updated in Task A |
| **5** | Enterprise claims partly prototype | **Documented** | Roadmap labels; narrative §5; no overclaim in README eval section |

## Evaluation story (single source of truth)

1. **External:** Scalekit / Anthropic / Cloudflare — cited, not replicated.
2. **Harness:** Separate metrics + Pareto axes; simulated transcripts; optional `--live-mcp`.
3. **Agent:** `examples/agent_runs/SAMPLE_RUN/` — real LLM, governance, audit correlation.

Do **not** use weighted composite scores in new docs. Historical composite in git before May 2026 is **deprecated**.

## Implemented (feedback #3) — `--extended`

| Modality | Purpose |
|----------|---------|
| `gax_ablation_no_cap` | Permissive cap on `policy_denied` vs restricted `gax` |
| `gax_ablation_no_envelope` | Raw JSON in context, no envelope v1 |
| `gax_ablation_schema_preload` | GAX + 43-tool schema tax |
| `programmatic_mcp` | Code-mode / optimized MCP (~1k tok overhead) |
| `cli_agent_spec` | Structured CLI result (CLI Agent Spec–style) |
| `cli_logged_proxy` | gh + post-hoc log line (“logging proxy” baseline) |
| `mcp_live_<server>` | Per-server naive MCP from [eval/fixtures/mcp_servers.yaml](../eval/fixtures/mcp_servers.yaml) |

Run: `python eval/run_comparison.py --extended` · Results: `eval/results/extended-comparison.md`

## Still queued

- Live probe of all npx MCP servers in CI (mock-only uses `mock_*` + github fixture)
- Formal side-by-side table vs MCP gateway filtering (Scalekit ~90% claim)
- Measured ablation on live agent (not just harness transcripts)
