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

Answers reviewer question: **“Why not gh + logging proxy?”** — compare `cli`, `cli_logged_proxy`, and `gax`. The decisive axis is **`fail_closed_rate`**, not audit rate: a proxy can synthesize an `audit_id` after the fact, but it logs a command that *already ran*. Only `gax*` modalities are scored on `fail_closed` at all, because only they have a pre-invoke enforcement step.

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

- **Tokens:** use the **paired** table in `comparison.md`. Per-modality medians run over different task subsets and are not head-to-head.
- **Governance:** `gax` / bridge enforce pre-invoke (`fail_closed_rate`); `cli_logged_proxy` does not — its `audit_id` is synthetic and post-hoc.
- **`gax_ablation_schema_preload` is arithmetic, not an ablation** (`gax` + a 44k constant); it is queued for removal under W4.
- **Policy:** On task `policy_denied`, `gax` fails closed; `gax_ablation_no_cap` succeeds — shows cap value.

No weighted composite. See [eval/METHODOLOGY.md](../eval/METHODOLOGY.md).
