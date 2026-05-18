# Evaluation: CLI vs MCP (simulated) vs GAX**Mean composite score** (higher is better):- **gax**: 0.986- **gax_plan**: 0.9838- **gax_mcp_bridge**: 0.7363- **cli**: 0.678- **mcp_naive_43**: 0.5605
**Leader:** gax (0.986)
## Scoring weights
- Tokens 30% | Reliability 25% | Governance 25% | Structure 20%
## Per-run
| task | modality | ok | tokens | latency_ms | composite |
|---|---|---|---:|---:|---:|
| pr_list | cli | True | 94 | 285.19 | 0.6994 |
| pr_list | mcp_naive_43 | True | 44120 | 398.0034999999999 | 0.5603 |
| pr_list | gax | True | 414 | 355.05 | 0.985 |
| pr_list | gax_mcp_bridge | False | 200 | 0 | 0.7363 |
| pr_view_first | cli | True | 26 | 291.42 | 0.6998 |
| pr_view_first | mcp_naive_43 | True | 44052 | 373.428 | 0.5607 |
| pr_view_first | gax | True | 192 | 320.82 | 0.9863 |
| echo | cli | True | 50 | 0 | 0.6347 |
| echo | mcp_naive_43 | True | 44076 | 0.0 | 0.5605 |
| echo | gax | True | 156 | 2.46 | 0.9866 |
| parallel_plan | gax_plan | True | 611 | 373.36 | 0.9838 |
