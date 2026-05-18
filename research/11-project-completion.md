# Project completion summary (May 2026)

## Deliverables

| Area | Location |
|------|----------|
| GAX reference impl | `gax/` v0.4.0 |
| Research hub | `research/` |
| Benchmark deep-research | `mcp_vs_cli_benchmarks_2026/report.md` |
| ACSP specification site | `docs/acsp/` |
| Evaluation | `eval/run_comparison.py`, `eval/run_full.py` |
| Migration research | `gax_implementation_migration_2026/report.md` |

## Evaluation conclusion

Weighted composite (tokens 30%, reliability 25%, governance 25%, structure 20%):

- **gax** and **gax_mcp_bridge** lead (~0.98)
- **cli** mid (~0.68) — good tokens, weak governance
- **mcp_naive_43** low (~0.56) — schema tax

**Claim:** GAX is the best **overall** agent surface for governed, token-efficient, structured automation. CLI remains valid for ungoverned local-only use; naive MCP is not cost-competitive.

## Reproduce

```bash
cd gax && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python ../eval/run_full.py
```
