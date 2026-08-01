# Paper Changelog

Revision history for `PAPER.md`. Per **IR-8**, superseded claims are recorded here rather than deleted — the record of what we believed, and why, must stay reconstructible.

Format: version, date, trigger, changes, superseded claims, evidence.

---

## [0.1.0] — 2026-07-29

**Trigger:** Initial draft.

**Evidence base:** Extended eval run recorded in `eval/results/comparison.json` (18 tasks × 18 modalities, `tiktoken cl100k_base`), plus live MCP schema probes of `github`, `filesystem`, and `memory` servers.

### Added

- Full paper structure: abstract through reproducibility (§1–10)
- Three-plane decomposition and five invariants (§3)
- Primary comparison across 7 headline modalities (§6.1)
- Four ablations attributing results to specific invariants (§7)
- `gh` + logging-proxy comparator answering the standing reviewer objection (§7.4)
- Evidence tier system `[M]`/`[O]`/`[E]`/`[A]`/`[U]` (§1.4)
- Explicit negative results — where CLI and optimized MCP beat GAX (§8.2)
- Provenance table mapping every number to its artifact (§10.2)
- Living-document infrastructure: this file, `REVISION_PROTOCOL.md`, `OPEN_QUESTIONS.md`

### Key figures established

| Claim | Value | Tier |
|-------|-------|------|
| CLI median tokens | 113 | `[M]` |
| GAX median tokens | 140 (1.24× CLI) | `[M]` |
| Naive MCP (43-tool fixture) | 44,061 | `[M]` on fixture, fixture from `[E]` |
| Live GitHub MCP schema | 4,450 tok / 26 tools | `[M]` |
| Envelope cost | ~84 tok/invocation | `[M]` |
| Schema-preload ablation | 44,170 ≈ naive 44,061 | `[M]` |
| Logging proxy | 159 tok, no pre-invoke enforcement | `[M]` |
| MCP bridge vs naive same server | 610 vs 4,488 (86% cheaper) | `[M]` |

### Decisions of record

**No weighted composite (IR-5).** A prior internal framing used a 30/25/25/20 composite. Rejected before drafting: authors choosing weights for their own system produces a number that cannot be trusted. Separate metrics and Pareto fronts only.

**External figures kept external.** The 4×–32×, ~28% timeout, ~98.7%, and ~1k-vs-1.17M figures are tiered `[E]` and marked *not replicated*. Earlier repository drafts risked reading as if these were our measurements.

**Ablations designed adversarially.** The suite was built to find configurations beating the full system. It succeeded — `gax_ablation_no_envelope` is the lowest-token modality in the study, beating the system we advocate. That result is reported prominently (§6.2, §7.1) rather than buried.

**Framing chosen: decoupling, not superiority.** The thesis is that discovery, authorization, and response structure are independent concerns. This survives the mixed results; a "GAX wins" framing would not, since our own data contradicts it.

### Known limitations at this version

Simulated transcripts (Q1, blocking 1.0) · single tokenizer (Q2) · fixture-vs-live catalog discrepancy (Q3) · no formal threat model (Q4) · small registry (Q5) · self-evaluation (Q8). See `OPEN_QUESTIONS.md`.

### Superseded

Caught during initial drafting by the IR-2 gate, before publication. Recorded because it demonstrates the gate working, and because it fixes the population definition for all future runs.

The first draft took figures from the **committed** `eval/results/comparison.md`, while `comparison.json` contained a **newer uncommitted run**. Verifying every number against raw rows (IR-2) surfaced the divergence.

| Prior draft figure | Corrected | Reason |
|--------------------|-----------|--------|
| `gax_ablation_no_envelope` 74 tok | **56** | Stale committed markdown |
| Envelope cost ~66 tok | **~84** | Derived: 140 − 56 |
| `gax_mcp_bridge` 755 tok | **610** | Stale committed markdown |
| `gax_plan` 671 tok | **488** | Stale committed markdown |
| Bridge saving 83% | **86%** | Recomputed from 610 vs 4,488 |
| `programmatic_mcp` 1,088 tok | **1,086** | Stale committed markdown |

**Population definition fixed.** Raw `comparison.json` medians over *all* rows differ from published tables (e.g. `cli` 40 vs 113) because failed and skipped runs carry `tokens: 0`. The published harness tables — and this paper — use **successful runs only**. This is now stated explicitly in §6.1 and must be preserved in future revisions; mixing populations silently changes headline numbers by 3×.

**Unchanged by the correction:** every qualitative conclusion. CLI remains token-optimal, the governance premium remains ~27 tokens, and the schema-preload ablation still reproduces naive MCP cost. The envelope's price rose ~27%, which strengthens rather than weakens §7.1's argument that structure should be paid for only when needed.

---

## Template for future entries

```markdown
## [X.Y.Z] — YYYY-MM-DD

**Trigger:** <what prompted this revision>
**Evidence base:** <run / source that drove it>

### Changed
- §N: <what changed and why>

### Superseded
| Prior claim | Version | Replaced by | Reason |
|-------------|---------|-------------|--------|

### Open questions
- Resolved: Qn — <resolution and evidence>
- Added: Qn — <new question and what it threatens>

### Gate check
- [ ] IR-1 citations verified   - [ ] IR-2 numbers traced   - [ ] IR-3 claims tiered
- [ ] IR-4 bias disclosure      - [ ] IR-5 no composite     - [ ] IR-6 negative results
- [ ] IR-7 ≤2 passes            - [ ] IR-8 supersessions logged
```
