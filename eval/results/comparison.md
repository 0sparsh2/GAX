# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

Publishable summary: [live-run-summary.md](./live-run-summary.md)

## Token comparison (paired)

Restricted to tasks where **both** modalities produced a real row. This is the like-for-like number; the aggregate table further down runs each modality over its own task subset and must not be read as a head-to-head token comparison.

| pair | n paired | median A | median B | median ratio | range |
|---|---:|---:|---:|---:|---|
| cli → gax | 6 | 77.5 | 249.0 | **3.567×** | 1.278×–6.138× |
| cli → gax_mcp_bridge | 1 | 108 | 449 | **4.157×** | 4.157×–4.157× |

### cli → gax, per task

| task | cli tokens | gax tokens | ratio |
|---|---:|---:|---:|
| cli_bad_flag | 263 | 336 | 1.278× |
| pr_list_invalid_repo | 61 | 137 | 2.246× |
| pr_view_invalid_number | 43 | 128 | 2.977× |
| pr_list | 108 | 449 | 4.157× |
| pr_view_first | 36 | 162 | 4.5× |
| multi_turn_pr_workflow | 94 | 577 | 6.138× |

*Excluded as not comparable (9):* `aws_mock_list`, `discovery_only`, `echo`, `jira_mock_get`, `kubectl_mock`, `large_output_truncation`, `policy_denied`, `search_stub`, `unknown_command`

## Aggregate by modality

> **Not a head-to-head comparison.** Each modality runs a different subset of the suite, so `median_tokens` below is a per-modality distribution, not a cross-modality ranking. See the paired table above.

| modality | n | completion | expected_outcome | fail_closed | median_tokens | derivation |
|---|---:|---:|---:|---:|---:|---|
| cli | 6 | 0.5 | 1.0 | — | 94 | measured |
| cli_agent_spec | 5 | 0.4 | 0.4 | — | 95 | measured |
| cli_logged_proxy | 5 | 0.4 | 0.4 | — | 93 | measured |
| gax | 15 | 0.7333 | 1.0 | 0.5 (n=4) | 137 | measured |
| gax_ablation_no_cap | 1 | 1.0 | 1.0 | — | 275 | measured |
| gax_ablation_no_envelope | 10 | 0.8 | 0.8 | — | 74 | measured |
| gax_ablation_schema_preload | 12 | 0.6667 | 0.6667 | — | 44165 | measured |
| gax_mcp_bridge | 1 | 1.0 | 1.0 | — | 449 | measured |
| gax_plan | 2 | 0.5 | 1.0 | 0.0 (n=1) | 645 | measured |
| mcp_live_github | 5 | 1.0 | 1.0 | — | 44062 | measured |
| mcp_live_mock_filesystem | 5 | 1.0 | 1.0 | — | 168 | measured |
| mcp_live_mock_github | 5 | 1.0 | 1.0 | — | 90 | measured |
| mcp_naive_43 | 11 | 0.7273 | 1.0 | — | 44060 | measured |
| programmatic_mcp | 5 | 1.0 | 1.0 | — | 1084 | measured |

## By-design properties

These are **architectural constants verified by test**, not measured outcomes: `cli` emits no `audit_id` and `gax` emits one on every invoke because that is what each design *is*.

| modality | audit_id_rate | structured_envelope_rate |
|---|---:|---:|
| cli | 0.0 | 0.0 |
| cli_agent_spec | 0.0 | 0.0 |
| cli_logged_proxy | 0.0 | 0.0 |
| gax | 0.8 | 0.8 |
| gax_ablation_no_cap | 1.0 | 1.0 |
| gax_ablation_no_envelope | 1.0 | 0.0 |
| gax_ablation_schema_preload | 1.0 | 1.0 |
| gax_mcp_bridge | 1.0 | 1.0 |
| gax_plan | 1.0 | 1.0 |
| mcp_live_github | 0.0 | 0.0 |
| mcp_live_mock_filesystem | 0.0 | 0.0 |
| mcp_live_mock_github | 0.0 | 0.0 |
| mcp_naive_43 | 0.0 | 0.0 |
| programmatic_mcp | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)

*Token axis deliberately omitted — see paired table.*

- **highest_completion_rate**: gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, gax_ablation_no_cap
- **highest_expected_outcome_rate**: cli, mcp_naive_43, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, gax_ablation_no_cap, gax_plan
- **highest_fail_closed_rate**: gax

## Per-run sample

`completed` is the un-rewritten result: `False` here can still be the *expected* outcome for error-category tasks.

| task | category | modality | completed | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 108 | 314.33 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 352.05 |
| pr_list | happy_path | gax | True | 449 | 389.04 |
| pr_list | happy_path | gax_mcp_bridge | True | 449 | 302.61 |
| pr_list | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| pr_list | happy_path | gax_ablation_no_envelope | True | 319 | 391.83 |
| pr_list | happy_path | gax_ablation_schema_preload | True | 44477 | 393.75 |
| pr_list | happy_path | programmatic_mcp | True | 1088 | 330.05 |
| pr_list | happy_path | cli_agent_spec | True | 150 | 323.74 |
| pr_list | happy_path | cli_logged_proxy | True | 140 | 279.56 |
| pr_list | happy_path | mcp_live_mock_github | True | 93 | 352.05 |
| pr_list | happy_path | mcp_live_mock_filesystem | True | 171 | 352.05 |
| pr_list | happy_path | mcp_live_github | True | 44065 | 352.05 |
| pr_list | happy_path | mcp_live_filesystem | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_memory | False | 0 | 0.0 |
| pr_view_first | happy_path | cli | True | 36 | 289.31 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 324.03 |
| pr_view_first | happy_path | gax | True | 162 | 330.43 |
| pr_view_first | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| pr_view_first | happy_path | gax_ablation_no_envelope | True | 74 | 390.84 |
| pr_view_first | happy_path | gax_ablation_schema_preload | True | 44185 | 328.47 |
| pr_view_first | happy_path | programmatic_mcp | True | 1084 | 303.78 |
| pr_view_first | happy_path | cli_agent_spec | True | 71 | 317.59 |
| pr_view_first | happy_path | cli_logged_proxy | True | 68 | 288.04 |
| pr_view_first | happy_path | mcp_live_mock_github | True | 90 | 324.03 |
| pr_view_first | happy_path | mcp_live_mock_filesystem | True | 168 | 324.03 |
| pr_view_first | happy_path | mcp_live_github | True | 44062 | 324.03 |
| pr_view_first | happy_path | mcp_live_filesystem | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_memory | False | 0 | 0.0 |
| echo | happy_path | cli | True | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | gax | True | 110 | 5.92 |
| echo | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| echo | happy_path | gax_ablation_no_envelope | True | 25 | 4.46 |
| echo | happy_path | gax_ablation_schema_preload | True | 44138 | 3.99 |
| kubectl_mock | happy_path | cli | True | 2 | 0.0 |
| kubectl_mock | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| kubectl_mock | happy_path | gax | True | 143 | 3.58 |

*…and 84 more rows in comparison.json*
