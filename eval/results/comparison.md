# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

## Aggregate by modality
| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |
|---|---:|---:|---:|---:|---:|
| cli | 7 | 1.0 | 104 | 0.0 | 0.0 |
| gax | 15 | 1.0 | 137 | 0.8 | 0.8 |
| gax_mcp_bridge | 2 | 1.0 | 732 | 1.0 | 1.0 |
| gax_plan | 2 | 1.0 | 665 | 1.0 | 1.0 |
| mcp_naive_43 | 12 | 1.0 | 44062 | 0.0 | 0.0 |
| mcp_naive_live | 11 | 1.0 | 4483 | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)
- **lowest_median_tokens**: cli
- **highest_success_rate**: cli, mcp_naive_43, mcp_naive_live, gax, gax_mcp_bridge, gax_plan
- **highest_audit_id_rate**: gax_mcp_bridge, gax_plan
- **highest_structured_envelope_rate**: gax_mcp_bridge, gax_plan

## Per-run sample
| task | category | modality | ok | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 116 | 580.44 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 650.09 |
| pr_list | happy_path | mcp_naive_live | True | 4489 | 650.09 |
| pr_list | happy_path | gax | True | 458 | 421.07 |
| pr_list | happy_path | gax_mcp_bridge | True | 457 | 360.78 |
| pr_view_first | happy_path | cli | True | 36 | 314.95 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 352.74 |
| pr_view_first | happy_path | mcp_naive_live | True | 4486 | 352.74 |
| pr_view_first | happy_path | gax | True | 158 | 339.66 |
| echo | happy_path | cli | False | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| echo | happy_path | gax | True | 107 | 2.41 |
| kubectl_mock | happy_path | cli | False | 2 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| kubectl_mock | happy_path | gax | True | 145 | 1.61 |
| aws_mock_list | happy_path | cli | False | 2 | 0.0 |
| aws_mock_list | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| aws_mock_list | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| aws_mock_list | happy_path | gax | True | 138 | 1.39 |
| jira_mock_get | happy_path | cli | False | 2 | 0.0 |
| jira_mock_get | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| jira_mock_get | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| jira_mock_get | happy_path | gax | True | 137 | 1.29 |
| pr_list_invalid_repo | error | cli | True | 61 | 234.49 |
| pr_list_invalid_repo | error | mcp_naive_43 | True | 44069 | 262.63 |
| pr_list_invalid_repo | error | mcp_naive_live | True | 4492 | 262.63 |
| pr_list_invalid_repo | error | gax | True | 137 | 236.96 |
| pr_view_invalid_number | error | cli | True | 43 | 450.8 |
| pr_view_invalid_number | error | mcp_naive_43 | True | 44060 | 504.9 |
| pr_view_invalid_number | error | mcp_naive_live | True | 4483 | 504.9 |
| pr_view_invalid_number | error | gax | True | 131 | 353.54 |
| unknown_command | error | gax | True | 113 | 0.91 |
| policy_denied | error | gax | True | 115 | 0.46 |
| cli_bad_flag | error | cli | True | 263 | 55.25 |
| cli_bad_flag | error | mcp_naive_43 | True | 44062 | 61.88 |
| cli_bad_flag | error | mcp_naive_live | True | 4485 | 61.88 |
| cli_bad_flag | error | gax | True | 340 | 379.77 |
| large_output_truncation | truncation | cli | False | 2 | 0.0 |

*…and 14 more rows in comparison.json*
