# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

Publishable summary: [live-run-summary.md](./live-run-summary.md)

## Aggregate by modality
| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |
|---|---:|---:|---:|---:|---:|
| cli | 6 | 1.0 | 113 | 0.0 | 0.0 |
| cli_agent_spec | 5 | 0.4 | 95 | 0.0 | 0.0 |
| cli_logged_proxy | 5 | 0.4 | 93 | 0.0 | 0.0 |
| gax | 15 | 1.0 | 137 | 0.8 | 0.8 |
| gax_ablation_no_cap | 1 | 1.0 | 282 | 1.0 | 1.0 |
| gax_ablation_no_envelope | 10 | 0.8 | 74 | 1.0 | 0.0 |
| gax_ablation_schema_preload | 12 | 0.6667 | 44165 | 1.0 | 1.0 |
| gax_mcp_bridge | 1 | 1.0 | 467 | 1.0 | 1.0 |
| gax_plan | 2 | 1.0 | 678 | 1.0 | 1.0 |
| mcp_live_github | 5 | 1.0 | 44062 | 0.0 | 0.0 |
| mcp_live_mock_filesystem | 5 | 1.0 | 168 | 0.0 | 0.0 |
| mcp_live_mock_github | 5 | 1.0 | 90 | 0.0 | 0.0 |
| mcp_naive_43 | 11 | 1.0 | 44060 | 0.0 | 0.0 |
| programmatic_mcp | 5 | 1.0 | 1084 | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)
- **lowest_median_tokens**: gax_ablation_no_envelope
- **highest_success_rate**: cli, mcp_naive_43, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, gax_ablation_no_cap, gax_plan
- **highest_audit_id_rate**: gax_mcp_bridge, gax_ablation_no_envelope, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan
- **highest_structured_envelope_rate**: gax_mcp_bridge, gax_ablation_schema_preload, gax_ablation_no_cap, gax_plan

## Per-run sample
| task | category | modality | success | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 127 | 453.38 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 507.79 |
| pr_list | happy_path | gax | True | 468 | 318.81 |
| pr_list | happy_path | gax_mcp_bridge | True | 467 | 336.37 |
| pr_list | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| pr_list | happy_path | gax_ablation_no_envelope | True | 337 | 331.23 |
| pr_list | happy_path | gax_ablation_schema_preload | True | 44496 | 313.17 |
| pr_list | happy_path | programmatic_mcp | True | 1088 | 476.05 |
| pr_list | happy_path | cli_agent_spec | True | 170 | 358.43 |
| pr_list | happy_path | cli_logged_proxy | True | 159 | 309.48 |
| pr_list | happy_path | mcp_live_mock_github | True | 93 | 507.79 |
| pr_list | happy_path | mcp_live_mock_filesystem | True | 171 | 507.79 |
| pr_list | happy_path | mcp_live_github | True | 44065 | 507.79 |
| pr_list | happy_path | mcp_live_filesystem | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_memory | False | 0 | 0.0 |
| pr_view_first | happy_path | cli | True | 36 | 293.64 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 328.88 |
| pr_view_first | happy_path | gax | True | 162 | 313.38 |
| pr_view_first | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| pr_view_first | happy_path | gax_ablation_no_envelope | True | 74 | 354.55 |
| pr_view_first | happy_path | gax_ablation_schema_preload | True | 44185 | 795.7 |
| pr_view_first | happy_path | programmatic_mcp | True | 1084 | 308.32 |
| pr_view_first | happy_path | cli_agent_spec | True | 71 | 296.96 |
| pr_view_first | happy_path | cli_logged_proxy | True | 68 | 290.08 |
| pr_view_first | happy_path | mcp_live_mock_github | True | 90 | 328.88 |
| pr_view_first | happy_path | mcp_live_mock_filesystem | True | 168 | 328.88 |
| pr_view_first | happy_path | mcp_live_github | True | 44062 | 328.88 |
| pr_view_first | happy_path | mcp_live_filesystem | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_memory | False | 0 | 0.0 |
| echo | happy_path | cli | False | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | gax | True | 110 | 1.72 |
| echo | happy_path | gax_ablation_no_cap | False | 0 | 0.0 |
| echo | happy_path | gax_ablation_no_envelope | True | 25 | 0.8 |
| echo | happy_path | gax_ablation_schema_preload | True | 44135 | 1.02 |
| kubectl_mock | happy_path | cli | False | 2 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| kubectl_mock | happy_path | gax | True | 145 | 0.79 |

*…and 84 more rows in comparison.json*
