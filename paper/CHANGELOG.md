# Paper Changelog

Revision history for `PAPER.md`. Per **IR-8**, superseded claims are recorded here rather than deleted — the record of what we believed, and why, must stay reconstructible.

Format: version, date, trigger, changes, superseded claims, evidence.

---

## [0.2.0] — 2026-09-28

**Trigger:** New eval run with changed numbers; new modalities and benchmarks; implementation maturity change (side-effect ceiling, pinned MCP import, pluggable command search); a known-invalid headline figure.

**Evidence base:** `eval/results/comparison.json` (live run, `--live-mcp --extended`, paired comparisons recomputed from its rows), `security-eval.json`, `search-eval-22.json`, `search-eval-87.json`, `eval/case_study/results.json`, and `mcp_registry/snapshot.json` (65 tools from five public MCP servers).

### Pre-commitment vs result (Phase 2)

Written before the refresh ran:

| Expectation | Result | |
|---|---|---|
| Paired cli→gax 3–4× | 3.48× | ✅ |
| Absolute overhead ~150–200 tok; thesis survives; MINOR bump | ~170 tok; separability survives | ✅ |
| gax completion < 1.0 | 0.73 | ✅ |
| Live github schema ~4.4–4.5k | 4,450 | ✅ |
| Pinning 4/4; all 6 real servers import + verify | 4/4; 5 servers, 65 pins, 0 false alarms | ✅ |
| Jev ≥ 0.95, keyword 0.4–0.5, intent ≈ 0 | Jev 1.00; keyword 0.47 / 0.33; intent 0.00 | ✅ (keyword at 87 below range) |
| Ceiling refuses destructive pre-invoke, 100% | 41/41 | ✅ |
| *(not pre-committed)* logging proxy vs GAX | proxy **cheaper** | ❗ finding — contradicts v0.1.0 |

The proxy reversal was not anticipated. It is reported as a finding (§7.4) rather than explained away.

### Superseded (IR-8)

| v0.1.0 claim | Status | Why |
|---|---|---|
| GAX 140 vs CLI 113 median tokens — **1.24×**, "~27 tokens" | **Retracted** | Medians over different task subsets (cli n = 7, gax n = 15, 6 shared); the 9 GAX-only tasks were cheap mocks that pulled its median down. Paired: 79 → 248, 3.48×. |
| "Governance is nearly free"; naive MCP overhead "1,627× the cost of GAX's governance" | **Retracted** | Derived from the 27-token figure. Replaced by ~26× (one live server) / ~260× (fixture) vs the paired ~170-token premium. |
| Logging proxy 159 vs GAX 140 — "the token argument for proxying does not hold" | **Reversed** | Unpaired (proxy n = 6, gax n = 15). Paired on 5 shared tasks: proxy 93, GAX 161. The proxy is cheaper; the mechanism argument (no pre-invoke refusal) stands. |
| `cli_agent_spec` 170 > GAX 140 | **Reversed** | Same cause. Paired: 95 vs 161. |
| Envelope costs ~84 tok | **Revised** to ~78 | Paired on 10 tasks (65 → 143). Conclusion unchanged. |
| Bridge 610 vs 4,488, 86% cheaper | **Revised** to 579 vs 4,489, 87% | Paired, n = 2 — now stated. |
| Schema preload 44,170 ≈ naive 44,061, tiered `[M]` | **Re-tiered** to `[A]` | Both add the same 44,026 fixture; the agreement is arithmetic, not an independent measurement. |
| "Thirteen modalities tie at 1.00 success" (§6.2) | **Retracted** | The success metric counted expected failures as successes and read 1.00 for everything. Replaced by `completion` / `expected_outcome` / `fail_closed`. |
| 3-server schema sum 10,253 | **Revised** to 10,750 | Servers changed (filesystem 3,127 → 3,345; memory 2,676 → 2,955). |

### Added

- §4: `k8s` adapter, exit code 6, side-effect ceiling, pinned import, pluggable search; updated maturity statement
- §5.1: two further bias mitigations — paired comparison, and disclosure of a discarded run (IR-4: strengthened)
- §5.3: paired token methodology; decomposed success metrics; enforcement and selection benchmarks
- §5.4: small-n pairs, author-written selection queries, live-server drift (replaces the "success-rate artifacts" paragraph, which the decomposition resolved)
- §6.3 Enforcement (Findings 6–7) and §6.4 Command selection (Finding 8)
- §8.2: four new limitations — governance is not nearly free; a proxy is cheaper; pinning covers the contract, not the implementation; better selection depends on a remote vendor
- §8.3: two new rows (logging proxy; untrusted MCP servers)
- §8.4: lesson 4 — compare paired, check the environment
- `OPEN_QUESTIONS.md`: Q4 and Q5 partial evidence; Q6 and Q7 figures updated; new Q9 (selection generalization)

### A run was discarded

The first refresh used a revoked `GITHUB_TOKEN`. Every `gh` call returned HTTP 401; the harness completed normally and reported CLI completion 0.00 and a GAX-cheaper-than-CLI task. It was discarded and repeated with a valid credential. Recorded because the failure was silent and the numbers looked plausible.

### Version rationale

MINOR (0.1.0 → 0.2.0), not MAJOR. Two headline figures are retracted and one finding reversed, but the central thesis — discovery, authorization, and response structure are separable, and governance costs orders of magnitude less than eager schema injection — survives the corrected numbers. The claim that governance is *nearly free* does not survive and is withdrawn explicitly in §6.1 and §8.2. A reader who considers that framing central should treat this as a major revision.

### Gate check (Phase 4)

- [x] Every new number appears in §10.2 with a tier
- [x] No new external citations introduced (IR-1)
- [x] Bias disclosure intact and strengthened (IR-4)
- [x] No composite score; token axis removed from Pareto (IR-5)
- [x] §8.2 still states real limitations — four added, none removed (IR-6)
- [x] Superseded claims logged above (IR-8)
- [x] Two improvement passes used (IR-7): pass 1 rewrote §4–10; pass 2 caught two stale figures (§7.2 table, orphan provenance row) and a duplicated table in `README.md`
- [x] Version bumped, `Last revised` updated
- [ ] Not done this cycle: §1 contributions list (C1–C3) does not yet mention the enforcement and selection benchmarks; citation re-resolution (IR-1 anti-drift) deferred — last done 2026-07-29

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
