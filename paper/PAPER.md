# Governed Agent Execution: Decoupling Tool Discovery, Authorization, and Response Structure in LLM Agent Tool Interfaces

**Version:** 0.1.0 (living document) · **Status:** Working paper — Draft
**Last revised:** 2026-07-29
**Corresponding artifact:** [GAX / ACSP reference implementation](https://github.com/0sparsh2/GAX)

> **Living document notice.** This is a continuously revised working paper, not a frozen submission. Claims are tiered by evidence strength (§1.4) and every quantitative result is traceable to a reproducible harness invocation (§10). Superseded claims are retained in [`CHANGELOG.md`](./CHANGELOG.md) rather than silently deleted. Open problems that would change the paper's conclusions are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

---

## Abstract

Large language model (LLM) agents increasingly act on external systems — version control, orchestration platforms, SaaS APIs — through one of two dominant interfaces. The **command-line interface (CLI)** pattern gives agents a token-efficient, composable surface that pretrained models already understand, but relies on ambient credentials, offers no uniform response contract, and provides weak per-invocation audit. The **Model Context Protocol (MCP)** pattern supplies typed tools, OAuth, and multi-tenant governance, but naive deployments inject complete tool schemas into the context window on every session, a cost that published third-party measurements place in the tens of thousands of tokens.

We argue this is a false dichotomy arising from a *conflation of concerns*: both patterns bind tool **discovery**, **authorization**, and **response structure** to a single interface decision. We present **ACSP** (Agent Capability Shell Protocol) and its reference implementation **GAX** (Governed Agent eXecution), which decompose agent tool access into three planes with distinct visibility to the model — an **invocation plane** the model sees, a **control plane** it never sees, and a **data plane** it sees only in projected form. The design rests on five invariants: lazy discovery, capability tokens per invocation, a uniform response envelope, a registered-command allowlist in place of arbitrary shell, and composable declarative plans.

We evaluate on an 18-task suite spanning happy paths, error handling, policy denial, output truncation, multi-turn sessions, and plan failure, measuring agent-context cost with `tiktoken` (`cl100k_base`) across 18 modalities. We deliberately report **separate metrics rather than a weighted composite**, because the authors designed the system under test. Results are genuinely mixed and we report them as such: raw CLI achieves the lowest median context cost (113 tokens) but 0% audit coverage and 0% structured-response rate; GAX costs modestly more (140 tokens, a 1.24× overhead) while achieving 80% audit and structured-envelope coverage; naive MCP with a 43-tool schema fixture costs 44,061 median tokens, roughly 390× the CLI baseline, with no governance benefit in return. A live probe of `@modelcontextprotocol/server-github` measured 4,450 schema tokens across 26 tools, confirming the schema tax is real but that the widely-cited 44k figure reflects larger catalogs than a single contemporary server.

Four ablations isolate which invariants carry the result. Removing the envelope drops median cost to 56 tokens but structured-response rate to zero, establishing the envelope's price at roughly 84 tokens per invocation. Adding schema preloading to the GAX path raises median cost to 44,170 tokens, demonstrating that the token advantage derives from lazy discovery specifically, not from the protocol as a whole. A permissive-capability ablation succeeds on a task the governed path refuses, isolating the capability check as the mechanism of policy enforcement. Against a `gh`-plus-logging-proxy comparator — the most common reviewer objection — we find comparable token cost but no pre-invocation enforcement, supporting our claim that post-hoc logging and fail-closed authorization are not substitutes.

Our central finding is that **the token cost of governance is small; the token cost of eager schema injection is large; and these are separable concerns.** We explicitly do not claim GAX is superior overall — no such claim survives our own data.

**Keywords:** LLM agents, tool use, Model Context Protocol, capability-based security, agent governance, context engineering, protocol design

---

## 1. Introduction

### 1.1 Motivation

An LLM agent that cannot act on external systems is a text generator. The capacity to list pull requests, inspect cluster state, or query an internal API is what distinguishes an agent from a chatbot, and the interface through which that capacity is exposed is now a consequential engineering decision.

Two patterns dominate practice. In the **CLI pattern**, the agent emits shell commands (`gh pr list --repo org/api`) and receives stdout. In the **MCP pattern**, a server advertises typed tools over a standard protocol and the agent selects among them. These are usually framed as a tradeoff between efficiency and governance: CLI is cheap but ungoverned, MCP is governed but expensive.

We contend the framing is wrong, and that the tradeoff is an artifact of how both patterns bundle concerns rather than a property of the underlying problem.

### 1.2 The conflation of concerns

Three distinct questions are answered *simultaneously and implicitly* by choosing CLI or MCP:

1. **Discovery** — How does the agent learn which capabilities exist? MCP's answer is *eagerly, in full, before the first turn*. CLI's answer is *from pretrained knowledge plus prose in the system prompt*.
2. **Authorization** — What prevents the agent from doing something it should not? MCP's answer is *server-side scope checks, typically per session*. CLI's answer is, in the common case, *nothing beyond the ambient credentials of the executing process*.
3. **Response structure** — What contract governs the returned data? MCP's answer is *typed but implementation-defined*. CLI's answer is *whatever the tool prints*.

Because both patterns answer all three at once, improving one answer requires accepting the others. A team wanting MCP's authorization story inherits its discovery cost. A team wanting CLI's token economics inherits ambient credentials and unstructured output. The observed tradeoff is a consequence of coupling, not necessity.

This paper's thesis: **these three concerns are independently addressable, and decoupling them dominates either bundled pattern on the axes the bundling was forcing you to sacrifice.**

### 1.3 Contributions

- **C1.** A three-plane decomposition of agent tool access (invocation / control / data) organized by *visibility to the model*, with five protocol invariants (§3).
- **C2.** ACSP-1.0, an implementation-agnostic protocol specification, and GAX, an open-source reference implementation (§4).
- **C3.** An 18-task, 18-modality evaluation harness measuring agent-context cost with a real tokenizer, reporting separate metrics under explicit bias disclosure (§5–6).
- **C4.** Four ablations attributing the results to specific invariants rather than to the system as a whole (§7).
- **C5.** A direct empirical response to the "why not `gh` plus a logging proxy?" objection (§7.4).
- **C6.** An explicit negative-results section stating where CLI beats GAX and where our evidence is weakest (§8).

### 1.4 Evidence tiers

Because this document is revised continuously and mixes measurement with synthesis, every substantive claim carries a tier. This convention is load-bearing: it prevents the strongest-sounding numbers, which are borrowed, from being read as our own measurements.

| Tier | Meaning | Verification |
|------|---------|--------------|
| **[M]** Measured | Produced by our harness on a specified run | Re-runnable via §10; raw rows in `eval/results/comparison.json` |
| **[O]** Operational | Observed in a live agent run with artifacts | Correlated `audit_id` values in run transcripts |
| **[E]** External | Reported by a third party; **not replicated by us** | Cited to primary source |
| **[A]** Argued | Design reasoning, not measurement | Supported by construction or ablation, labeled as such |
| **[U]** Unresolved | Open question that could change conclusions | Tracked in `OPEN_QUESTIONS.md` |

---

## 2. Background and Related Work

### 2.1 The schema tax in naive MCP

MCP standardizes tool advertisement, and the straightforward deployment advertises every tool the server offers before the first user turn. Cost scales with catalog size and is paid per session regardless of use.

Third-party measurements motivate the problem. Scalekit reports **4×–32×** higher token consumption for naive MCP versus CLI on equivalent GitHub tasks (75 trials, Claude Sonnet 4) **[E]**. The same report notes **7 of 25** MCP runs failed with `ConnectTimeout` against GitHub's remote Copilot MCP endpoint — an 18/25 (72%) completion rate versus 25/25 (100%) for both CLI variants **[E]**. We flag a nuance frequently lost in secondary citation: the source states every failure was a TCP-level timeout where the connection never completed. This is a *transport reliability* observation about one remote endpoint, **not** evidence that MCP tool-calling logic fails ~28% of the time once connected. We use it to motivate local-sidecar architecture (§3.3), and for nothing stronger.

The 44k figure has a specific provenance worth stating, since our harness inherits it: Scalekit's simplest task consumed 1,365 tokens via CLI versus **44,026** via MCP against GitHub's remote Copilot MCP server — the 32× endpoint of the reported range **[E]**. Our fixture uses that measured value directly (`fixture_schema_tokens: 44026`).

Our own live probe measured **4,450 schema tokens across 26 tools** for `@modelcontextprotocol/server-github` **[M]** — an order of magnitude below the fixture, indicating the widely-quoted figure reflects a larger aggregated catalog than a single contemporary server. We report both and treat the 44k value as a *fixture modeling a large catalog*, not as a claim about any current server. Which better represents deployed practice is unresolved (`OPEN_QUESTIONS.md` Q3).

### 2.2 Optimized MCP: partial solutions

The schema tax is recognized, and several mitigations exist. Anthropic's code-execution approach exposes tools as a filesystem/SDK the model explores programmatically, reporting **~98.7%** token reduction in a worked example **[E]**. Cloudflare's Code Mode replaces schema injection with a `search`-plus-`execute` surface over OpenAPI, reporting **~1k versus ~1.17M** tokens in one case **[E]**.

**These approaches substantially solve the token problem, and we do not claim otherwise.** Our measured `programmatic_mcp` comparator costs 1,086 median tokens **[M]** — 40× better than the naive fixture and squarely in the practical range.

Our claim against them is narrower and is about *scope*, not token efficiency: they optimize discovery while leaving authorization and response structure unstandardized. Neither specifies a per-invocation capability token, a uniform success/failure envelope, nor an audit identifier as protocol guarantees. A team adopting Code Mode still builds those separately. ACSP's contribution is treating all three as one protocol surface **[A]**.

### 2.3 Agent-oriented CLI design

Parallel work improves CLI ergonomics for agents. CLI Spec and CLI Agent Spec define structured output and semantic exit codes; practitioner work argues for JSON-only output with `next_actions` hints. ACSP adopts these conventions — the envelope's `next` field is directly inspired by them — and extends them with the control plane they omit **[A]**. We include a `cli_agent_spec` modality as a first-class comparator rather than a strawman (§7.4).

### 2.4 Capability security and audit

Capability-based authorization is well established. Macaroons provide bearer tokens with contextual caveats supporting offline attenuation; SPIFFE/SVID provides workload identity suitable for audit attestation. ACSP's per-invocation capability is a direct application: the token names allowed commands, scopes, tenant, and expiry, and the shell fails closed on mismatch. Our contribution is not the primitive but its *placement* — binding it to every agent tool invocation as a protocol requirement rather than a deployment option **[A]**.

### 2.5 Positioning

| Approach | Discovery | Authorization | Response structure | Single runtime |
|----------|-----------|---------------|--------------------|----------------|
| Raw CLI | Pretrained + prose | Ambient credentials | Tool-defined | No |
| Naive MCP | Eager, full catalog | Per-session scopes | Typed, impl-defined | Per server |
| Optimized MCP | Lazy / programmatic | Per-session scopes | Typed, impl-defined | Per server |
| CLI Agent Spec | Pretrained + prose | Ambient credentials | **Standardized** | No |
| `gh` + logging proxy | Pretrained + prose | Ambient (post-hoc log) | Tool-defined | No |
| **ACSP / GAX** | **Lazy (`search`/`doc`)** | **Per-invoke capability** | **Envelope v1** | **Yes (sidecar)** |

---

## 3. Design

### 3.1 The three planes

ACSP partitions agent tool access by **what the model can see** — the organizing principle, because context visibility is simultaneously the cost driver and the attack surface.

| Plane | Model sees? | Owns |
|-------|-------------|------|
| **Invocation** | Yes | Short commands: `gax <command> [args]` |
| **Control** | **Never** | OAuth, token vault, policy, capability mint/revoke, audit |
| **Data** | Filtered | Envelope v1; `surface=model` projects and truncates |

The trust boundary is precise: **the model proposes a registered command and arguments; the shell enforces policy before any adapter executes.** The model is an untrusted proposer, never an authorization participant. This is what distinguishes the design from wrapping — a wrapper observes what the model already decided to run; ACSP constrains what it can decide.

### 3.2 Five invariants

1. **Lazy discovery.** `search`, `doc`, and `schema` return bounded payloads (~80–250 tokens). The full registry never enters context. Discovery cost becomes proportional to *use*, not to catalog size — the property that decouples context cost from tool count.
2. **Capability per invocation.** Every invoke carries a JWT or macaroon binding tenant, subject, allowed commands, scopes, and expiry. Absent or insufficient capability fails closed.
3. **Uniform envelope.** Success and failure share one schema: `v`, `ok`, `cmd`, `audit_id`, `data`, `meta`, optional `error` and `next`. Agents parse one shape; failures are data, not text to be inferred from.
4. **No arbitrary shell.** Only registered manifests are invocable. The action surface is enumerable and reviewable — a property no shell-based approach provides.
5. **Composable plans.** Multi-step workflows execute as declarative YAML DAGs server-side, returning one envelope, so intermediate results need not transit the context window.

### 3.3 Architecture

```text
┌──────────────┐   short commands    ┌──────────────┐
│  LLM / Agent │ ───────────────────▶│  gax CLI     │
└──────────────┘                     └──────┬───────┘
                                            │ HTTP + GAX-Capability
                                            ▼
                                     ┌──────────────┐
                                     │    gaxd      │  Registry
                                     │  (sidecar)   │  Policy (OPA)
                                     └──────┬───────┘  Projection
                                            │          Audit / OTEL
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
        ┌──────────┐                  ┌──────────┐                  ┌──────────┐
        │  exec    │                  │   mcp    │                  │   http   │
        │ (gh, …)  │                  │  bridge  │                  │ OpenAPI  │
        └──────────┘                  └──────────┘                  └──────────┘
```

The sidecar is local by default (`127.0.0.1:9477`), which is a deliberate response to the remote-MCP timeout observations in §2.1 **[A]**.

The **adapter layer** matters for adoption: MCP servers and existing CLIs become backends behind stable ACSP command names. ACSP does not compete with MCP for the integration slot — it consumes MCP as one adapter among several, so the `mcp` bridge yields governed invocation of an MCP tool *without* that tool's schema entering context.

### 3.4 Envelope v1

```json
{
  "v": 1, "ok": true, "cmd": "gh.pr.list@1.0.0",
  "audit_id": "aud_0b20bea710fe48fc", "surface": "model",
  "schema": "https://schemas.gax.dev/gh/pr.list/v1",
  "data": { "items": [ { "number": 42, "title": "…", "state": "OPEN" } ] },
  "meta": { "truncated": true, "row_count": 10, "duration_ms": 355 },
  "next": [ { "cmd": "gh.pr.view", "args": { "number": 42 }, "reason": "inspect first PR" } ]
}
```

Three design decisions deserve note. **`audit_id` is mandatory on every response**, making audit a protocol guarantee rather than a deployment practice — an agent cannot perform an unlogged action, because the identifier is produced by the same code path that produces the result. **`meta.truncated` makes projection explicit**, so an agent knows it is reasoning over partial data rather than silently mistaking a truncated list for a complete one. **`next` is advisory**, offering cheap continuation hints without additional discovery calls.

---

## 4. Implementation

GAX is a Python 3.10+ implementation in two parts: `gax`, a client CLI handling discovery, auth, invocation, and plans; and `gaxd`, an HTTP sidecar owning the registry, policy engine, projection, and audit log. Commands are declared as YAML manifests specifying adapter, required scopes, side effects, and I/O schemas, and may be generated from OpenAPI specifications.

Four adapters are implemented: `exec` (wraps existing CLIs such as `gh`), `mcp` (one ACSP command per MCP tool, schema retained in the sidecar), `http` (OpenAPI-derived), and `mock` (credential-free testing). Semantic exit codes distinguish policy denial (2), invalid capability (3), not found (4), and adapter error (5) — failure modes an agent should handle differently.

**Maturity is uneven and we state it plainly [A].** The envelope, sidecar, manifest registry, capability minting, plans, and OAuth device flow are working. The MCP bridge is a functioning prototype without connection pooling. Enterprise integrations — HashiCorp Vault, SPIFFE, OPA, compliance export — are hooks and stubs, not production deployments. `kubectl`, `aws`, and `jira` commands exist as mocks. Claims in this paper are scoped to the working subset.

---

## 5. Evaluation Methodology

### 5.1 Bias disclosure

**GAX is our protocol and our implementation. This is not a neutral third-party evaluation.** Three mitigations are applied, and readers should weight the results accordingly regardless.

First, **no weighted composite score.** A composite requires choosing weights, and authors choose weights that favor their system. We report median tokens, success rate, audit-id rate, and structured-envelope rate separately, and identify Pareto winners per axis without declaring an overall champion.

Second, **adversarial ablations.** The ablation suite (§7) is constructed to find configurations that *beat* the full system on individual axes. It succeeds: `gax_ablation_no_envelope` is the lowest-token modality in the entire study, beating the system we advocate.

Third, **external claims remain external.** The largest numbers in §2 are third-party and tiered **[E]**. We did not replicate them.

### 5.2 Task suite and modalities

Eighteen tasks span happy paths, error conditions, policy denial, output truncation, multi-turn sessions, plan failure, and discovery-only operations, against `octocat/Hello-World` where live access is required.

Eighteen modalities are measured, grouped as: **baselines** (`cli`, `mcp_naive_43`, `mcp_naive_live`), **GAX paths** (`gax`, `gax_mcp_bridge`, `gax_plan`), **ablations** (`gax_ablation_no_cap`, `_no_envelope`, `_schema_preload`), **comparators** (`programmatic_mcp`, `cli_agent_spec`, `cli_logged_proxy`), and a **multi-server MCP catalog** probing five real and mock servers.

### 5.3 Measurement

Tokens are counted with `tiktoken` `cl100k_base` over the simulated agent transcript, falling back to `len(text)//4` only if unavailable. Metrics: `success` (completed as intended), `has_audit_id`, `structured_envelope` (valid envelope v1 with a `data` object). We report **medians**, since schema-tax distributions are heavily skewed by fixed per-session costs.

### 5.4 Threats to validity

We state these before results, not after, because they qualify the numbers rather than excusing them.

**Transcripts are simulated [U].** The harness constructs representative transcripts rather than running a full model per modality per task. This isolates the interface variable and makes runs deterministic and cheap, but it does **not** capture whether a real model uses more turns under one interface than another. A model might, for instance, issue redundant `search` calls under lazy discovery that eager schema injection would avoid — an effect our design cannot observe and which could narrow or reverse the token gap. This is the single most important limitation in the paper and the top item in `OPEN_QUESTIONS.md`.

**Single tokenizer.** `cl100k_base` is not the tokenizer of every deployed agent; ratios should transfer better than absolute counts.

**Single-repository task suite.** Eighteen tasks against one GitHub repository is not a broad workload sample. Absolute counts are workload-specific.

**Schema fixture provenance [E].** The 44k figure is a published Scalekit measurement, not ours. Our live probe measured 4,450 tokens for a 26-tool server. Conclusions about naive MCP are therefore *conditional on catalog size*, and we present both.

**Success-rate artifacts.** Several modalities show non-1.0 success rates due to intentional environment restrictions (e.g. mock-only runs cannot execute live `gh`). These reflect harness configuration, not interface quality, and we avoid drawing quality conclusions from them.

---

## 6. Results

All figures from the extended run recorded in `eval/results/comparison.json` **[M]**.

### 6.1 Primary comparison

| Modality | n | Success | Median tokens | Audit-id | Structured envelope |
|----------|---:|---:|---:|---:|---:|
| `cli` | 7 | 1.00 | **113** | 0% | 0% |
| `gax` | 15 | 1.00 | 140 | **80%** | **80%** |
| `gax_plan` | 2 | 1.00 | 488 | **100%** | **100%** |
| `gax_mcp_bridge` | 2 | 1.00 | 610 | **100%** | **100%** |
| `programmatic_mcp` | 6 | 1.00 | 1,086 | 0% | 0% |
| `mcp_live_github` (26 tools) | 6 | 1.00 | 4,488 | 0% | 0% |
| `mcp_naive_43` (fixture) | 12 | 1.00 | 44,061 | 0% | 0% |

Medians are over **successful runs only**, matching the published harness tables; modality `n` therefore reflects completed runs, not attempts. Failed and skipped runs record `tokens: 0`, so medians over all rows differ substantially (e.g. `cli` 40 vs 113) — the population choice is load-bearing and is fixed by `CHANGELOG.md` for future revisions. Even-`n` medians are reported floored, following the harness.

**Finding 1 — CLI wins on tokens; the margin is small [M].** Raw CLI is the cheapest realistic modality at 113 median tokens. GAX costs 140, an overhead of **27 tokens (1.24×)**. We report this as a CLI win because it is one.

**Finding 2 — governance is nearly free; eager schema injection is not [M].** The 27-token premium buys 80% audit and structured-envelope coverage. The naive MCP path costs 43,948 *additional* tokens over CLI — **1,627× the cost of GAX's governance overhead** — and delivers 0% on both governance axes. Cost and governance are not on the same axis, and the expensive pattern is not the governed one.

**Finding 3 — schema cost scales with catalog, not protocol [M].** Live servers measured 4,450 (github, 26 tools), 3,127 (filesystem, 14), and 2,676 (memory, 9) schema tokens. The 44k fixture models a large aggregated catalog. Naive MCP's cost is therefore a *deployment* property. It is also cumulative: an agent connected to all three live servers pays ~10,253 tokens before its first turn.

**Finding 4 — the bridge governs MCP tools at a fraction of naive cost [M].** `gax_mcp_bridge` reaches 100% audit and envelope coverage at 610 median tokens versus 4,488 for the same server accessed naively — **86% cheaper with strictly more governance**, because the schema stays in the sidecar.

### 6.2 Pareto structure

- **Lowest median tokens:** `gax_ablation_no_envelope` (56) — *an ablation, not the advocated system*
- **Highest success rate:** thirteen modalities tie at 1.00
- **Highest audit-id rate:** all GAX variants (1.00, except baseline `gax` at 0.80)
- **Highest structured-envelope rate:** `gax_mcp_bridge`, `gax_plan`, `gax_ablation_no_cap`, `gax_ablation_schema_preload`

**No modality dominates all axes.** The token-optimal configuration is one we do not recommend, because it discards the structured envelope. This is the honest shape of the result and we decline to smooth it with a composite score.

---

## 7. Ablation Study

Ablations answer the attribution question: *which invariants produce the effect?*

### 7.1 Envelope removal — pricing the structure

| Modality | Median tokens | Audit | Envelope |
|----------|---:|---:|---:|
| `gax` | 140 | 0.80 | 0.80 |
| `gax_ablation_no_envelope` | **56** | 0.79 | **0.00** |

Returning raw JSON instead of envelope v1 cuts median cost by 60%. **The envelope costs ~84 tokens per invocation [M]** — the price of `ok`, `cmd`, `audit_id`, `meta`, and `next` on every response.

This is the study's most useful number and the one most damaging to a naive pro-GAX reading: a deployment that does not need machine-parseable responses should not pay for them. The envelope is justified when uniform failure handling and audit correlation matter — and only then. Note that `audit_id` coverage is essentially unchanged (0.79), since the sidecar logs regardless of projection; what is lost is the agent's ability to *parse* results uniformly.

### 7.2 Schema preloading — isolating the mechanism

| Modality | Median tokens |
|----------|---:|
| `gax` | 140 |
| `gax_ablation_schema_preload` | **44,170** |
| `mcp_naive_43` | 44,061 |

Adding eager schema injection to the GAX path reproduces naive MCP's cost almost exactly (within 0.25%). **GAX's token advantage comes from lazy discovery specifically, not from ACSP as a whole [M].** Any protocol adopting lazy discovery would capture the same benefit; conversely, ACSP deployed with eager discovery would forfeit it entirely. This is the cleanest attribution in the study, and it deliberately limits the credit ACSP can claim.

### 7.3 Capability removal — isolating enforcement

On the `policy_denied` task, baseline `gax` **fails closed** while `gax_ablation_no_cap` (permissive capability) **succeeds in performing the action** **[M]**. The difference is attributable to the capability check alone — not the envelope, not discovery, not the sidecar's existence. Refusal is a property of the authorization mechanism, and removing it removes the refusal.

### 7.4 Against `gh` + a logging proxy

The most common reviewer objection: *why not run `gh` and log it?* We implemented that comparator.

| Modality | Median tokens | Audit-id | Envelope | Pre-invoke enforcement |
|----------|---:|---:|---:|---|
| `cli` | 113 | 0% | 0% | No |
| `cli_logged_proxy` | 159 | 0%* | 0% | **No** |
| `cli_agent_spec` | 170 | 0% | 0% | No |
| `gax` | 140 | 80% | 80% | **Yes** |

\* synthetic post-hoc log line, not a protocol-guaranteed identifier.

**Finding 5 [M] + [A].** The logging proxy costs *more* than GAX (159 vs 140) while providing strictly less. The token argument for proxying does not hold in our measurements. More fundamentally, a proxy observes what the model already ran; it cannot shrink the action surface (arbitrary shell remains available), cannot fail closed before execution, and cannot supply a uniform envelope. Logging and authorization are different mechanisms with different failure modes: a proxy tells you what happened, a capability check determines what *can* happen. §7.3 shows the latter changes outcomes.

Notably `cli_agent_spec` — the strongest CLI-side comparator, with genuinely structured output — costs 170 tokens, *more* than GAX, while lacking the control plane. Structured output alone does not confer governance.

---

## 8. Discussion

### 8.1 What the evidence supports

**Decoupling is achievable and cheap [M].** Governance-per-invocation costs ~27 tokens over raw CLI; structured envelopes cost ~84. Both are small relative to any realistic tool response, and both are two to three orders of magnitude below eager schema injection.

**The dichotomy is false [M] + [A].** "Efficient but ungoverned" versus "governed but expensive" does not survive measurement. The expensive property (eager discovery) and the governance properties (capabilities, envelopes, audit) are independent, and §7.2 demonstrates the independence directly by transplanting the expensive property onto the governed system.

**MCP need not be replaced [M].** The bridge governs MCP tools at 86% lower context cost than naive access. ACSP is a coordination layer over MCP, not a competitor for the same slot.

### 8.2 What the evidence does not support

We state these directly rather than in a closing caveat.

**GAX is not the best choice for every deployment [M].** For a single-user, single-tenant agent with trusted credentials and no audit requirement, raw CLI is cheaper and simpler, and we would recommend it. GAX's premium buys properties such a deployment does not need.

**GAX does not dominate optimized MCP on tokens [M].** `programmatic_mcp` at 1,086 tokens is practical. Our differentiation is scope of standardization (§2.2), an **[A]**-tier architectural argument, not a measured token win.

**We did not replicate the headline external numbers [E].** The 4×–32× and ~98.7% figures are third-party. Our contribution is the decomposition and ablation, not independent confirmation of those studies.

**Simulated transcripts may not reflect real agent behavior [U].** Real models may consume turns differently across interfaces. This could narrow the gap we report, and no result in §6 is safe from it.

**Enterprise claims are unproven [A].** Vault, SPIFFE, OPA, and compliance export are hooks and stubs. No production deployment, no threat model at security-venue rigor, no conformance suite at scale.

### 8.3 When to use what

| Context | Recommendation | Basis |
|---------|----------------|-------|
| Single-user, trusted creds, no audit need | **Raw CLI** | Cheapest; premium buys unneeded properties |
| Token-constrained, governance not required | **Optimized MCP / code mode** | 1,086 tok, mature |
| Multi-tenant, audit or policy required | **ACSP / GAX** | Governance at ~1.24× CLI cost |
| Existing MCP investment, context pressure | **ACSP bridge over MCP** | 86% cheaper, schema stays in sidecar |
| Regulated environment | **ACSP — with caveats** | Protocol fits; enterprise integrations are stubs |

### 8.4 Generalizable lessons

Independent of ACSP's fate, three findings should transfer **[A]**:

1. **Discovery cost should scale with use, not catalog size.** §7.2 shows this is the dominant term; any protocol can adopt it.
2. **Audit belongs in the response contract.** An identifier produced by the same code path as the result cannot be omitted by a misconfigured deployment.
3. **Post-hoc logging is not authorization.** §7.3 and §7.4 show the distinction is empirical, not semantic.

---

## 9. Conclusion

The CLI-versus-MCP debate treats a coupling artifact as a fundamental tradeoff. By decomposing agent tool access into invocation, control, and data planes organized by model visibility, and enforcing lazy discovery, per-invocation capabilities, and a uniform envelope, ACSP obtains MCP-class governance at close to CLI-class context cost.

Our measurements are mixed and we report them mixed. CLI remains the token-optimal realistic modality at 113 median tokens; GAX costs 140 for 80% audit and structured-envelope coverage; naive MCP costs 44,061 for neither. Ablations attribute the token result specifically to lazy discovery — reproducible by any protocol — and the governance result specifically to capability enforcement, which post-hoc logging does not replicate. The strongest honest summary is not that GAX wins, but that **the cost of governance is small, the cost of eager schema injection is large, and treating them as the same tradeoff is a design error.**

The most important open problem is the one that most threatens these results: real-agent trials replacing simulated transcripts, to establish whether interface choice changes how many turns a model takes (§10.2, `OPEN_QUESTIONS.md` Q1).

---

## 10. Reproducibility

### 10.1 Regenerating results

```bash
pip install -r eval/requirements.txt
cd gax && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python ../eval/run_comparison.py --mock-only --extended   # CI-safe, no credentials
python ../eval/run_comparison.py --live-mcp --extended    # full; needs GITHUB_TOKEN
```

Outputs: `eval/results/comparison.json` (all rows), `comparison.md` (base), `extended-comparison.md` (ablations).

Live-server probes require `npx` and network access; individual server failures are tolerated and reported as `fail` (see the `fetch` row in §6.3 of the extended results).

### 10.2 Provenance of every number in this paper

| §  | Claim | Tier | Source |
|----|-------|------|--------|
| 6.1 | cli 113 / gax 140 / naive 44,061 median tokens | **[M]** | `comparison.json`, success-only rows |
| 6.1 | github MCP 4,450 tok / 26 tools | **[M]** | Live `tools/list` probe |
| 6.1 | bridge 610 vs 4,488 tokens | **[M]** | `comparison.json` |
| 7.1 | envelope costs ~84 tok | **[M]** | 140 − 56, ablation |
| 7.2 | preload 44,170 ≈ naive 44,061 | **[M]** | Ablation |
| 7.3 | policy denial reverses without cap | **[M]** | `policy_denied` task |
| 7.4 | proxy 159 vs gax 140 | **[M]** | Comparator |
| 2.1 | 4×–32× tokens; 18/25 (72%) MCP completion; 44,026-tok fixture | **[E]** | Scalekit — source re-verified 2026-07-29; *not replicated* |
| 2.2 | ~98.7% (150k→2k tokens) | **[E]** | Anthropic — source re-verified 2026-07-29; *not replicated* |
| 2.2 | ~1k vs ~1.17M tokens | **[E]** | Cloudflare — *not replicated* |
| 6.1 | 3-server catalog sum 10,253 tok | **[M]** | 4,450 + 3,127 + 2,676, probe rows |
| 4 | Enterprise maturity | **[A]** | Repository roadmap |
| 5.4 | Simulated-transcript threat | **[U]** | `OPEN_QUESTIONS.md` Q1 |

### 10.3 Revision protocol

This paper is regenerated, not rewritten. See [`REVISION_PROTOCOL.md`](./REVISION_PROTOCOL.md) for the gates each revision must pass, and [`CHANGELOG.md`](./CHANGELOG.md) for the history of superseded claims.

---

## References

**Primary sources (verified accessible):**

1. Scalekit. *MCP vs CLI: token consumption analysis.* https://www.scalekit.com/blog/mcp-vs-cli-use — 75 benchmark runs, Claude Sonnet 4; 4–32× token multiple; 1,365 vs 44,026 tokens on the simplest task; MCP 18/25 vs CLI 25/25 completion. Verified 2026-07-29. **[E]**
2. Anthropic. *Code execution with MCP.* https://www.anthropic.com/engineering/code-execution-with-mcp — 150,000 → 2,000 tokens (98.7%) in the Google Drive → Salesforce example. Verified 2026-07-29. **[E]**
3. Cloudflare. *Code Mode: the better way to use MCP.* https://blog.cloudflare.com/code-mode-mcp/ **[E]**
4. IETF. *RFC 8628 — OAuth 2.0 Device Authorization Grant.* https://www.rfc-editor.org/rfc/rfc8628
5. Birgisson, A. et al. *Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud.* Google Research, NDSS 2014.
6. CLI Agent Spec. https://github.com/cli-agent-spec/cli-agent-spec
7. CLI Spec. https://clispec.dev/
8. Model Context Protocol specification. https://modelcontextprotocol.io/

**In-repository artifacts:**

9. `docs/acsp/ACSP-1.0.md` — protocol specification
10. `eval/METHODOLOGY.md` — evaluation methodology and bias disclosure
11. `docs/ABLATIONS.md` — ablation design
12. `eval/results/comparison.json` — complete result rows
13. `examples/agent_runs/SAMPLE_RUN/` — live agent run with correlated audit IDs **[O]**

> **Citation integrity.** Following the verification discipline of the reference skill suite, every external citation resolves to a source consulted during drafting. No citation is included on recall alone. Where we could not verify a claimed figure independently, it is tiered **[E]** and marked *not replicated*.
