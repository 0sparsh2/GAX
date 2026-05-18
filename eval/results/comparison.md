# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

## Aggregate by modality
| modality | n | success_rate | median_tokens | audit_id_rate | structured_envelope_rate |
|---|---:|---:|---:|---:|---:|
| cli | 7 | 1.0 | 104 | 0.0 | 0.0 |
| gax | 15 | 1.0 | 137 | 0.8 | 0.8 |
| gax_plan | 2 | 1.0 | 656 | 1.0 | 1.0 |
| mcp_naive_43 | 12 | 1.0 | 44062 | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)
- **lowest_median_tokens**: cli
- **highest_success_rate**: cli, mcp_naive_43, gax, gax_plan
- **highest_audit_id_rate**: gax_plan
- **highest_structured_envelope_rate**: gax_plan

## Per-run sample
| task | category | modality | ok | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 116 | 464.13 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 519.83 |
| pr_list | happy_path | gax | True | 456 | 1338.87 |
| pr_list | happy_path | gax_mcp_bridge | False | 120 | 0.0 |
| pr_view_first | happy_path | cli | True | 36 | 369.31 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 413.63 |
| pr_view_first | happy_path | gax | True | 159 | 375.06 |
| echo | happy_path | cli | False | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | gax | True | 112 | 1.45 |
| kubectl_mock | happy_path | cli | False | 2 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| kubectl_mock | happy_path | gax | True | 143 | 1.06 |
| aws_mock_list | happy_path | cli | False | 2 | 0.0 |
| aws_mock_list | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| aws_mock_list | happy_path | gax | True | 137 | 0.95 |
| jira_mock_get | happy_path | cli | False | 2 | 0.0 |
| jira_mock_get | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| jira_mock_get | happy_path | gax | True | 139 | 0.93 |
| pr_list_invalid_repo | error | cli | True | 61 | 369.87 |
| pr_list_invalid_repo | error | mcp_naive_43 | True | 44069 | 414.25 |
| pr_list_invalid_repo | error | gax | True | 135 | 331.77 |
| pr_view_invalid_number | error | cli | True | 43 | 405.13 |
| pr_view_invalid_number | error | mcp_naive_43 | True | 44060 | 453.75 |
| pr_view_invalid_number | error | gax | True | 127 | 386.73 |
| unknown_command | error | gax | True | 114 | 0.84 |
| policy_denied | error | gax | True | 117 | 0.43 |
| cli_bad_flag | error | cli | True | 263 | 54.08 |
| cli_bad_flag | error | mcp_naive_43 | True | 44062 | 60.57 |
| cli_bad_flag | error | gax | True | 341 | 366.5 |
| large_output_truncation | truncation | cli | False | 2 | 0.0 |
| large_output_truncation | truncation | mcp_naive_43 | True | 44049 | 0.0 |
| large_output_truncation | truncation | gax | True | 216 | 3.41 |
| discovery_only | discovery | gax | True | 24 | 0.5 |
| search_stub | discovery | gax | True | 23 | 0.5 |
| multi_turn_pr_workflow | multi_turn | gax | True | 586 | 781.13 |
| multi_turn_pr_workflow | multi_turn | cli | True | 104 | 752.43 |
| multi_turn_pr_workflow | multi_turn | mcp_naive_43 | True | 44104 | 758.6 |
| plan_parallel_happy | plan | gax_plan | True | 656 | 436.3 |
| plan_with_failure | plan | gax_plan | True | 315 | 3.28 |

*…and 3 more rows in comparison.json*
