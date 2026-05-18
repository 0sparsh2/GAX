# Agent run receipts

Each `python examples/agent_pr_triage.py` run creates a timestamped folder here.

**Committed proof run:** [`SAMPLE_RUN/`](SAMPLE_RUN/) — LLM loop from `20260518T185623Z` plus pre-LLM recovery probe (`adapter_error` on missing `repo` → retry; `recovery_after_error: true`). Re-run `python examples/agent_pr_triage.py` locally to refresh; never commit secrets or tokens.

**Not committed by default** (see root `.gitignore`). After a successful run, you may commit a redacted folder as proof.

Expected files:

| File | Contents |
|------|----------|
| `governance.jsonl` | Denied / scope / expiry scenarios + audit_ids |
| `transcript.jsonl` | LLM reasoning + gax_search/doc/invoke chain |
| `manifest.json` | Proof flags + correlation summary |
| `summary.md` | Human-readable receipt checklist |
