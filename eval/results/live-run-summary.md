# Live eval run — GAX vs CLI vs MCP (May 2026)

**Repo:** [0sparsh2/GAX](https://github.com/0sparsh2/GAX) · **Gist:** [live-run-summary](https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340) · **Narrative:** [docs/PUBLIC_NARRATIVE.md](../../docs/PUBLIC_NARRATIVE.md) · **Harness:** `eval/run_comparison.py --live-mcp` · **Counter:** tiktoken `cl100k_base`

## Bias disclosure

This is a **self-assessment** by the GAX authors. We report separate metrics (no weighted “winner”). External benchmarks: [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use), [Anthropic Code Mode](https://www.anthropic.com/engineering/code-execution-with-mcp), [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/).

## Setup

- 18 tasks: PR list/view, mocks, errors, policy denial, truncation, multi-turn, plans, MCP bridge
- Live GitHub MCP server: `@modelcontextprotocol/server-github` (26 tools)
- `gax_mcp_bridge`: `mcp.github.list_pulls` via GAX envelope (schema not in agent prompt)

## Correction (July 2026)

**An earlier version of this summary published `cli 104` vs `gax 137` (~1.3×).
That comparison was invalid** — the two medians ran over *different task subsets*.
`cli` skips every mock and discovery task, while `gax` runs them cheaply, dragging the
GAX median down. We found this in our own review; the corrected like-for-like figure is
**~3.5×**, and `success_rate: 100%` across the board was an artifact of rewriting
expected failures to `ok=True`. See [METHODOLOGY](../METHODOLOGY.md) and
[PLAN-2026H2](../../docs/PLAN-2026H2.md).

## Token comparison — paired (the like-for-like number)

Restricted to tasks where **both** modalities produced a real, non-skipped row:

| Pair | n paired | median A | median B | median ratio |
|------|---------:|---------:|---------:|-------------:|
| **cli → gax** | 6 | 80 | 250 | **~3.5×** (range 1.3–5.9×) |
| **cli → gax_mcp_bridge** | 1 | 114 | 456 | ~4.0× |

Per-task ratios and the 9 excluded tasks: [`comparison.md`](./comparison.md).

## Per-modality distribution (NOT head-to-head)

Each modality runs its own subset, so these medians are distributions, not a ranking:

| Modality | n | Median tokens | Completion | Expected outcome | Derivation |
|----------|--:|--------------:|-----------:|-----------------:|------------|
| **cli** | 6 | 98 | 0.50 | 1.00 | measured |
| **gax** | 15 | 139 | 0.73 | 1.00 | measured |
| **gax_mcp_bridge** | 1 | 456 | 1.00 | 1.00 | measured |
| **gax_plan** | 2 | 651 | 0.50 | 1.00 | measured |
| **mcp_live** (26-tool server) | — | 4,483 | — | — | measured |
| **mcp_naive_43** | 11 | 44,060 | 0.73 | 1.00 | **modeled from fixture** |

**Live `tools/list` probe:** 26 tools → **4,450** schema tokens (measured), vs **44,026** for the 43-tool Copilot MCP pack cited by Scalekit.

**By design, verified by test** (architectural constants, not measurements): `cli` audit-id rate 0%; `gax` 80–100%; `gax_mcp_bridge` / `gax_plan` 100%.

## Takeaways

1. **Token axis:** CLI beats GAX by **~3.5×** on like-for-like tasks. Governance is not free. Naive MCP remains far more expensive, but that fixture is a *model*, not our measurement — and modern tool-search / code-mode MCP setups largely close it.
2. **Governance axis:** GAX and `gax_mcp_bridge` emit `audit_id` + envelope v1 and enforce **before** the adapter runs; CLI and raw MCP transcripts do neither.
3. **`fail_closed` is scoped honestly:** only modalities that *have* an enforcement layer are scored on it. Raw `cli` is not marked 0.0 for a test it never sat.
4. **Not a single winner:** CLI wins tokens, clearly. GAX wins pre-invoke enforcement and audit correlation.
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
