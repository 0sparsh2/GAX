# Background: MCP vs CLI for AI agents

## What each is

**MCP (Model Context Protocol)** — Open JSON-RPC protocol (Anthropic, late 2024). Servers advertise typed tools, resources, and prompts; clients discover schemas and invoke tools with structured parameters and JSON responses. Focus: interoperability, discoverability, governed access.

**CLI** — Commands via shell (`gh`, `git`, `pytest`). Agent constructs strings; stdout/stderr returns as text (sometimes JSON with flags). Focus: composability, maturity, low context overhead.

## Why “CLI wins” in benchmarks (naive setups)

| Factor | Effect |
|--------|--------|
| Tool schema injection | **43-tool** Copilot MCP ~44k/task; **93-tool** github-mcp-server ~55k idle (see phase1-findings) vs hundreds for `gh` |
| Multi-turn schema repeat | Schemas re-sent or partially repeated each turn |
| Structured JSON responses | Large tool outputs re-injected into context |
| Ecosystem maturity | Shell/CLI decades hardened; early MCP servers: timeouts, connection failures |

Reported ranges: **4×–32×** higher token usage for naive MCP vs CLI on comparable tasks ([Scalekit benchmark](https://www.scalekit.com/blog/mcp-vs-cli-use), [repo](https://github.com/scalekit-inc/mcp-vs-cli-benchmark)). Example: **1,365** tokens (CLI) vs **44,026** (MCP) for a simple “repo language” task (~32×). Scalekit reports **28%** MCP run failure vs **100%** CLI completion in their 75-run GitHub suite (Claude Sonnet 4).

Deep dive: [mcp_vs_cli_benchmarks_2026/phase1-findings.md](../mcp_vs_cli_benchmarks_2026/phase1-findings.md).

## Where MCP wins

- **Security & governance** — OAuth 2.1, per-tool scopes, centralized audit
- **Typed interfaces** — JSON Schema in/out; less parsing ambiguity
- **Stateful sessions** — Long-lived MCP connection vs one-shot processes
- **Cross-system orchestration** — SaaS without a single shell environment

## Optimized MCP (narrows token gap)

- **Programmatic tool calling** ([Anthropic](https://anthropic.com/engineering/code-execution-with-mcp)) — filesystem/SDK discovery; example workflow ~150k → ~2k tokens (~98.7% reduction cited)
- **Code Mode** ([Cloudflare](https://blog.cloudflare.com/code-mode-mcp/)) — `search()` + `execute()` over OpenAPI; ~1k tokens vs ~1.17M native MCP for large APIs

Insight: overhead is often **client exposure policy**, not MCP inherently.

## Hybrid consensus

Use **CLI** for inner-loop dev (tests, git, local files). Use **MCP** for outer-loop multi-tenant SaaS. Use **HTTP APIs** where SDKs exist.

**Open question (this project):** Can one surface combine CLI ergonomics + MCP governance without hybrid operational complexity?

→ See [02-gax-proposal.md](./02-gax-proposal.md)
