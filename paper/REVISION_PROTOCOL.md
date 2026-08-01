# Revision Protocol

How `PAPER.md` is revised. The paper is a **living document**: it is regenerated against current evidence rather than rewritten from memory. This file defines the gates each revision must pass.

Adapted from the human-in-the-loop conventions of [imbad0202/academic-research-skills](https://github.com/imbad0202/academic-research-skills) — integrity gates, bounded revision loops, and generator/evaluator separation.

---

## Iron rules

These are non-negotiable. A revision violating any of them is rejected regardless of how much it improves the prose.

**IR-1 — No unverified citations.** Every external citation must be resolved during the revision that introduces it. A remembered URL is not a citation. If a source cannot be reached, the claim is removed or downgraded to `[A]`.

**IR-2 — Every number traces to an artifact.** Each quantitative claim maps to a row in `eval/results/comparison.json` or a named external source, and appears in the §10.2 provenance table. Numbers typed from memory are prohibited — regenerate or delete.

**IR-3 — Tier every claim.** `[M]` measured, `[O]` operational, `[E]` external, `[A]` argued, `[U]` unresolved. Untiered substantive claims are defects. The tier discipline exists to keep borrowed numbers from reading as ours.

**IR-4 — Bias disclosure survives every revision.** §5.1 may be strengthened, never softened or removed. We evaluate our own system.

**IR-5 — No weighted composite.** Separate metrics and Pareto fronts only. Any revision introducing an overall score is rejected.

**IR-6 — Negative results are load-bearing.** §8.2 must state where the approach loses. A revision that removes a limitation must show it was *resolved by evidence*, and log that in `CHANGELOG.md`.

**IR-7 — Bounded revision loops.** Maximum two improvement passes per cycle. Anything unresolved after two passes becomes an acknowledged limitation in §8.2 or an entry in `OPEN_QUESTIONS.md` — it does not silently disappear.

**IR-8 — Supersede, don't delete.** Claims invalidated by new evidence move to `CHANGELOG.md` with the reason. The record of what we believed and why must remain reconstructible.

---

## Revision cycle

### Phase 0 — Trigger

Revise when any of these occur:

| Trigger | Typical scope |
|---------|---------------|
| New eval run with changed numbers | §6, §7, §10.2 |
| New ablation or modality | §5.2, §7 |
| Open question resolved | §8.2, `OPEN_QUESTIONS.md` |
| Implementation maturity change | §4, §8.2 |
| New related work | §2, §8.2 |
| External review received | Varies — log in `CHANGELOG.md` |

### Phase 1 — Evidence refresh (before touching prose)

```bash
python eval/run_comparison.py --live-mcp --extended
```

Diff new results against the numbers in §6–7. **If numbers changed, prose changes to match — never the reverse.** This ordering is the core discipline: evidence updates first, and the paper follows.

### Phase 2 — Pre-commitment (generator/evaluator separation)

Before editing, write down what you expect to change and why. Recording the expectation first prevents post-hoc rationalization of whatever the data turned out to show. If results contradict the pre-commitment, that contradiction is a **finding** and belongs in the paper.

### Phase 3 — Targeted revision

Edit only the sections the trigger implicates. Untouched sections stay byte-identical, so review diffs stay small and the changelog stays meaningful.

### Phase 4 — Gate check

- [ ] Every new number appears in §10.2 with a tier
- [ ] Every new citation was resolved this cycle (IR-1)
- [ ] Bias disclosure intact (IR-4)
- [ ] No composite score introduced (IR-5)
- [ ] §8.2 still states real limitations (IR-6)
- [ ] Superseded claims logged in `CHANGELOG.md` (IR-8)
- [ ] Version bumped, `Last revised` updated

### Phase 5 — Record

Add a `CHANGELOG.md` entry: what changed, what evidence drove it, what was superseded.

---

## Versioning

`MAJOR.MINOR.PATCH`

| Bump | When |
|------|------|
| **MAJOR** | A central claim is retracted or reversed; thesis changes |
| **MINOR** | New section, ablation, or materially updated results |
| **PATCH** | Clarification, typo, citation formatting — no claim change |

Pre-1.0 signals the paper has not undergone external peer review. Reaching 1.0 requires resolving `OPEN_QUESTIONS.md` Q1 (real-agent trials) — until simulated transcripts are validated against real runs, the evaluation is not submission-grade.

---

## Anti-drift checks

Long-lived documents accumulate characteristic failures. Check each cycle:

**Claim inflation.** Compare §6 hedging against the previous version. Hedges tend to weaken over successive edits until a measured claim becomes an absolute one. Re-read §8.2 aloud — if it stopped feeling uncomfortable, it has probably been softened.

**Stale numbers.** Any figure not regenerated in the last three cycles gets re-verified or marked with its measurement date.

**Citation rot.** External URLs are re-resolved at least every fifth cycle (IR-1 applies to *existing* citations, not just new ones).

**Scope creep.** The paper's claim is about decoupling discovery, authorization, and response structure. Material not serving that thesis belongs in `research/`, not here.

**AI-typical prose.** Uniform paragraph lengths, throat-clearing openers ("It is important to note that…"), and hedge-stacking ("may potentially somewhat") are edited out. Prefer direct statement.
