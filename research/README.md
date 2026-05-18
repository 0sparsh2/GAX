# Research hub — MCP vs CLI vs GAX

Living documentation for the **MCP vs CLI** investigation and the **GAX** (Governed Agent eXecution) prototype.

## Index

| Doc | Topic |
|-----|--------|
| [01-background-mcp-vs-cli.md](./01-background-mcp-vs-cli.md) | Problem framing, benchmarks, hybrid consensus |
| [02-gax-proposal.md](./02-gax-proposal.md) | GAX thesis: third way beyond hybrid |
| [03-architecture.md](./03-architecture.md) | Planes, components, sequence diagrams |
| [04-protocol-envelope.md](./04-protocol-envelope.md) | Envelope v1, surfaces, caps |
| [05-comparison-matrix.md](./05-comparison-matrix.md) | CLI vs MCP vs hybrid vs GAX |
| [06-implementation-roadmap.md](./06-implementation-roadmap.md) | What is built, what is next |
| [07-prior-art.md](./07-prior-art.md) | OAuth CLIs, CLI Agent Spec, macaroons, Teleport |
| [08-prototype-guide.md](./08-prototype-guide.md) | GAX v0.1 code map, API, how to extend |
| [09-implementation-migration.md](./09-implementation-migration.md) | MCP/CLI usage today, migration paths, adoption |
| [09-oauth-and-plans.md](./09-oauth-and-plans.md) | OAuth device flow + `gax plan run` |
| [10-evaluation.md](./10-evaluation.md) | CLI / MCP / GAX comparison harness |
| [11-project-completion.md](./11-project-completion.md) | Final deliverables & eval conclusion |

## Diagrams

Mermaid sources (render in GitHub / VS Code):

- [diagrams/architecture.mmd](./diagrams/architecture.mmd) — System context
- [diagrams/sequence-invoke.mmd](./diagrams/sequence-invoke.mmd) — Invocation flow
- [diagrams/planes.mmd](./diagrams/planes.mmd) — Control / invocation / data planes

### Diagrams (PNG)

Pre-rendered exports (dark theme, transparent background) for docs and slides:

| Diagram | PNG | Mermaid source |
|---------|-----|----------------|
| Architecture | [architecture.png](./diagrams/png/architecture.png) | [architecture.mmd](./diagrams/architecture.mmd) |
| Invocation sequence | [sequence-invoke.png](./diagrams/png/sequence-invoke.png) | [sequence-invoke.mmd](./diagrams/sequence-invoke.mmd) |
| Three planes | [planes.png](./diagrams/png/planes.png) | [planes.mmd](./diagrams/planes.mmd) |

Regenerate: `npx -y @mermaid-js/mermaid-cli -i research/diagrams/<name>.mmd -o research/diagrams/png/<name>.png -t dark -b transparent`

## Code

Prototype implementation: [`../gax/`](../gax/)

## Benchmark research (deep-research)

- [../mcp_vs_cli_benchmarks_2026/](../mcp_vs_cli_benchmarks_2026/) — Phase 1–2 complete: [report.md](../mcp_vs_cli_benchmarks_2026/report.md), `results/*.json`, [phase1-findings.md](../mcp_vs_cli_benchmarks_2026/phase1-findings.md)

## Deep research runs

Structured runs (outline + JSON + report) live at repo root, e.g.:

- [`gax_implementation_migration_2026/`](../gax_implementation_migration_2026/) — implementation & migration (May 2026)

## How to extend

Add new `.md` files here and link them from this index. Keep Mermaid in `diagrams/*.mmd` and reference from markdown for single source of truth.
