# Phase 1 findings — MCP vs CLI benchmarks (2024–2026)

**Status:** Phase 1 complete. **Phase 2 complete** (8/8 JSON validated). **Report:** [report.md](./report.md).

**Method:** Web search + primary fetch of Scalekit (Mar 2026), Anthropic engineering (Nov 2025), Cloudflare Code Mode (Feb 2026), OnlyCLI, GitHub `gh-aw-firewall` cli-proxy report (Apr 2026), Firecrawl synthesis, CLI Agent Spec repos. Cross-checked against `research/01-background-mcp-vs-cli.md` and `research/05-comparison-matrix.md`.

---

## Top 5 benchmark numbers (cited)

| # | Metric | Value | URL |
|---|--------|-------|-----|
| 1 | Simple GitHub task token use (repo language) | CLI **1,365** vs MCP **44,026** (**32×**) | https://www.scalekit.com/blog/mcp-vs-cli-use |
| 2 | MCP run failure rate (same harness) | **28%** failed (7/25 `ConnectTimeout`); CLI **25/25** | https://www.scalekit.com/blog/mcp-vs-cli-use |
| 3 | Suite token multiplier (median across 5 tasks) | **4×–32×** MCP vs CLI; **75** runs, Claude Sonnet 4 | https://github.com/scalekit-inc/mcp-vs-cli-benchmark |
| 4 | Code execution + MCP (example workflow) | **150,000 → 2,000** tokens (**98.7%** reduction) | https://www.anthropic.com/engineering/code-execution-with-mcp |
| 5 | Cloudflare API via Code Mode | **~1,000** tokens (2 tools) vs **1,170,523** native MCP / **244,047** minimal-params MCP | https://blog.cloudflare.com/code-mode-mcp/ |

**Honorable mentions (not top 5 but material):**

- **~55,000** tokens idle schema for **93-tool** GitHub MCP server; **143,000** for three services (72% of 200k window) — https://onlycli.github.io/OnlyCLI/blog/mcp-token-cost-benchmark/
- **~24%** token/cost reduction replacing GitHub MCP with `gh` via cli-proxy (single workflow, n=1 post) — https://github.com/github/gh-aw-firewall/issues/1885
- **~90%** token reduction claim for MCP gateway schema filtering (43 → 2–3 tools) — https://www.scalekit.com/blog/mcp-vs-cli-use
- **800-token** CLI+Skills file: ~⅓ fewer tool calls and latency vs naive CLI — Scalekit (same)

