# Live eval run — GAX vs CLI vs MCP (May 2026)

**Repo:** [0sparsh2/GAX](https://github.com/0sparsh2/GAX) · **Gist:** [live-run-summary](https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340) · **Narrative:** [docs/PUBLIC_NARRATIVE.md](../../docs/PUBLIC_NARRATIVE.md) · **Harness:** `eval/run_comparison.py --live-mcp` · **Counter:** tiktoken `cl100k_base`

## Bias disclosure

This is a **self-assessment** by the GAX authors. We report separate metrics (no weighted “winner”). External benchmarks: [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use), [Anthropic Code Mode](https://www.anthropic.com/engineering/code-execution-with-mcp), [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/).

## Setup

- 18 tasks: PR list/view, mocks, errors, policy denial, truncation, multi-turn, plans, MCP bridge
- Live GitHub MCP server: `@modelcontextprotocol/server-github` (26 tools)
- `gax_mcp_bridge`: `mcp.github.list_pulls` via GAX envelope (schema not in agent prompt)

## Aggregate (live run)

| Modality | Median tokens | Success | Audit-id rate | Structured envelope |
|----------|---------------|---------|---------------|---------------------|
| **cli** | 104 | 100% | 0% | 0% |
| **gax** | 137 | 100% | 80% | 80% |
| **gax_mcp_bridge** | 732 | 100% | 100% | 100% |
| **gax_plan** | 665 | 100% | 100% | 100% |
| **mcp_live** (26-tool server) | 4,483 | 100% | 0% | 0% |
| **mcp_naive_43** (Scalekit fixture) | 44,062 | 100% | 0% | 0% |

**Live `tools/list` probe:** 26 tools → **4,450** schema tokens (measured), vs **44,026** for the 43-tool Copilot MCP pack cited by Scalekit.

## Takeaways

1. **Token axis:** CLI ≈ GAX ≪ naive MCP (44k fixture). Even the lean GitHub MCP server adds ~4.5k/session before the first tool call.
2. **Governance axis:** GAX and `gax_mcp_bridge` emit `audit_id` + envelope v1; CLI and raw MCP transcripts do not.
3. **MCP bridge:** Same backend as MCP, but the agent sees a short `gax` command + envelope — not the full tool schema. Bridge tasks passed with `ok: true` in this run.
4. **Not a single winner:** CLI wins lowest tokens; GAX wins audit/structure without paying naive schema tax.
5. **Harness ≠ agent benchmark:** Transcripts are simulated ([`eval/session_transcript.py`](../session_transcript.py)). Real LLM proof: [`examples/agent_runs/SAMPLE_RUN/`](../../examples/agent_runs/SAMPLE_RUN/) (`20260518T193305Z`).

## External benchmarks (not replicated here)

| Claim | Source |
|-------|--------|
| 4×–32× tokens (naive MCP vs CLI) | [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use) |
| 28% MCP **run** failures (7/25 `ConnectTimeout`) | Scalekit — infrastructure, not our eval |
| Optimized MCP token reductions | Anthropic, Cloudflare (see [benchmark report](../../mcp_vs_cli_benchmarks_2026/report.md)) |

## Reproduce

```bash
pip install -r eval/requirements.txt
cd gax && pip install -e ".[dev]"
# GITHUB_TOKEN in repo-root .env (gitignored) or export
python ../eval/run_comparison.py --live-mcp
```

Full rows: `eval/results/comparison.json` · Case study: `eval/case_study/RESULTS.md`

## CI (no secrets)

PRs run pytest + mock MCP bridge + `eval/run_comparison.py --mock-only`. Offline MCP mock: `eval/mock_mcp/github_stdio_mock.py`.
