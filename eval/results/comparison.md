# Evaluation: CLI vs naive MCP vs GAX (v2)
**Tasks:** 18 · **Token counter:** `tiktoken cl100k_base`
**No weighted composite.** Separate metrics only; see [METHODOLOGY.md](../METHODOLOGY.md).

**Live MCP probe:** 26 tools, **4450** schema tokens (measured `tools/list`).

Publishable summary: [live-run-summary.md](./live-run-summary.md)

## Token comparison (paired)

Restricted to tasks where **both** modalities produced a real row. This is the like-for-like number; the aggregate table further down runs each modality over its own task subset and must not be read as a head-to-head token comparison.

| pair | n paired | median A | median B | median ratio | range |
|---|---:|---:|---:|---:|---|
| cli → gax | 6 | 79.0 | 248.0 | **3.475×** | 1.274×–5.938× |
| cli → gax_mcp_bridge | 2 | 112.0 | 578.5 | **5.165×** | 4.0×–6.33× |

### cli → gax, per task

| task | cli tokens | gax tokens | ratio |
|---|---:|---:|---:|
| cli_bad_flag | 263 | 335 | 1.274× |
| pr_list_invalid_repo | 61 | 136 | 2.23× |
| pr_view_invalid_number | 43 | 128 | 2.977× |
| pr_list | 112 | 445 | 3.973× |
| pr_view_first | 36 | 161 | 4.472× |
| multi_turn_pr_workflow | 97 | 576 | 5.938× |

*Excluded as not comparable (10):* `mcp_bridge_pr_list`, `aws_mock_list`, `discovery_only`, `echo`, `jira_mock_get`, `kubectl_mock`, `large_output_truncation`, `policy_denied`, `search_stub`, `unknown_command`

## Aggregate by modality

> **Not a head-to-head comparison.** Each modality runs a different subset of the suite, so `median_tokens` below is a per-modality distribution, not a cross-modality ranking. See the paired table above.

| modality | n | completion | expected_outcome | fail_closed | median_tokens | derivation |
|---|---:|---:|---:|---:|---:|---|
| cli | 7 | 0.5714 | 1.0 | — | 97 | measured |
| cli_agent_spec | 6 | 0.5 | 0.5 | — | 155 | measured |
| cli_logged_proxy | 6 | 0.5 | 0.5 | — | 144 | measured |
| gax | 15 | 0.7333 | 1.0 | 0.5 (n=4) | 139 | measured |
| gax_ablation_no_cap | 1 | 1.0 | 1.0 | — | 276 | measured |
| gax_ablation_no_envelope | 11 | 0.8182 | 0.8182 | — | 74 | measured |
| gax_ablation_schema_preload | 13 | 0.6923 | 0.6923 | — | 44163 | measured |
| gax_mcp_bridge | 2 | 1.0 | 1.0 | — | 709 | measured |
| gax_plan | 2 | 0.5 | 1.0 | 0.0 (n=1) | 646 | measured |
| mcp_live_filesystem | 6 | 1.0 | 1.0 | — | 3384 | measured |
| mcp_live_github | 6 | 1.0 | 1.0 | — | 4489 | measured |
| mcp_live_memory | 6 | 1.0 | 1.0 | — | 2994 | measured |
| mcp_live_mock_filesystem | 6 | 1.0 | 1.0 | — | 171 | measured |
| mcp_live_mock_github | 6 | 1.0 | 1.0 | — | 93 | measured |
| mcp_naive_43 | 12 | 0.75 | 1.0 | — | 44062 | measured |
| mcp_naive_live | 11 | 0.7273 | 1.0 | — | 4483 | measured |
| programmatic_mcp | 6 | 1.0 | 1.0 | — | 1088 | measured |

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
| mcp_live_filesystem | 0.0 | 0.0 |
| mcp_live_github | 0.0 | 0.0 |
| mcp_live_memory | 0.0 | 0.0 |
| mcp_live_mock_filesystem | 0.0 | 0.0 |
| mcp_live_mock_github | 0.0 | 0.0 |
| mcp_naive_43 | 0.0 | 0.0 |
| mcp_naive_live | 0.0 | 0.0 |
| programmatic_mcp | 0.0 | 0.0 |

