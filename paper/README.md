# Research Paper — Governed Agent Execution

A **continuously improving** working paper on the GAX/ACSP approach.

| File | Purpose |
|------|---------|
| [`PAPER.md`](./PAPER.md) | The paper — abstract through reproducibility |
| [`REVISION_PROTOCOL.md`](./REVISION_PROTOCOL.md) | Gates every revision must pass (iron rules IR-1…IR-8) |
| [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md) | Unresolved problems that could change conclusions |
| [`CHANGELOG.md`](./CHANGELOG.md) | Revision history; superseded claims preserved |

**Current version:** 0.2.0 · Working paper, no external peer review.

---

## What this paper argues

The CLI-versus-MCP debate treats a *coupling artifact* as a fundamental tradeoff. Both patterns bind three independent concerns — tool **discovery**, **authorization**, and **response structure** — to one interface decision. Decouple them and you get MCP-class governance at a context cost within an order of magnitude of CLI — and far below eager-discovery MCP.

The measured summary, which is genuinely mixed (v0.2.0, paired on shared tasks):

| | Result |
|---|---:|
| CLI → GAX tokens | 79 → 248 (**3.48×**, ~170 absolute) |
| Logging proxy vs GAX | proxy **cheaper** (93 vs 161) — but cannot refuse |
| Live GitHub MCP schema | 4,450 tokens / 26 tools |
| Naive MCP (43-tool fixture) | 44,062 tokens |
| Read-only credential refused on mutating commands, even when allowlisted | 41/41, 0 over-blocks |
| Third-party tool rewritten after approval, refused before running | 4/4, 0 false alarms on 65 real pins |
| Right command on first search, 87 commands (selection model / keyword) | 1.00 / 0.33 |

**Governance costs a few hundred tokens. Eager schema injection costs thousands. These are separable concerns** — which is the paper's actual claim, not that GAX wins overall. It does not, and §8.2 says so.

**v0.2.0 retracts two v0.1.0 figures** — GAX at 1.24× CLI, and a logging proxy costing more than GAX. Both came from comparing medians over different task sets. See [`CHANGELOG.md`](./CHANGELOG.md).

---

## Reading paths

**Reviewers, 10 min** — Abstract → §1.2 (conflation of concerns) → §6 (results) → §8.2 (what the evidence does *not* support).

**Practitioners choosing an interface** — §8.3 (decision table) → §7.4 (why not `gh` + logging proxy) → §6.1.

**Researchers assessing rigor** — §1.4 (evidence tiers) → §5.1 (bias disclosure) → §5.4 (threats to validity) → §10.2 (per-number provenance) → `OPEN_QUESTIONS.md`.

**Contributors** — `REVISION_PROTOCOL.md` first, then `OPEN_QUESTIONS.md` for what needs work.

---

## Evidence tiers

Every substantive claim is tagged, so borrowed numbers never read as ours:

`[M]` measured by our harness · `[O]` observed in a live agent run · `[E]` **external, not replicated by us** · `[A]` argued from design · `[U]` unresolved

The largest numbers in the literature (4×–32×, ~98.7% reduction) are `[E]`. We cite them to motivate the problem and claim no credit for them.

---

## Reproducing the results

```bash
pip install -r eval/requirements.txt
cd gax && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

python ../eval/run_comparison.py --mock-only --extended   # no credentials needed
python ../eval/run_comparison.py --live-mcp --extended    # full; needs GITHUB_TOKEN
```

Every number in §6–7 maps to a row in `eval/results/comparison.json` via the provenance table in §10.2.

---

## How this stays a living document

Revisions are **regenerated against evidence, not rewritten from memory**. The cycle: refresh evidence → pre-commit to expected changes → revise only implicated sections → gate check → log.

Three rules do the heavy lifting:

- **IR-2** — every number traces to an artifact; figures typed from memory are prohibited
- **IR-6** — negative results are load-bearing; removing a limitation requires evidence that resolved it
- **IR-8** — supersede, don't delete; invalidated claims move to `CHANGELOG.md` with their reason

Reaching **1.0** requires resolving `OPEN_QUESTIONS.md` **Q1** — real-agent trials replacing simulated transcripts. Until then the evaluation is not submission-grade, and the paper says so.

---

## Known weaknesses

Stated here, not buried in the paper:

1. **Simulated transcripts** (Q1) — we cannot observe whether interfaces change agent turn counts. This threatens every number in §6.
2. **Self-evaluation** (Q8) — we designed the system, harness, and tasks. Disclosure is not a remedy.
3. **No threat model** (Q4) — capability enforcement is demonstrated, not adversarially analyzed.
4. **Enterprise integrations are stubs** — Vault, SPIFFE, OPA are hooks, not deployments.

Independent replication is welcome; contradicting results will be logged under IR-8.

---

## Relationship to the rest of the repository

The paper is the *analytical* layer over artifacts that already exist:

- [`docs/acsp/ACSP-1.0.md`](../docs/acsp/ACSP-1.0.md) — normative protocol spec
- [`eval/METHODOLOGY.md`](../eval/METHODOLOGY.md) — harness methodology
- [`docs/ABLATIONS.md`](../docs/ABLATIONS.md) — ablation design
- [`docs/PUBLIC_NARRATIVE.md`](../docs/PUBLIC_NARRATIVE.md) — the same story for non-academic readers

It does not duplicate them; it argues from them.

Structure and integrity conventions adapted from [imbad0202/academic-research-skills](https://github.com/imbad0202/academic-research-skills) — verified-citations-only, bounded revision loops, generator/evaluator separation, and mandatory limitations disclosure.
