# Publishing eval summary to GitHub Gist

**Gist URL:** https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340

After each live run, sync gist content from [results/live-run-summary.md](./results/live-run-summary.md):

```bash
scripts/publish-eval-gist.sh           # update the linked gist in place (history is kept)
scripts/publish-eval-gist.sh --new     # create a separate gist instead
```

The script updates the existing gist through the GitHub API, so every link in the
repo keeps pointing at current numbers. It previously created a *new* gist on each
run, which left the linked one showing stale results — the linked gist went
unchanged from May to September 2026 while its numbers were corrected in the repo.

Before publishing, check the run is valid: `cli` completion non-zero and the live
probe `ok: true` (see `METHODOLOGY.md` — a revoked token produces a plausible but
meaningless run).

## What the gist must say (reviewer-safe)

1. **Bias disclosure** — GAX authors; no weighted composite.
2. **Paired token comparisons** — only tasks both modalities completed; per-modality medians labelled as distributions, not rankings.
3. **Enforcement and selection** — measured separately from tokens (`security-eval.md`, `search-eval.md`).
4. **External numbers** — Scalekit/Anthropic/Cloudflare are **cited**, not our 75-trial replication.
5. **Agent proof** — link to `examples/agent_runs/SAMPLE_RUN/` for **real LLM** receipts (not harness simulation).

Full narrative: [docs/PUBLIC_NARRATIVE.md](../docs/PUBLIC_NARRATIVE.md)
