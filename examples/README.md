# GAX examples

## Real LLM agent demo (`agent_pr_triage.py`)

**This is not a scripted transcript simulator.** An LLM receives only `gax_search`, `gax_doc`, and `gax_invoke` — no hardcoded command catalog in the system prompt.

### What it proves

| Claim | Evidence file |
|-------|----------------|
| Dynamic discovery | `transcript.jsonl`: `gax_search` before first `gax_invoke` |
| Token thesis (no MCP schema dump) | Tool results are GAX envelopes only |
| Governance | `governance.jsonl`: denied / scope / expiry + `audit_id` |
| Audit correlation | `summary.md` + `grep` on `~/.gax/audit.jsonl` |
| Multi-step workflow | Agent mission: list → pick stale PR → view → risk → draft comment |
| Error recovery | Pre-LLM recovery probe (`adapter_error` on missing `repo`, then retry) + `proof_flags.recovery_after_error` |

### Setup

```bash
pip install -r examples/requirements-agent.txt
cd gax && pip install -e ".[dev]"

# repo-root .env:
#   GITHUB_TOKEN=...          # live gh.pr.*
#   GEMINI_API_KEY=...              # primary
#   GEMINI_FALLBACK_KEY=...         # optional second key if primary is rate-limited
#   GEMINI_MODEL=gemini-2.5-flash   # recommended (3.1-pro often has zero free quota)
#   GEMINI_FALLBACK_MODEL=gemini-2.5-flash
#   OPENAI_API_KEY=...        # or ANTHROPIC_API_KEY
```

### Run

```bash
# Full demo: governance receipts + LLM agent loop
python examples/agent_pr_triage.py

# Governance only (no LLM API key required)
python examples/agent_pr_triage.py --governance-only
```

Outputs: `examples/agent_runs/<timestamp>/`

### Committed proof run

[`agent_runs/SAMPLE_RUN/`](agent_runs/SAMPLE_RUN/) — operational receipts from a live run (`20260518T185623Z`): the LLM discovers commands via `gax_search` / `gax_doc`, invokes `gh.pr.list` and `gh.pr.view` against `octocat/Hello-World`, drafts a review comment, and posts via `demo.echo`. Governance scenarios (policy deny, scope mismatch, expired capability) run without the LLM and every `audit_id` correlates to `~/.gax/audit.jsonl`. Inspect `transcript.jsonl` for the full tool chain (including API-key fallback on rate limit).

### Other examples

- `gax/examples/demo-session.sh` — manual CLI walkthrough
- `gax/examples/plan-demo.yaml` — declarative plan (no LLM)