## Pareto winners (per axis, ties allowed)

*Token axis deliberately omitted — see paired table.*

- **highest_completion_rate**: gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, mcp_live_filesystem, mcp_live_memory, gax_ablation_no_cap
- **highest_expected_outcome_rate**: cli, mcp_naive_43, mcp_naive_live, gax, gax_mcp_bridge, programmatic_mcp, mcp_live_mock_github, mcp_live_mock_filesystem, mcp_live_github, mcp_live_filesystem, mcp_live_memory, gax_ablation_no_cap, gax_plan
- **highest_fail_closed_rate**: gax

## Per-run sample

`completed` is the un-rewritten result: `False` here can still be the *expected* outcome for error-category tasks.

| task | category | modality | completed | tokens | latency_ms |
|---|---|---|---:|---:|---:|
| pr_list | happy_path | cli | True | 112 | 398.29 |
| pr_list | happy_path | mcp_naive_43 | True | 44066 | 446.08 |
| pr_list | happy_path | mcp_naive_live | True | 4489 | 446.08 |
| pr_list | happy_path | gax | True | 445 | 441.86 |
| pr_list | happy_path | gax_mcp_bridge | True | 448 | 383.33 |
| pr_list | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| pr_list | happy_path | gax_ablation_no_envelope | True | 315 | 375.34 |
| pr_list | happy_path | gax_ablation_schema_preload | True | 44473 | 405.29 |
| pr_list | happy_path | programmatic_mcp | True | 1088 | 418.2 |
| pr_list | happy_path | cli_agent_spec | True | 155 | 414.65 |
| pr_list | happy_path | cli_logged_proxy | True | 144 | 349.95 |
| pr_list | happy_path | mcp_live_mock_github | True | 93 | 446.08 |
| pr_list | happy_path | mcp_live_mock_filesystem | True | 171 | 446.08 |
| pr_list | happy_path | mcp_live_github | True | 4489 | 446.08 |
| pr_list | happy_path | mcp_live_filesystem | True | 3384 | 446.08 |
| pr_list | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_list | happy_path | mcp_live_memory | True | 2994 | 446.08 |
| pr_view_first | happy_path | cli | True | 36 | 333.89 |
| pr_view_first | happy_path | mcp_naive_43 | True | 44063 | 373.96 |
| pr_view_first | happy_path | mcp_naive_live | True | 4486 | 373.96 |
| pr_view_first | happy_path | gax | True | 161 | 362.0 |
| pr_view_first | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| pr_view_first | happy_path | gax_ablation_no_envelope | True | 74 | 366.55 |
| pr_view_first | happy_path | gax_ablation_schema_preload | True | 44189 | 347.85 |
| pr_view_first | happy_path | programmatic_mcp | True | 1084 | 350.58 |
| pr_view_first | happy_path | cli_agent_spec | True | 71 | 417.97 |
| pr_view_first | happy_path | cli_logged_proxy | True | 68 | 340.49 |
| pr_view_first | happy_path | mcp_live_mock_github | True | 90 | 373.96 |
| pr_view_first | happy_path | mcp_live_mock_filesystem | True | 168 | 373.96 |
| pr_view_first | happy_path | mcp_live_github | True | 4486 | 373.96 |
| pr_view_first | happy_path | mcp_live_filesystem | True | 3381 | 373.96 |
| pr_view_first | happy_path | mcp_live_fetch | False | 0 | 0.0 |
| pr_view_first | happy_path | mcp_live_memory | True | 2991 | 373.96 |
| echo | happy_path | cli | True | 2 | 0.0 |
| echo | happy_path | mcp_naive_43 | True | 44049 | 0.0 |
| echo | happy_path | mcp_naive_live | True | 4472 | 0.0 |
| echo | happy_path | gax | True | 110 | 4.63 |
| echo | happy_path | gax_ablation_no_cap | True | 0 | 0.0 |
| echo | happy_path | gax_ablation_no_envelope | True | 25 | 4.37 |
| echo | happy_path | gax_ablation_schema_preload | True | 44136 | 3.01 |

*…and 110 more rows in comparison.json*
