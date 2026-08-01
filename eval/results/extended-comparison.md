# Extended evaluation — ablations, comparisons, MCP catalog

See [docs/ABLATIONS.md](../docs/ABLATIONS.md) and [METHODOLOGY.md](../METHODOLOGY.md).

## MCP server schema probe
| server | tools | schema_tokens | status |
|---|---:|---:|---|
| mock_github | 1 | 52 | ok |
| mock_filesystem | 3 | 130 | ok |
| github | 43 | 44026 | fixture |
| filesystem | — | — | skipped |
| fetch | — | — | skipped |
| memory | — | — | skipped |

## Ablation modalities (median tokens)
- **gax_ablation_no_cap**: median 275 tok, audit 1.0, envelope 1.0
- **gax_ablation_no_envelope**: median 74 tok, audit 1.0, envelope 0.0
- **gax_ablation_schema_preload**: median 44165 tok, audit 1.0, envelope 1.0

## Comparison modalities
- **programmatic_mcp**: median 1084 tok, completion 1.0
- **cli_agent_spec**: median 95 tok, completion 0.4
- **cli_logged_proxy**: median 93 tok, completion 0.4

## Multi-MCP naive (per server)
- **mcp_live_github**: median 44062 tok
- **mcp_live_mock_filesystem**: median 168 tok
- **mcp_live_mock_github**: median 90 tok

## Pareto (all modalities in this run)
- **highest_completion_rate**: gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, gax_ablation_no_cap
- **highest_expected_outcome_rate**: cli, mcp_naive_43, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, gax_ablation_no_cap, gax_plan
- **highest_fail_closed_rate**: gax

**Interpretation:** `gax_ablation_schema_preload` shows cost of naive schema tax on GAX path; `gax_ablation_no_envelope` drops structured envelope rate; `gax_ablation_no_cap` on `policy_denied` shows permissive cap allows invoke. `cli_logged_proxy` adds post-hoc log tokens but not pre-invoke enforcement.
