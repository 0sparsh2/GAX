# Ablation study & framework comparisons

Extends the base harness (`eval/run_comparison.py`) with **`--extended`**: GAX ablations, optimized-MCP / CLI Agent Spec / logging-proxy comparisons, and **multi-MCP schema probes**.

## Run

```bash
pip install -r eval/requirements.txt
cd gax && pip install -e ".[dev]"

# CI-safe (mock MCP servers only)
python ../eval/run_comparison.py --mock-only --extended

# Full (GITHUB_TOKEN for live github MCP + gh tasks)
python ../eval/run_comparison.py --live-mcp --extended
```

Outputs:

- `eval/results/comparison.json` — all rows
- `eval/results/extended-comparison.md` — ablation/comparison summary
- `eval/results/comparison.md` — base modalities

## Ablation modalities

| Modality | What it isolates |
|----------|------------------|
| `gax` (baseline) | Cap + envelope v1 + lazy doc |
| `gax_ablation_no_cap` | **policy_denied** task with permissive cap (invoke allowed) vs restricted `gax` |
| `gax_ablation_no_envelope` | Same invoke; agent context gets **raw JSON**, not envelope v1 |
| `gax_ablation_schema_preload` | GAX transcript **+ 43-tool schema tax** (~44k fixture) |

## Comparison modalities

| Modality | Models |
|----------|--------|
| `programmatic_mcp` | Anthropic / Cloudflare **code mode** (~1k tok overhead + code snippet) |
| `cli_agent_spec` | [CLI Agent Spec](https://github.com/cli-agent-spec/cli-agent-spec)–style structured `cli-agent-result/v1` |
| `cli_logged_proxy` | Raw `gh` + **post-hoc** synthetic audit log line (not pre-invoke enforcement) |

Answers reviewer question: **“Why not gh + logging proxy?”** — compare `cli`, `cli_logged_proxy`, and `gax` on tokens, `audit_id_rate`, and `structured_envelope_rate`.

## Multi-MCP catalog

Servers in `eval/fixtures/mcp_servers.yaml`:

| ID | Package / mock |
|----|----------------|
| `mock_github` | CI mock stdio |
| `mock_filesystem` | CI mock stdio (3 tools) |
| `github` | `@modelcontextprotocol/server-github` |
| `filesystem` | `@modelcontextprotocol/server-filesystem` |
| `fetch` | `@modelcontextprotocol/server-fetch` |
| `memory` | `@modelcontextprotocol/server-memory` |

Per-task rows: `mcp_live_<server_id>` with measured `tools/list` token cost (or fixture when `--mock-only`).

`gax_mcp_bridge` remains the governed path for GitHub MCP (schema not in prompt).

## How to read results

- **Tokens:** Expect `gax_ablation_schema_preload` ≈ `mcp_naive_43`; `programmatic_mcp` ≪ naive MCP.
- **Governance:** `gax` / bridge keep `audit_id_rate`; `cli_logged_proxy` does not enforce caps (synthetic post-hoc id only).
- **Policy:** On task `policy_denied`, `gax` fails closed; `gax_ablation_no_cap` succeeds — shows cap value.

No weighted composite. See [eval/METHODOLOGY.md](../eval/METHODOLOGY.md).
