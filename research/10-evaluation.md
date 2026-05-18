# Evaluation methodology: CLI vs MCP vs GAX

## Goal

Demonstrate that **GAX** matches or beats **CLI** on token efficiency while exceeding both on **governance** and **structured automation** — the dimensions where naive **MCP** pays a heavy cost.

## Harness

```bash
cd gax && source .venv/bin/activate && pip install -e .
python ../eval/run_comparison.py
# Optional: measure real tools/list from GitHub MCP server
export GITHUB_TOKEN=ghp_...
python ../eval/run_comparison.py --live-mcp
```

Outputs:

- `eval/results/comparison.json`
- `eval/results/comparison.md`

## Modalities

| Modality | What it measures |
|----------|------------------|
| `cli` | Raw `gh` subprocess; tokens ≈ command + stdout |
| `mcp_naive_43` | Same backend + **43-tool** schema overhead (~44k tokens, Scalekit) |
| `mcp_naive_93` | Same + **93-tool** idle schema (~55k, OnlyCLI) |
| `gax` | `invoke()` with `surface=model`, cap, envelope, audit |
| `gax_plan` | Parallel plan block → single combined envelope |

## Composite score (higher = better)

| Dimension | Weight | CLI | MCP naive | GAX |
|-----------|--------|-----|-----------|-----|
| Token efficiency | 30% | High | Low | High |
| Reliability | 25% | High | ~72% (Scalekit infra) | High |
| Governance | 25% | Low | Medium | High |
| Structured output | 20% | Medium | High | High |

Expected leader: **`gax`** or **`gax_plan`** on composite; **`cli`** on raw tokens only; **`mcp_naive_*`** lowest overall.

## Full pipeline

```bash
python eval/run_full.py   # pytest + comparison + full_eval.json
```

## Limitations (document honestly)

- MCP is **simulated** (schema token tax + reliability factor), not a live MCP server in the loop.
- Token counts are **estimates** (chars/4), not provider billing tokens.
- For publication-grade results, wire Anthropic/OpenAI token APIs and Scalekit’s harness repo.

## Next

- Phase 2 deep-research JSON per benchmark item
- Live MCP server in eval (optional `--live-mcp` flag)
- Publish reproducible notebook from `comparison.json`
