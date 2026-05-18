# Comparison matrix

| Dimension | Raw CLI | Naive MCP | Optimized MCP | Hybrid | **GAX** |
|-----------|---------|-----------|--------|---------|
| Discovery in context | Minimal (`--help`) | Heavy (all tool schemas) | Lazy code/search APIs | Two models | **Lazy `doc` / `search` only** |
| Token cost (typical) | Low | High (4×–32×) | Near CLI (1k–2k cited) | Mixed | **Low with `surface=model`** |
| OAuth / per-user auth | Ambient env / keys | Server-side | Server-side | Split | **Sidecar + cap token** |
| Audit trail | Shell history (weak) | MCP server logs | MCP logs | Split | **`audit_id` every invoke** |
| Multi-tenant | Hard | Natural | Natural | Hard for CLI path | **`tenant_id` in cap** |
| Structured output | Ad hoc / `--json` | JSON-RPC | JSON in sandbox | Mixed | **Envelope v1 + schema URI** |
| Composability | Pipes (powerful, risky) | Multi-turn RPC | Code in sandbox | Both | **Typed plan / in-daemon jq** |
| Arbitrary code execution | Yes (`bash`) | No | Sandboxed JS | Often yes locally | **No — registered commands only** |
| Ecosystem | Huge | Growing | Cloud/vendor | Both | **Adapters over both** |
| Maturity | Decades | Early | 2025–2026 | Ops complexity | **Protocol + reference impl** |

## When to use what (pragmatic)

| Scenario | Recommendation |
|----------|----------------|
| Solo dev, local tests, git | Raw CLI or **GAX** with local tenant |
| Enterprise SaaS agent, many users | **GAX** or governed MCP |
| Existing MCP server investment | Wrap as **GAX adapter** |
| Maximum token savings, no governance | Raw CLI (accept risk) |

## GAX vs optimized MCP

| | Optimized MCP (Code Mode / programmatic) | GAX |
|---|------------------------------------------|-----|
| Discovery | `search` / `execute` in sandbox | `gax search` / `gax doc` |
| UX for model | Code/API-like | **Shell-like commands** |
| Governance | MCP server auth | **Cap per invoke + gaxd policy** |
| Composability | JS in sandbox | **plan YAML + jq in daemon** |

GAX is closest to **optimized MCP exposure** plus **CLI mental model** plus **first-class caps/audit/tenancy**.

### Mitigation tiers (cited token reductions)

| Pattern | Approx. reduction | Source |
|---------|-------------------|--------|
| MCP gateway / filtered tools | ~90% | [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use) |
| Programmatic tool calling | ~98.7% (150k→2k example) | [Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp) |
| Cloudflare Code Mode | ~99.9% (1.17M→~1k) | [Cloudflare](https://blog.cloudflare.com/code-mode-mcp/) |

**Eval:** run `python eval/run_comparison.py` — see [10-evaluation.md](./10-evaluation.md).
