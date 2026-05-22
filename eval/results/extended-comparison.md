# Extended evaluation — ablations, comparisons, MCP catalog

See [docs/ABLATIONS.md](../docs/ABLATIONS.md) and [METHODOLOGY.md](../METHODOLOGY.md).

## MCP server schema probe
| server | tools | schema_tokens | status |
|---|---:|---:|---|
| mock_github | 1 | 52 | ok |
| mock_filesystem | 3 | 130 | ok |
| github | 26 | 4450 | ok |
| filesystem | 14 | 3127 | ok |
| fetch | — | — | fail |
| memory | 9 | 2676 | ok |

## Ablation modalities (median tokens)
- **gax_ablation_no_cap**: median 282 tok, audit 1.0, envelope 1.0
- **gax_ablation_no_envelope**: median 74 tok, audit 1.0, envelope 0.0
- **gax_ablation_schema_preload**: median 44165 tok, audit 1.0, envelope 1.0

## Comparison modalities
- **programmatic_mcp**: median 1088 tok, success 1.0
- **cli_agent_spec**: median 170 tok, success 0.5
- **cli_logged_proxy**: median 159 tok, success 0.5

## Multi-MCP naive (per server)
- **mcp_live_filesystem**: median 3166 tok
- **mcp_live_github**: median 4489 tok
- **mcp_live_memory**: median 2715 tok
- **mcp_live_mock_filesystem**: median 171 tok
- **mcp_live_mock_github**: median 93 tok

## Pareto (all modalities in this run)
- **lowest_median_tokens**: gax_ablation_no_envelope
- **highest_success_rate**: cli, mcp_naive_43, mcp_naive_live, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, mcp_live_filesystem, mcp_live_memory, gax_ablation_no_cap, gax_plan
- **highest_audit_id_rate**: gax_mcp_bridge, gax_ablation_no_envelope, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan
- **highest_structured_envelope_rate**: gax_mcp_bridge, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan

**Interpretation:** `gax_ablation_schema_preload` shows cost of naive schema tax on GAX path; `gax_ablation_no_envelope` drops structured envelope rate; `gax_ablation_no_cap` on `policy_denied` shows permissive cap allows invoke. `cli_logged_proxy` adds post-hoc log tokens but not pre-invoke enforcement.
