# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

**Live MCP probe:** 26 tools, **4450** schema tokens (measured `tools/list`).

Publishable summary: [live-run-summary.md](./live-run-summary.md)

## Aggregate by modality
| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |
|---|---:|---:|---:|---:|---:|
| cli | 7 | 1.0 | 104 | 0.0 | 0.0 |
| gax | 15 | 1.0 | 138 | 0.8 | 0.8 |
| gax_mcp_bridge | 2 | 1.0 | 734 | 1.0 | 1.0 |
| gax_plan | 2 | 1.0 | 670 | 1.0 | 1.0 |
| mcp_naive_43 | 12 | 1.0 | 44062 | 0.0 | 0.0 |
| mcp_naive_live | 11 | 1.0 | 4483 | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)
- **lowest_median_tokens**: cli
- **highest_success_rate**: cli, mcp_naive_43, mcp_naive_live, gax, gax_mcp_bridge, gax_plan
- **highest_audit_id_rate**: gax_mcp_bridge, gax_plan
- **highest_structured_envelope_rate**: gax_mcp_bridge, gax_plan

## Per-run sample
| task | category | modality | success | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 116 | 280.18 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 313.8 |
| pr_list | happy_path | mcp_naive_live | True | 4489 | 313.8 |
| pr_list | happy_path | gax | True | 459 | 396.32 |
| pr_list | happy_path | gax_mcp_bridge | True | 456 | 316.83 |
| pr_view_first | happy_path | cli | True | 36 | 308.94 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 346.01 |
| pr_view_first | happy_path | mcp_naive_live | True | 4486 | 346.01 |
| pr_view_first | happy_path | gax | True | 160 | 287.01 |
| echo | happy_path | cli | False | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| echo | happy_path | gax | True | 111 | 1.34 |
| kubectl_mock | happy_path | cli | False | 2 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| kubectl_mock | happy_path | gax | True | 145 | 0.97 |
| aws_mock_list | happy_path | cli | False | 2 | 0.0 |
| aws_mock_list | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| aws_mock_list | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| aws_mock_list | happy_path | gax | True | 138 | 1.28 |
| jira_mock_get | happy_path | cli | False | 2 | 0.0 |
| jira_mock_get | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| jira_mock_get | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| jira_mock_get | happy_path | gax | True | 138 | 0.97 |
| pr_list_invalid_repo | error | cli | True | 61 | 224.95 |
| pr_list_invalid_repo | error | mcp_naive_43 | True | 44069 | 251.94 |
| pr_list_invalid_repo | error | mcp_naive_live | True | 4492 | 251.94 |
| pr_list_invalid_repo | error | gax | True | 136 | 217.51 |
| pr_view_invalid_number | error | cli | True | 43 | 319.98 |
| pr_view_invalid_number | error | mcp_naive_43 | True | 44060 | 358.38 |
| pr_view_invalid_number | error | mcp_naive_live | True | 4483 | 358.38 |
| pr_view_invalid_number | error | gax | True | 128 | 302.74 |
| unknown_command | error | gax | True | 114 | 0.33 |
| policy_denied | error | gax | True | 114 | 0.24 |
| cli_bad_flag | error | cli | True | 263 | 35.25 |
| cli_bad_flag | error | mcp_naive_43 | True | 44062 | 39.48 |
| cli_bad_flag | error | mcp_naive_live | True | 4485 | 39.48 |
| cli_bad_flag | error | gax | True | 344 | 282.32 |
| large_output_truncation | truncation | cli | False | 2 | 0.0 |

*…and 14 more rows in comparison.json*