**MindStudio:** No published MCP-vs-CLI token benchmark found; product is MCP/SDK for exposing agents as tools (https://github.com/mindstudio-ai/mindstudio-agent), not a comparator study. Use Scalekit + OnlyCLI + odedha-dr/mcp-vs-direct-benchmark for Phase 2 instead.

---

## Research items (outline)

Path: **`mcp_vs_cli_benchmarks_2026/outline.yaml`**

| # | Item | Category |
|---|------|----------|
| 1 | Scalekit MCP vs CLI benchmark | Empirical benchmark |
| 2 | Naive MCP schema overhead | Mechanism |
| 3 | CLI token baseline | Mechanism |
| 4 | MCP reliability and failure modes | Reliability |
| 5 | Optimized MCP — programmatic tool calling | Mitigation |
| 6 | Optimized MCP — Cloudflare Code Mode | Mitigation |
| 7 | Governance and security trade-off | Enterprise |
| 8 | GAX positioning vs benchmarks | Synthesis |

---

## Cross-check: corrections for existing `research/` docs

### `research/01-background-mcp-vs-cli.md`

| Current claim | Verdict | Recommended edit |
|---------------|---------|------------------|
| GitHub MCP **~44k–55k** tokens upfront | **Partially correct** | Split by server: **Copilot MCP 43 tools** drives ~44k on a simple task (Scalekit); **github-mcp-server ~93 tools** ~55k idle (OnlyCLI). Not interchangeable. |
| **4×–35×** higher token usage | **Slightly high upper bound** | Prefer **4×–32×** (Scalekit median suite, n=75, p<0.05). Drop **35×** unless citing OnlyCLI headline only with attribution. |
| **25–30%** MCP run failures | **Refine** | Cite **28%** infrastructure failures (Scalekit, Copilot MCP `ConnectTimeout`, Mar 2026). Distinguish **task success** (both modalities 100% on tasks when connected) from **run completion**. |
| Programmatic tool calling **~98.7%** | **Correct** | Keep; primary source is Anthropic Nov 2025 post (150k→2k), not third-party blogs. |
| Code Mode `search()` + `execute()` | **Correct direction** | Add Cloudflare numbers: **1.17M** vs **~1k** tokens; date Feb 2026. |
| “CLI decades hardened; MCP timeouts” | **Supported** | Add Scalekit + GitHub cli-proxy as first-party adjacent evidence. |

### `research/05-comparison-matrix.md`

| Current claim | Verdict | Recommended edit |
|---------------|---------|------------------|
| Naive MCP **4×–35×** | **Same as 01** | Change to **4×–32×**; footnote Scalekit 2026. |
| No row for **optimized MCP** | **Gap** | Add column or footnote: optimized MCP (code mode / programmatic / gateway-filtered) → token cost **near CLI** with MCP auth retained. |
| GAX vs optimized MCP table (lines 27–34) | **Mostly valid** | Add row: **Measured token gap (naive)** with Scalekit citation; **Mitigation path** = gateway ~90%, Code Mode ~99.9%, programmatic ~98.7%. |
| “MCP server logs” for audit | **OK** | Note CLI Agent Spec + enterprise MCP OAuth as parallel governance paths for CLI-shaped tools. |

### Not in 01/05 but relevant for Phase 2

- **GitHub cli-proxy (~24%)** is *not* the same as CLI-vs-MCP micro-benchmarks: it removes MCP schemas in an existing agent loop while keeping multi-turn workflows — cite separately from 32× per-task gap.
- **CLI Agent Spec** (https://github.com/cli-agent-spec/cli-agent-spec): 67 failure modes / structured exit codes — supports GAX “registered commands + envelope” without conceding raw bash.
- **Firecrawl** (https://www.firecrawl.dev/blog/mcp-vs-cli): good secondary synthesis; **43 tools ≈ 28k tokens/turn**, 4 servers ≈ **150k+** before first question — aligns with Anthropic example.

---

## GAX positioning (synthesis)

| Benchmark axis | Finding | GAX implication |
|----------------|---------|-----------------|
| Naive MCP tokens | Strongly worse than CLI | **Supported** — lazy `doc`/`search` is mandatory for cost parity |
| MCP not inherently expensive | Code mode / programmatic / gateway | **Supported** — GAX is competing in the **exposure policy** layer, not raw protocol |
| MCP reliability | Remote server timeouts material | **gaxd** connection pooling / adapter health aligns with Scalekit “gateway” pattern |
| Governance | MCP OAuth wins multi-tenant | **Supported** — caps + sidecar auth; don’t claim CLI-level tokens *and* enterprise auth without lazy discovery |
| vs optimized MCP | Similar discovery model | GAX differentiator = **shell ergonomics + cap-per-invoke + envelope v1 + tenancy** in one product surface |

**Conclusion:** Existing research direction is sound; numeric ranges and failure-rate wording need **tighter citations and server-variant precision**. No fundamental GAX thesis change required.

---

## Primary source bibliography (Phase 2 seeds)

1. Scalekit — MCP vs CLI: Benchmarking AI Agent Cost & Reliability — https://www.scalekit.com/blog/mcp-vs-cli-use  
2. scalekit-inc/mcp-vs-cli-benchmark — https://github.com/scalekit-inc/mcp-vs-cli-benchmark  
3. OnlyCLI — MCP Token Trap (35× headline, 93-tool server) — https://onlycli.github.io/OnlyCLI/blog/mcp-token-cost-benchmark/  
4. Anthropic — Code execution with MCP — https://www.anthropic.com/engineering/code-execution-with-mcp  
5. Anthropic — Advanced tool use / Programmatic Tool Calling — https://www.anthropic.com/engineering/advanced-tool-use  
6. Cloudflare — Code Mode MCP — https://blog.cloudflare.com/code-mode-mcp/  
7. GitHub gh-aw-firewall #1885 — cli-proxy token usage — https://github.com/github/gh-aw-firewall/issues/1885  
8. Firecrawl — MCP vs CLI for AI Agents (2026) — https://www.firecrawl.dev/blog/mcp-vs-cli  
9. CLI Agent Spec — https://github.com/cli-agent-spec/cli-agent-spec  
10. odedha-dr/mcp-vs-direct-benchmark — https://github.com/odedha-dr/mcp-vs-direct-benchmark  

---

## Phase 2 — done

- `results/*.json` (8 items, validator PASS)
- [report.md](./report.md)
