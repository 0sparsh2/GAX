# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

**Live MCP probe:** 26 tools, **4450** schema tokens (measured `tools/list`).

Publishable summary: [live-run-summary.md](./live-run-summary.md)

## Aggregate by modality
| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |
|---|---:|---:|---:|---:|---:|
| cli | 7 | 1.0 | 113 | 0.0 | 0.0 |
| cli_agent_spec | 6 | 0.5 | 170 | 0.0 | 0.0 |
| cli_logged_proxy | 6 | 0.5 | 159 | 0.0 | 0.0 |
| gax | 15 | 1.0 | 136 | 0.8 | 0.8 |
| gax_ablation_no_cap | 1 | 1.0 | 282 | 1.0 | 1.0 |
| gax_ablation_no_envelope | 11 | 0.8182 | 74 | 1.0 | 0.0 |
| gax_ablation_schema_preload | 13 | 0.6923 | 44165 | 1.0 | 1.0 |
| gax_mcp_bridge | 2 | 1.0 | 753 | 1.0 | 1.0 |
| gax_plan | 2 | 1.0 | 673 | 1.0 | 1.0 |
| mcp_live_filesystem | 6 | 1.0 | 3166 | 0.0 | 0.0 |
| mcp_live_github | 6 | 1.0 | 4489 | 0.0 | 0.0 |
| mcp_live_memory | 6 | 1.0 | 2715 | 0.0 | 0.0 |
| mcp_live_mock_filesystem | 6 | 1.0 | 171 | 0.0 | 0.0 |
| mcp_live_mock_github | 6 | 1.0 | 93 | 0.0 | 0.0 |
| mcp_naive_43 | 12 | 1.0 | 44062 | 0.0 | 0.0 |
| mcp_naive_live | 11 | 1.0 | 4483 | 0.0 | 0.0 |
| programmatic_mcp | 6 | 1.0 | 1088 | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)
- **lowest_median_tokens**: gax_ablation_no_envelope
- **highest_success_rate**: cli, mcp_naive_43, mcp_naive_live, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, mcp_live_filesystem, mcp_live_memory, gax_ablation_no_cap, gax_plan
- **highest_audit_id_rate**: gax_mcp_bridge, gax_ablation_no_envelope, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan
- **highest_structured_envelope_rate**: gax_mcp_bridge, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan

## Per-run sample
| task | category | modality | success | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 127 | 424.08 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 474.97 |
| pr_list | happy_path | mcp_naive_live | True | 4489 | 474.97 |
| pr_list | happy_path | gax | True | 468 | 295.75 |
| pr_list | happy_path | gax_mcp_bridge | True | 467 | 303.7 |
| pr_list | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| pr_list | happy_path | gax_ablation_no_envelope | True | 337 | 286.73 |
| pr_list | happy_path | gax_ablation_schema_preload | True | 44495 | 330.35 |
| pr_list | happy_path | programmatic_mcp | True | 1088 | 445.28 |
| pr_list | happy_path | cli_agent_spec | True | 170 | 294.62 |
| pr_list | happy_path | cli_logged_proxy | True | 159 | 265.99 |
| pr_list | happy_path | mcp_live_mock_github | True | 93 | 474.97 |
| pr_list | happy_path | mcp_live_mock_filesystem | True | 171 | 474.97 |
| pr_list | happy_path | mcp_live_github | True | 4489 | 474.97 |
| pr_list | happy_path | mcp_live_filesystem | True | 3166 | 474.97 |
| pr_list | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_memory | True | 2715 | 474.97 |
| pr_view_first | happy_path | cli | True | 36 | 265.8 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 297.7 |
| pr_view_first | happy_path | mcp_naive_live | True | 4486 | 297.7 |
| pr_view_first | happy_path | gax | True | 162 | 278.22 |
| pr_view_first | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| pr_view_first | happy_path | gax_ablation_no_envelope | True | 74 | 295.68 |
| pr_view_first | happy_path | gax_ablation_schema_preload | True | 44189 | 262.87 |
| pr_view_first | happy_path | programmatic_mcp | True | 1084 | 279.09 |
| pr_view_first | happy_path | cli_agent_spec | True | 71 | 1362.59 |
| pr_view_first | happy_path | cli_logged_proxy | True | 68 | 284.51 |
| pr_view_first | happy_path | mcp_live_mock_github | True | 90 | 297.7 |
| pr_view_first | happy_path | mcp_live_mock_filesystem | True | 168 | 297.7 |
| pr_view_first | happy_path | mcp_live_github | True | 4486 | 297.7 |
| pr_view_first | happy_path | mcp_live_filesystem | True | 3163 | 297.7 |
| pr_view_first | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_memory | True | 2712 | 297.7 |
| echo | happy_path | cli | False | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| echo | happy_path | gax | True | 109 | 3.29 |
| echo | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| echo | happy_path | gax_ablation_no_envelope | True | 25 | 2.09 |
| echo | happy_path | gax_ablation_schema_preload | True | 44136 | 1.63 |

*…and 110 more rows in comparison.json*
