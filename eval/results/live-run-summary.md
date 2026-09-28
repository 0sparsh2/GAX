# Live eval run — GAX vs CLI vs MCP (September 2026)

**Repo:** [0sparsh2/GAX](https://github.com/0sparsh2/GAX) · **Narrative:** [docs/PUBLIC_NARRATIVE.md](../../docs/PUBLIC_NARRATIVE.md) · **Counter:** tiktoken `cl100k_base`

## Bias disclosure

This is a **self-assessment** by the GAX authors. Separate metrics, no weighted "winner". External references: [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use), [Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp), [Cloudflare](https://blog.cloudflare.com/code-mode-mcp/).

Every number below is read from a results file in this directory — `comparison.json`, `security-eval.json`, `search-eval-22.json`, `search-eval-87.json` — or `../case_study/results.json`.

## What changed since July

- **Security and search are now benchmarked**, not just tokens: [security-eval.md](./security-eval.md), [search-eval.md](./search-eval.md).
- **July's corrected figures held.** Paired cli→gax was ~3.5×; this run: **3.48×**.
- **A run was discarded.** The first refresh used a revoked `GITHUB_TOKEN` from `.env`: every `gh` call returned HTTP 401, CLI completion read 0.00, and one task showed GAX *cheaper* than CLI. Those numbers were thrown away and the run repeated with a valid credential. Noted because a broken environment produced plausible-looking output.

## 1. Tokens — paired (the like-for-like number)

Only tasks where both modalities produced a real row:

| Pair | n | median A | median B | median ratio | range |
|------|--:|---------:|---------:|-------------:|-------|
| **cli → gax** | 6 | 79.0 | 248.0 | **3.48×** | 1.3–5.9× |
| cli → gax_mcp_bridge | 2 | 112.0 | 578.5 | 5.17× | 4.0–6.3× |

Bridge row is **n = 2** — indicative only.

**3-turn workflow** ([case study](../case_study/RESULTS.md), simulated transcripts): cli 158 · gax 689 (**4.4×**) · gax_mcp_bridge 703 · mcp_naive_43 44,062.

**Live `tools/list`:** `@modelcontextprotocol/server-github` → **26 tools, 4,450 schema tokens** (measured) vs 44,026 for the 43-tool pack Scalekit cites (fixture, not measured by us).

## 2. Per-modality distribution (NOT head-to-head)

Each modality runs its own task subset, so these medians are not a ranking.

| Modality | n | Median tokens | Completion | Expected outcome |
|----------|--:|--------------:|-----------:|-----------------:|
| **cli** | 7 | 97 | 0.57 | 1.00 |
| **gax** | 15 | 139 | 0.73 | 1.00 |
| **gax_mcp_bridge** | 2 | 709 | 1.00 | 1.00 |
| **gax_plan** | 2 | 646 | 0.50 | 1.00 |
| **mcp_naive_live** | 11 | 4,483 | 0.73 | 1.00 |
| **mcp_naive_43** *(modeled from fixture)* | 12 | 44,062 | 0.75 | 1.00 |

## 3. Enforcement ([security-eval.md](./security-eval.md))

| Check | Result |
|---|---:|
| Read-only capability refused on write/destructive commands, **command explicitly allowlisted** | **41/41** |
| Capability at the command's level allowed (no over-blocking) | **41/41** |
| Tampered MCP tool refused before running (description / schema / rename / vanish) | **4/4** |
| Pins re-verified against 65 real public-server tools — false alarms | **0** |

41 of 87 commands are mutating; most are imported MCP tools, which default to `destructive` until reviewed.

## 4. Command selection ([search-eval.md](./search-eval.md))

hit@1 on 36 queries (literal, synonym, intent, out-of-scope):

| | 22 commands | 87 commands | intent @ 87 | p50 latency |
|---|---:|---:|---:|---:|
| keyword | 0.472 | 0.333 | 0.0 | <1 ms |
| **jev** (default) | **1.0** | **1.0** | **1.0** | 272 ms |

Keyword degrades as MCP servers are imported; Jev did not. Queries are hand-written by the author (n = 36).

## Takeaways

1. **Tokens:** CLI is ~3.5× cheaper than GAX like-for-like (~169 tokens absolute); ~4.4× over a 3-turn workflow. Governance is not free.
2. **Enforcement held in every case measured**, including against a server rewriting its own tools, with zero false alarms on unchanged real servers.
3. **Selection** is where GAX can still save turns: natural-language requests resolve correctly with Jev and mostly fail with keyword matching.
4. **Harness ≠ agent benchmark.** Transcripts are simulated ([`session_transcript.py`](../session_transcript.py)); real-LLM receipts: [`examples/agent_runs/SAMPLE_RUN/`](../../examples/agent_runs/SAMPLE_RUN/).

## Reproduce

```bash
cd gax && pip install -e ".[dev]" && cd ..
export GITHUB_TOKEN=...                        # must be valid — see "a run was discarded"
python eval/run_comparison.py --live-mcp --extended
python eval/import_mcp_servers.py eval/results/mcp_registry
python eval/run_security_eval.py --live
JEV_API_KEY=... python eval/run_search_eval.py --backend keyword --backend jev --json eval/results/search-eval-22.json
python eval/case_study/run_case_study.py
```
