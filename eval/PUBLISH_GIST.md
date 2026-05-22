# Publishing eval summary to GitHub Gist

**Gist URL:** https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340

After each live run, sync gist content from [results/live-run-summary.md](./results/live-run-summary.md).

## Update via GitHub CLI

```bash
gh gist edit cea07652091fc4d47637e87d958ed340 \
  -f live-run-summary.md < eval/results/live-run-summary.md
```

## What the gist must say (reviewer-safe)

1. **Bias disclosure** — GAX authors; no weighted composite.
2. **Separate metrics** — median tokens, success, audit-id rate, envelope rate.
3. **Pareto** — CLI lowest tokens; GAX strongest governance/structure in harness.
4. **External numbers** — Scalekit/Anthropic/Cloudflare are **cited**, not our 75-trial replication.
5. **Agent proof** — link to `examples/agent_runs/SAMPLE_RUN/` for **real LLM** receipts (not harness simulation).

Full narrative: [docs/PUBLIC_NARRATIVE.md](../docs/PUBLIC_NARRATIVE.md)
