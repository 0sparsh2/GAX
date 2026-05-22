# ACSP — Agent Capability Shell Protocol

**ACSP** is the formal name for the **GAX** (Governed Agent eXecution) protocol implemented in this repository.

## Documents

| Doc | Description |
|-----|-------------|
| **[ACSP-1.0.md](./ACSP-1.0.md)** | **Implementation-agnostic protocol spec** |
| [CONFORMANCE.md](./CONFORMANCE.md) | Teaser conformance tests (reference impl) |
| [protocol.md](./protocol.md) | Normative overview: planes, envelope, capabilities |
| [envelope-v1.md](./envelope-v1.md) | Response envelope schema |
| [discovery.md](./discovery.md) | Lazy `search` / `doc` / `schema` |
| [../gax/README.md](../../gax/README.md) | Reference implementation |

## Status

- **Implementation:** `gax` Python package v0.4+
- **Evaluation:** `eval/run_comparison.py`, `eval/run_full.py`
- **Research:** `research/`, `mcp_vs_cli_benchmarks_2026/report.md`

## Why ACSP / GAX

See [PUBLIC_NARRATIVE.md](../PUBLIC_NARRATIVE.md): external benchmarks (Scalekit, Anthropic, Cloudflare) vs our harness vs `SAMPLE_RUN` agent receipts. ACSP adds **CLI ergonomics + cap-per-invoke + audit** in one sidecar without naive MCP schema preload.
