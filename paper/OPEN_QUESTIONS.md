# Open Questions

Unresolved problems that could change the paper's conclusions. Each is tiered `[U]` in `PAPER.md`.

Ordered by **how much the paper's conclusions depend on them**, not by how easy they are to answer.

---

## Q1 — Do simulated transcripts reflect real agent behavior? `[U]` · **Blocking 1.0**

**Status:** Open · **Threatens:** §6 (all results), §8.1

The harness constructs representative transcripts rather than running a live model per modality per task (§5.4). This isolates the interface variable and keeps runs deterministic and cheap, but it cannot observe **turn-count effects**.

The specific risk: lazy discovery may induce extra turns. An agent that must call `gax search`, then `gax doc`, then invoke, spends three round-trips where eager schema injection spends one. If each round-trip carries conversation history, the per-turn saving could be partly or wholly offset. Our measurements would not detect this.

**What would resolve it.** N≥30 trials per modality with a real model on the same task suite, measuring total session tokens and turn counts, across at least two model families to separate model-specific prompting effects from interface effects.

**Possible outcomes.** (a) Turn counts comparable → §6 stands. (b) Lazy discovery costs extra turns → the 1.24× overhead figure is wrong and §6.1/§8.1 need revision. (c) Lazy discovery *reduces* turns because smaller context improves selection → results strengthen. **We do not know which, and the paper should not be read as if we do.**

**Partial evidence.** `examples/agent_runs/SAMPLE_RUN/` shows a real model (Gemini 2.5 Flash-Lite) completing discovery-plus-invoke with only `gax_search`/`gax_doc`/`gax_invoke` — establishing feasibility `[O]`, not token parity. One run is not a trial.

---

## Q2 — Does the token advantage hold across tokenizers and model families? `[U]`

**Status:** Open · **Threatens:** §6.1 absolute figures

All counts use `tiktoken cl100k_base`. Models with different tokenizers will produce different absolute counts. JSON-heavy envelope text and prose-heavy CLI output may not scale identically across tokenizers — the envelope's punctuation density is exactly the kind of text where tokenizers diverge.

**What would resolve it.** Re-count existing transcripts under several tokenizers. Cheap: no new runs needed, only re-tokenization of stored transcripts.

**Expected outcome.** Ratios transfer, absolute values shift. Worth confirming precisely because it is cheap.

---

## Q3 — What is the real distribution of MCP catalog sizes? `[U]`

**Status:** Partially answered · **Threatens:** §2.1, §6.1 Finding 3

Our headline naive-MCP figure uses a 44k-token, 43-tool fixture from Scalekit `[E]`. Our own live probe measured 4,450 tokens / 26 tools for `@modelcontextprotocol/server-github` `[M]` — a 10× discrepancy.

Both are real; they measure different things. The open question is which better represents deployed practice. Agents connected to several servers accumulate: our three live servers sum to ~10,253 tokens before the first turn.

**What would resolve it.** Probe 20+ published MCP servers for tool count and schema size; survey typical multi-server configurations.

**Why it matters.** If real deployments cluster near 3–5k, naive MCP's cost is a real but manageable overhead and §6.1's framing overstates the problem. If multi-server aggregation is normal, the fixture is representative. Currently we present both and decline to pick.

---

## Q4 — What is the security posture under adversarial conditions? `[U]`

**Status:** Open · **Threatens:** §8.2 enterprise claims

The paper claims capability enforcement changes outcomes (§7.3) but presents **no threat model at security-venue rigor**. Unanalyzed: capability theft and replay, confused-deputy attacks through adapters, prompt injection inducing valid-but-harmful registered commands, sidecar compromise, audit log tampering.

Note that invariant 4 (no arbitrary shell) bounds prompt-injection *blast radius* to the registered command set — but bounding is not preventing, and a registered write command remains a viable injection target.

**What would resolve it.** A formal threat model with adversary capabilities, an attack-surface analysis per plane, and either a penetration test or formal argument.

**Current honest position:** ACSP provides *mechanisms* (fail-closed caps, allowlists, audit) whose *sufficiency* is unproven. §8.2 says this; readers evaluating for regulated use should treat it as disqualifying until resolved.

---

## Q5 — Does the approach scale past ~50 commands? `[U]`

**Status:** Open · **Threatens:** §3.2 invariant 1 generality

Lazy discovery decouples context cost from catalog size — but only if `gax search` returns relevant results. With thousands of registered commands, search quality becomes the bottleneck and a failed search costs extra turns (compounding Q1).

**What would resolve it.** Build a 500+ command registry; measure search precision@k and turn counts versus catalog size.

**Suspicion `[A]`:** there is a catalog size at which lazy discovery needs semantic search or hierarchical namespacing rather than the current lexical matching. We have not found that threshold because our registry is small.

---

## Q6 — Is the envelope's 66-token cost optimal? `[U]`

**Status:** Open · **Threatens:** §7.1 interpretation

§7.1 prices envelope v1 at ~84 tokens/invocation. Unexamined: whether a leaner encoding preserves the guarantees more cheaply. Candidates: shorter field names, omitting `next` when empty, binary/CBOR for non-LLM surfaces, eliding `schema` after first use in a session.

**What would resolve it.** Ablate individual envelope fields; measure the token/guarantee frontier.

**Why it matters.** If a redesign delivers the same guarantees at ~20 tokens, the CLI-vs-GAX gap narrows to near-noise and the §8.3 recommendation for small deployments changes. Note the envelope is now the *largest* single component of GAX's overhead — larger than the 27-token gap to CLI — so this is the highest-leverage optimization available.

---

## Q7 — How do plans compare to agent-side orchestration? `[U]`

**Status:** Open · **Threatens:** §3.2 invariant 5

`gax_plan` measures 671 median tokens `[M]`, but we never compared it against an agent orchestrating the same steps turn-by-turn. The claim that server-side plans save context is `[A]`, not `[M]`.

**What would resolve it.** Task pairs executed both as a plan and as sequential agent-driven invocations; compare total session tokens.

**Expectation:** plans should win as step count grows, since intermediate results skip the context window entirely. Untested.

---

## Q8 — Would independent evaluation reproduce these results? `[U]`

**Status:** Open · **Threatens:** everything

We designed the system, the harness, and the tasks. §5.1 discloses this; disclosure is not a remedy. Task selection may unconsciously favor GAX's strengths — for instance, our suite includes a `policy_denied` task, a scenario where GAX has a mechanism and CLI structurally cannot compete.

**What would resolve it.** A third party running the harness on their own task suite, ideally one designed before reading this paper.

**Standing invitation.** The harness is open source and runs credential-free via `--mock-only --extended`. Contradicting results are welcome and will be logged in `CHANGELOG.md` under IR-8.

---

## Resolved

*(none yet — entries move here with the evidence that resolved them and the `CHANGELOG.md` version where the paper was updated)*
