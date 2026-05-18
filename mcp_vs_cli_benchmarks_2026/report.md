# MCP vs CLI for AI agents — Deep research report

**Topic:** Token costs, reliability benchmarks, optimized MCP patterns (2024–2026)  
**Methodology:** [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills), [RhinoInsight](https://arxiv.org/html/2511.18743v1) phased outline → JSON → synthesis. Phase 1 web citation pass + Phase 2 structured items + local GAX eval.

## Table of contents

1. [Scalekit MCP vs CLI benchmark](#scalekit-mcp-vs-cli-benchmark)
2. [Naive MCP schema overhead](#naive-mcp-schema-overhead)
3. [CLI token baseline](#cli-token-baseline)
4. [MCP reliability and failure modes](#mcp-reliability-and-failure-modes)
5. [Optimized MCP — programmatic tool calling](#optimized-mcp--programmatic-tool-calling)
6. [Optimized MCP — Cloudflare Code Mode](#optimized-mcp--cloudflare-code-mode)
7. [Governance and security trade-off](#governance-and-security-trade-off)
8. [GAX positioning vs benchmarks](#gax-positioning-vs-benchmarks)
9. [Synthesis & recommendation](#synthesis--recommendation)

---

## Scalekit MCP vs CLI benchmark

**Category:** Empirical benchmark

Scalekit ran **75** trials on five read-only GitHub tasks with **Claude Sonnet 4**, comparing **GitHub Copilot MCP (43 tools)** to **gh CLI** and **CLI+Skills**. On the simplest task (“repo language”), CLI used **1,365** tokens vs MCP **44,026** (~**32×**). Across the suite, MCP used **4×–32×** more tokens. **28%** of MCP **runs** failed (`ConnectTimeout` to remote Copilot MCP; **18/25**), while CLI completed **25/25** runs. When connected, task-level outcomes were successful for both modalities on the measured tasks.

| Metric | Value |
|--------|-------|
| Runs | 75 |
| MCP tools | 43 |
| Token ratio | 4×–32× |
| MCP run failure | 28% |
| CLI run completion | 100% |

**Sources:** [Scalekit blog](https://www.scalekit.com/blog/mcp-vs-cli-use), [benchmark repo](https://github.com/scalekit-inc/mcp-vs-cli-benchmark)

**GAX implication:** Lazy discovery and sidecar execution are mandatory for cost parity; local `gaxd` mitigates remote timeout class.

---

## Naive MCP schema overhead

**Category:** Mechanism

Overhead is driven by injecting full **tools/list** schemas each turn. **43-tool** Copilot MCP aligns with ~**44k** tokens on simple tasks; **93-tool** github-mcp-server reports ~**55k** idle. Multi-server stacks reach **~143k** tokens before user work (OnlyCLI / Firecrawl).

**GAX implication:** Never preload full registry; use `gax search` / `gax doc` (~80–250 tokens per discovery).

**Doc fix applied:** Split 43-tool vs 93-tool in `research/01-background-mcp-vs-cli.md`.

---

## CLI token baseline

**Category:** Mechanism

CLI agents pay for commands and output, not bulk schemas—typically **hundreds to low thousands** of tokens per GitHub task in Scalekit. **CLI+Skills** (~800 tokens) improved tool-call efficiency. Trade-off: ambient credentials, weak audit.

**GAX implication:** Match CLI invocation size; add envelope, `audit_id`, caps.

---

## MCP reliability and failure modes

**Category:** Reliability

Distinguish **run completion** (infrastructure) from **task success** (logic when connected). Scalekit: **28%** MCP run failures vs CLI **100%** completion. GitHub **cli-proxy** ~**24%** workflow token reduction is a different layer (schema removal in agent loop). **CLI Agent Spec** catalogs **67** failure modes for structured agent CLIs.

**GAX implication:** Semantic exit codes + `error.kind` in envelope; eval uses 0.72 reliability prior for naive MCP until `--live-mcp` passes.

---

## Optimized MCP — programmatic tool calling

**Category:** Mitigation

Anthropic **code execution with MCP** (Nov 2025): filesystem discovery, sandbox orchestration, example **150k → 2k** tokens (**98.7%**). **Programmatic Tool Calling** in Claude SDK.

**GAX implication:** Same “don’t load unused tools” axis; GAX adds shell ergonomics + cap-per-invoke without in-model JS sandbox.

---

## Optimized MCP — Cloudflare Code Mode

**Category:** Mitigation

Two tools (`search`, `execute`) over full API: **~1k** vs **~1.17M** native MCP tokens (**99.9%** reduction). Minimal-params MCP ~**244k**.

**GAX implication:** `gax search`/`gax doc` analogous at CLI UX; policy + audit remain GAX differentiators.

---

## Governance and security trade-off

**Category:** Enterprise

MCP: OAuth, per-user scopes, audit. CLI: ambient tokens, shell risk. **GAX:** device OAuth, macaroons/JWT caps, `policy.yaml`, OTEL audit export.

**GAX implication:** Default for multi-tenant agents; CLI for ungoverned local-only work.

---

## GAX positioning vs benchmarks

**Category:** Synthesis

| Surface | Token cost (naive) | Governance | Structure |
|---------|-------------------|------------|-------------|
| CLI | Best | Weak | Medium |
| Naive MCP | Worst | Medium | High |
| Optimized MCP | Near CLI | High | High |
| **GAX** | Near CLI (eval) | **Strong** | **Strong** |

**Local eval** (`eval/run_comparison.py`, weighted composite):

| Modality | Mean score |
|----------|------------|
| **gax** | **0.986** |
| gax_plan | 0.984 |
| cli | 0.678 |
| mcp_naive_43 | 0.561 |

Run with live MCP: `python eval/run_comparison.py --live-mcp` (requires `GITHUB_TOKEN`).

---

## Synthesis & recommendation

1. **Do not expose naive MCP tool catalogs to the model** — benchmarks and vendor optimizations agree.
2. **Do not rely on raw shell for enterprise agents** — governance and audit gaps dominate.
3. **Adopt GAX (or equivalent)** when you need **CLI ergonomics + MCP-class control + structured envelopes** in one surface.
4. **Wrap existing MCP servers** as GAX adapters (stub: `gax/adapters/mcp_bridge.py`) rather than maintaining hybrid agent prompts.

**Next research/engineering:** Phase 3 live MCP in all eval tasks; provider token APIs; OpenAPI → manifest generator; full MCP bridge.

---

*Generated from `mcp_vs_cli_benchmarks_2026/results/*.json`. Re-validate:*

```bash
python3 deep-research/scripts/validate_json.py \
  -f mcp_vs_cli_benchmarks_2026/fields.yaml \
  -j mcp_vs_cli_benchmarks_2026/results/*.json
```
