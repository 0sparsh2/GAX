# ACSP — Agent Capability Shell Protocol

**ACSP** is the formal name for the **GAX** (Governed Agent eXecution) protocol implemented in this repository.

## Documents

| Doc | Description |
|-----|-------------|
| [protocol.md](./protocol.md) | Normative overview: planes, envelope, capabilities |
| [envelope-v1.md](./envelope-v1.md) | Response envelope schema |
| [discovery.md](./discovery.md) | Lazy `search` / `doc` / `schema` |
| [../gax/README.md](../../gax/README.md) | Reference implementation |

## Status

- **Implementation:** `gax` Python package v0.4+
- **Evaluation:** `eval/run_comparison.py`, `eval/run_full.py`
- **Research:** `research/`, `mcp_vs_cli_benchmarks_2026/report.md`

## Why ACSP / GAX

Benchmarks show naive MCP is **4×–32×** more token-expensive than CLI; optimized MCP closes the gap. ACSP adds **CLI ergonomics + cap-per-invoke + audit** in one surface without hybrid agent prompts.
