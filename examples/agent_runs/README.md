# Agent run receipts

Each `python examples/agent_pr_triage.py` run creates a timestamped folder here.

**Not committed by default** (see root `.gitignore`). After a successful run, you may commit a redacted folder as proof — never commit secrets or tokens.

Expected files:

| File | Contents |
|------|----------|
| `governance.jsonl` | Denied / scope / expiry scenarios + audit_ids |
| `transcript.jsonl` | LLM reasoning + gax_search/doc/invoke chain |
| `manifest.json` | Proof flags + correlation summary |
| `summary.md` | Human-readable receipt checklist |
