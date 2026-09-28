# Governed Agent Execution: Decoupling Tool Discovery, Authorization, and Response Structure in LLM Agent Tool Interfaces

**Version:** 0.2.0 (living document) · **Status:** Working paper — Draft
**Last revised:** 2026-09-28
**Corresponding artifact:** [GAX / ACSP reference implementation](https://github.com/0sparsh2/GAX)

> **Living document notice.** This is a continuously revised working paper, not a frozen submission. Claims are tiered by evidence strength (§1.4) and every quantitative result is traceable to a reproducible harness invocation (§10). Superseded claims are retained in [`CHANGELOG.md`](./CHANGELOG.md) rather than silently deleted. Open problems that would change the paper's conclusions are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

---

## Abstract

Large language model (LLM) agents increasingly act on external systems — version control, orchestration platforms, SaaS APIs — through one of two dominant interfaces. The **command-line interface (CLI)** pattern gives agents a token-efficient, composable surface that pretrained models already understand, but relies on ambient credentials, offers no uniform response contract, and provides weak per-invocation audit. The **Model Context Protocol (MCP)** pattern supplies typed tools, OAuth, and multi-tenant governance, but naive deployments inject complete tool schemas into the context window on every session, a cost that published third-party measurements place in the tens of thousands of tokens.

We argue this is a false dichotomy arising from a *conflation of concerns*: both patterns bind tool **discovery**, **authorization**, and **response structure** to a single interface decision. We present **ACSP** (Agent Capability Shell Protocol) and its reference implementation **GAX** (Governed Agent eXecution), which decompose agent tool access into three planes with distinct visibility to the model — an **invocation plane** the model sees, a **control plane** it never sees, and a **data plane** it sees only in projected form. The design rests on five invariants: lazy discovery, capability tokens per invocation, a uniform response envelope, a registered-command allowlist in place of arbitrary shell, and composable declarative plans.

We evaluate on an 18-task suite spanning happy paths, error handling, policy denial, output truncation, multi-turn sessions, and plan failure, measuring agent-context cost with `tiktoken` (`cl100k_base`). We deliberately report **separate metrics rather than a weighted composite**, and compare modalities only on **tasks both completed** — an earlier version of this paper compared medians over different task subsets and understated GAX's cost by about 3× (§5.4, `CHANGELOG.md`). Results are mixed and we report them as such. On paired tasks raw CLI costs a median 79 tokens and GAX 248 — a **3.48× overhead, about 170 tokens absolute** — for pre-invocation enforcement and a structured, audited response. Naive MCP with a 43-tool schema fixture costs 44,062 median tokens; a live probe of `@modelcontextprotocol/server-github` measured 4,450 schema tokens across 26 tools, so the widely cited 44k figure reflects larger catalogs than a single contemporary server.

We also measure what the token harness cannot: whether enforcement holds and whether agents find the right command. A read-only capability was refused on all 41 write and destructive commands in an 87-command registry even when the command was explicitly allowlisted, with no over-blocking. An MCP server that rewrote its own tool after approval — description, schema, name, or disappearance — was refused before execution in 4 of 4 cases, with no false alarms across 65 pins re-verified against five public servers. For command selection, keyword matching found the right command first 33% of the time at 87 commands and 0% on intent-style requests; a selection model (Jev) scored 100% on both, at ~250 ms per query.

Ablations isolate which invariants carry the result. Removing the envelope cuts cost by about 78 tokens per invocation on paired tasks while dropping structured responses to zero. A permissive-capability ablation performs an action the governed path refuses, isolating the capability check as the enforcement mechanism. Against a `gh`-plus-logging-proxy comparator — the most common objection — the proxy is **cheaper** than GAX on paired tasks (93 vs 161 tokens); what it cannot do is refuse an action before it runs. We previously reported the opposite token result; it was an artifact of unpaired comparison.

Our central finding is that **governance costs a few hundred tokens per invocation, eager schema injection costs thousands to tens of thousands, and these are separable concerns.** We explicitly do not claim GAX is superior overall — no such claim survives our own data.

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

Five adapters are implemented: `exec` (wraps existing CLIs such as `gh`), `k8s` (argv-only `kubectl` with DNS-1123 validation and server-side dry run), `mcp` (one ACSP command per MCP tool, schema retained in the sidecar), `http` (OpenAPI-derived), and `mock` (credential-free testing). Semantic exit codes distinguish policy denial (2), invalid capability (3), not found (4), adapter error (5), and pin mismatch (6) — failure modes an agent should handle differently.

Three mechanisms added since v0.1.0 are evaluated in §6.3–6.4:

- **Side-effect ceiling.** Every command declares `read`, `write`, or `destructive`; every capability carries a ceiling (default `read`). A command above the ceiling is refused *even if the capability allowlists it by name*, so an allowlist edit cannot silently promote a read-only credential. Undeclared levels fail closed to `destructive`.
- **Pinned MCP import.** `gax mcp import` turns any MCP server's `tools/list` into governed commands and records a SHA-256 over each tool's name, description, and input schema. The live tool is re-hashed before every invocation; a mismatch fails closed. Description is pinned because it is instruction text for the model — the tool-poisoning vector.
- **Pluggable command search.** `gax_search` ranks commands with keyword matching or, when a key is configured, a remote selection model (TypeSafe Jev) that chooses among the registered commands plus an explicit "none" option. It sends the query and command descriptions — never arguments, capabilities, or audit data — and falls back to keyword matching on any failure.

**Maturity is uneven and we state it plainly [A].** The envelope, sidecar, manifest registry, capability minting, side-effect ceiling, pinned import, plans, and OAuth device flow are working, and the package is published. The MCP bridge spawns a process per call (no connection pooling) and the sidecar handles one request at a time. Enterprise integrations — HashiCorp Vault, SPIFFE, OPA, compliance export — are hooks and stubs. `aws` and `jira` commands are mocks. Claims in this paper are scoped to the working subset.

---

## 5. Evaluation Methodology

### 5.1 Bias disclosure

**GAX is our protocol and our implementation. This is not a neutral third-party evaluation.** Three mitigations are applied, and readers should weight the results accordingly regardless.

First, **no weighted composite score.** A composite requires choosing weights, and authors choose weights that favor their system. We report median tokens, success rate, audit-id rate, and structured-envelope rate separately, and identify Pareto winners per axis without declaring an overall champion.

Second, **adversarial ablations.** The ablation suite (§7) is constructed to find configurations that *beat* the full system on individual axes. It succeeds: `gax_ablation_no_envelope` is the lowest-token modality in the entire study, beating the system we advocate.

Third, **external claims remain external.** The largest numbers in §2 are third-party and tiered **[E]**. We did not replicate them.

Fourth, **we compare like with like, and we have been wrong about this before.** Each modality runs a different subset of the suite (CLI has no equivalent for mock or discovery tasks), so a median per modality compares different workloads. v0.1.0 did exactly that and reported GAX at 1.24× CLI; paired on shared tasks it is ~3.5×. Every cross-modality token claim in this version is paired (§5.3), and v0.1.0's unpaired claims are retracted in `CHANGELOG.md`.

Fifth, **we discard runs from a broken environment, and say so.** The first refresh for this version used a revoked GitHub token. It produced a complete, plausible-looking run — CLI completion 0.00, one task showing GAX *cheaper* than CLI — and was discarded. A self-evaluation that can be silently corrupted this way should disclose when it happened.

### 5.2 Task suite and modalities

Eighteen tasks span happy paths, error conditions, policy denial, output truncation, multi-turn sessions, plan failure, and discovery-only operations, against `octocat/Hello-World` where live access is required.

Eighteen modalities are measured, grouped as: **baselines** (`cli`, `mcp_naive_43`, `mcp_naive_live`), **GAX paths** (`gax`, `gax_mcp_bridge`, `gax_plan`), **ablations** (`gax_ablation_no_cap`, `_no_envelope`, `_schema_preload`), **comparators** (`programmatic_mcp`, `cli_agent_spec`, `cli_logged_proxy`), and a **multi-server MCP catalog** probing five real and mock servers.

### 5.3 Measurement

Tokens are counted with `tiktoken` `cl100k_base` over the simulated agent transcript, falling back to `len(text)//4` only if unavailable.

**Token comparisons are paired.** A cross-modality claim is computed only over tasks where both modalities produced a real row, and reported as per-task ratios with their median and range (`paired_by_modality_pair` in `comparison.json`). Per-modality medians are still reported, but as distributions, not rankings.

**Success is decomposed** into three axes, because a single rate that counts expected failures as successes reads 1.00 for every modality and measures nothing: `completion` (the operation succeeded on its own terms), `expected_outcome` (the result matched the task's declared expectation, including intended failures), and `fail_closed` (enforcement fired *before* the adapter ran — scored only for modalities that have an enforcement layer, and only on tasks meant to be blocked). Audit-id and envelope rates are architectural constants, reported as by-design properties rather than measurements.

Two further benchmarks cover what tokens cannot (§6.3–6.4): an **enforcement** benchmark (`run_security_eval.py`) and a **selection** benchmark (`run_search_eval.py`, 36 queries in literal, synonym, intent, and out-of-scope buckets, scored hit@1).

### 5.4 Threats to validity

We state these before results, not after, because they qualify the numbers rather than excusing them.

**Transcripts are simulated [U].** The harness constructs representative transcripts rather than running a full model per modality per task. This isolates the interface variable and makes runs deterministic and cheap, but it does **not** capture whether a real model uses more turns under one interface than another. A model might, for instance, issue redundant `search` calls under lazy discovery that eager schema injection would avoid — an effect our design cannot observe and which could narrow or reverse the token gap. This is the single most important limitation in the paper and the top item in `OPEN_QUESTIONS.md`.

**Single tokenizer.** `cl100k_base` is not the tokenizer of every deployed agent; ratios should transfer better than absolute counts.

**Single-repository task suite.** Eighteen tasks against one GitHub repository is not a broad workload sample. Absolute counts are workload-specific.

**Schema fixture provenance [E].** The 44k figure is a published Scalekit measurement, not ours. Our live probe measured 4,450 tokens for a 26-tool server. Conclusions about naive MCP are therefore *conditional on catalog size*, and we present both.

**Small n on some pairs.** The bridge comparisons rest on two paired tasks, and the proxy comparisons on five. They are reported with n and should be read as indicative.

**Author-written selection queries.** The 36 search queries were written by the author, and the out-of-scope confidence threshold (0.7) was tuned on the same six queries it is scored on. A held-out, third-party query set would be stronger.

**Live servers drift.** Public MCP servers change between runs: filesystem grew from 3,127 to 3,345 schema tokens and memory from 2,676 to 2,955 between July and September 2026. Import snapshots (`eval/results/mcp_registry/snapshot.json`) record the exact tool set each number was measured on.

---

## 6. Results

All figures from the extended run recorded in `eval/results/comparison.json` **[M]**.

### 6.1 Token cost

**Paired** — only tasks both modalities completed:

| Pair | n | median A | median B | median ratio | range |
|------|--:|---------:|---------:|-------------:|-------|
| `cli` → `gax` | 6 | 79 | 248 | **3.48×** | 1.3–5.9× |
| `cli` → `gax_mcp_bridge` | 2 | 112 | 579 | 5.17× | 4.0–6.3× |
| `gax_mcp_bridge` → `mcp_naive_live` | 2 | 579 | 4,489 | 7.76× | 6.3–10.0× |

**Per-modality distribution** — each over its own task subset, *not* a ranking:

| Modality | n | Median tokens | Completion | Expected outcome |
|----------|--:|--------------:|-----------:|-----------------:|
| `cli` | 7 | 97 | 0.57 | 1.00 |
| `gax` | 15 | 139 | 0.73 | 1.00 |
| `gax_mcp_bridge` | 2 | 709 | 1.00 | 1.00 |
| `programmatic_mcp` | 6 | 1,088 | 1.00 | 1.00 |
| `mcp_naive_live` (26 tools, measured) | 11 | 4,483 | 0.73 | 1.00 |
| `mcp_naive_43` (fixture, modeled) | 12 | 44,062 | 0.75 | 1.00 |

A 3-turn PR-triage workflow (`eval/case_study/`, simulated transcripts) gives cli 158, gax 689 (**4.4×**), bridge 703, naive MCP 44,062.

**Finding 1 — CLI wins on tokens, by more than we first reported [M].** On paired tasks GAX costs 3.48× CLI, about 170 tokens absolute per invocation; over a multi-turn workflow, 4.4×. v0.1.0 reported 1.24× and ~27 tokens from unpaired medians; that figure is retracted.

**Finding 2 — governance and eager discovery are still costs of different magnitude [M].** The ~170-token governance premium is roughly 26× smaller than one live server's schema (4,450 tokens) and ~260× smaller than the 43-tool fixture. The separation that motivates the paper survives the correction; the claim that governance is "nearly free" does not, and is withdrawn.

**Finding 3 — schema cost scales with catalog, not protocol [M].** Live servers measured 4,450 (github, 26 tools), 3,345 (filesystem, 14), and 2,955 (memory, 9) schema tokens. An agent connected to all three pays ~10,750 tokens before its first turn. Naive MCP's cost is a *deployment* property.

**Finding 4 — the bridge governs MCP tools at a fraction of naive cost [M].** On the two paired tasks, `gax_mcp_bridge` costs 579 median tokens versus 4,489 for the same server accessed naively — **87% cheaper**, with audit and envelope coverage the naive path lacks. n = 2; the direction is driven by the fixed schema term and is robust, the magnitude is not.

### 6.2 Pareto structure

Pareto winners are reported per axis (`pareto_winners_per_axis`). The **token axis is deliberately excluded** from that computation: ranking per-modality medians would reintroduce the unpaired comparison of §5.4. Token comparisons live in §6.1's paired table.

On the remaining axes every modality reaches 1.00 `expected_outcome`; `gax_mcp_bridge` and `programmatic_mcp` lead `completion`; and only GAX paths register on `fail_closed`. Baseline `gax` scores 0.50 there (n = 4): two of its four expected-failure tasks are an invalid repository and an invalid PR number, where the backend was reached and returned an error. That is correct behaviour — those are not authorization failures — and we report the 0.50 rather than redefining the metric to reach 1.00.

**No modality dominates all axes.** We decline to smooth this with a composite score.

### 6.3 Enforcement

`eval/run_security_eval.py`, results in `security-eval.json` **[M]**. The registry is 87 commands: bundled, two profiles, and 65 tools imported from five public MCP servers.

| Check | Result |
|---|---:|
| Read-only capability refused on write/destructive commands, **command explicitly allowlisted** | **41/41** |
| Capability at the command's own level allowed (no over-blocking) | **41/41** |
| MCP tool changed after approval, refused before running — description, schema, rename, vanish | **4/4** |
| Honest server unaffected | yes |
| Pins re-verified against 65 real public-server tools — false alarms | **0** |

**Finding 6 — the ceiling holds independently of the allowlist [M].** Naming a destructive command in a read-only capability does not make it invocable. The check is a second, independent condition, so a single mistaken allowlist edit cannot delete anything. The positive control matters as much as the refusal: a check that refuses everything would also score 41/41 on the first row.

**Finding 7 — pinning detects contract changes without false alarms [M].** Rewriting a tool's description — instruction text the model will follow — is caught with the schema untouched. Unchanged real servers produced no mismatches, which is what keeps operators from disabling the check.

### 6.4 Command selection

`eval/run_search_eval.py`, 36 queries, results in `search-eval-{22,87}.json` **[M]**. hit@1 = the first result is correct, i.e. no extra agent turn.

| Registry | Backend | literal | synonym | intent | out-of-scope | all | p50 latency |
|---:|---|---:|---:|---:|---:|---:|---:|
| 22 | keyword | 1.00 | 0.40 | 0.20 | 0.17 | 0.47 | <1 ms |
| 22 | Jev | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 253 ms |
| 87 | keyword | 1.00 | 0.20 | 0.00 | 0.00 | 0.33 | <1 ms |
| 87 | Jev | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 272 ms |

**Finding 8 — lexical discovery degrades as the catalog grows [M].** Keyword matching is perfect when the agent uses the manifest's words and fails otherwise; importing real MCP servers adds noise that drives intent-style requests ("what broke in CI") from 0.20 to 0.00. A selection model held at 1.00, with latency nearly flat in catalog size and ~57 remote input tokens per command. Lazy discovery (§7.2) removes the *schema* cost of a large catalog; this result is about the *selection* cost, which lazy discovery alone does not address.

Two design choices were forced by measurement. Without an explicit "none" option the model always picked something ("order a pizza" → a browser-automation tool at 0.72 confidence); with it, all six out-of-scope queries were refused. And sending all commands was more accurate than a lexical prefilter to 64, at no latency cost.

---

## 7. Ablation Study

Ablations answer the attribution question: *which invariants produce the effect?*

### 7.1 Envelope removal — pricing the structure

Paired on the 10 tasks both completed:

| Modality | Median tokens |
|----------|---:|
| `gax_ablation_no_envelope` | 65 |
| `gax` | 143 |

Returning raw JSON instead of envelope v1 cuts median cost by about half. **The envelope costs ~78 tokens per invocation [M]** (v0.1.0 reported ~84 from unpaired medians; the conclusion is unchanged) — the price of `ok`, `cmd`, `audit_id`, `meta`, and `next` on every response.

This is the study's most useful number and the one most damaging to a naive pro-GAX reading: a deployment that does not need machine-parseable responses should not pay for them. The envelope is justified when uniform failure handling and audit correlation matter — and only then. `audit_id` coverage is unchanged by the ablation, since the sidecar logs regardless of projection; what is lost is the agent's ability to *parse* results uniformly.

### 7.2 Schema preloading — isolating the mechanism

| Modality | Median tokens |
|----------|---:|
| `gax` | 139 |
| `gax_ablation_schema_preload` | 44,163 |
| `mcp_naive_43` | 44,062 |

Adding eager schema injection to the GAX path reproduces naive MCP's cost almost exactly. **This agreement is arithmetic, not an independent measurement [A]:** both modalities add the same 44,026-token fixture to a small transcript, so they could not have differed by much. What the ablation establishes is the attribution argument, not a measured coincidence — **GAX's token advantage comes from lazy discovery specifically, not from ACSP as a whole.** Any protocol adopting lazy discovery would capture the same benefit; conversely, ACSP deployed with eager discovery would forfeit it entirely. This is the cleanest attribution in the study, and it deliberately limits the credit ACSP can claim.

### 7.3 Capability removal — isolating enforcement

On the `policy_denied` task, baseline `gax` **fails closed** while `gax_ablation_no_cap` (permissive capability) **succeeds in performing the action** **[M]**. The difference is attributable to the capability check alone — not the envelope, not discovery, not the sidecar's existence. Refusal is a property of the authorization mechanism, and removing it removes the refusal. In the decomposed metrics, `gax` records `fail_closed` on this task and the ablation records a completed action. §6.3 generalises the test from one task to every mutating command in the registry.

### 7.4 Against `gh` + a logging proxy

The most common reviewer objection: *why not run `gh` and log it?* We implemented that comparator. Paired on the five tasks both completed:

| Modality | Median tokens | Audit-id | Envelope | Pre-invoke enforcement |
|----------|---:|---:|---:|---|
| `cli_logged_proxy` | **93** | post-hoc* | no | **No** |
| `cli_agent_spec` | 95 | no | structured, not governed | No |
| `gax` | 161 | yes | yes | **Yes** |

\* a synthetic log line written after the command ran, not a protocol-guaranteed identifier.

**Finding 5 (revised) — a logging proxy is cheaper, and cannot refuse [M] + [A].** The proxy costs about 58% of GAX's tokens. v0.1.0 reported the reverse (159 vs 140) from unpaired medians and concluded that "the token argument for proxying does not hold"; that conclusion is **retracted**. The token argument for proxying does hold.

What survives is the mechanism argument, and it is the one that matters. A proxy observes what the model already ran: it cannot shrink the action surface (arbitrary shell remains available), cannot fail closed before execution, and cannot stop a changed third-party tool. §7.3 and §6.3 show refusal is measurable, and it is what the extra ~70 tokens buy. A deployment that needs a record but not prevention should use the proxy.

`cli_agent_spec` — structured CLI output without a control plane — is likewise cheaper than GAX. Structured output alone is cheap; governance is what costs.

---

## 8. Discussion

### 8.1 What the evidence supports

**Decoupling is achievable at a modest, stated cost [M].** Governance-per-invocation costs ~170 tokens over raw CLI on paired tasks, of which the envelope is ~78. That is an order of magnitude or more below eager schema injection from even a single live server.

**The dichotomy is false [M] + [A].** "Efficient but ungoverned" versus "governed but expensive" does not survive measurement. The expensive property (eager discovery) and the governance properties (capabilities, envelopes, audit) are independent; §7.2 shows the independence by transplanting the expensive property onto the governed system.

**Enforcement is independent of naming [M].** A side-effect ceiling refused every mutating command to a read-only credential even when the credential named the command, with no over-blocking (§6.3).

**A changed third-party tool can be stopped before it runs [M].** Pinning caught every contract change tried, including description-only rewrites, with no false alarms on unchanged public servers (§6.3).

**MCP need not be replaced [M].** The bridge governs MCP tools at ~87% lower context cost than naive access (n = 2). ACSP is a coordination layer over MCP, not a competitor for the same slot.

### 8.2 What the evidence does not support

We state these directly rather than in a closing caveat.

**GAX is not the best choice for every deployment [M].** For a single-user, single-tenant agent with trusted credentials and no audit requirement, raw CLI is cheaper and simpler, and we would recommend it. GAX's premium buys properties such a deployment does not need.

**GAX does not dominate optimized MCP on tokens [M].** `programmatic_mcp` at 1,086 tokens is practical. Our differentiation is scope of standardization (§2.2), an **[A]**-tier architectural argument, not a measured token win.

**We did not replicate the headline external numbers [E].** The 4×–32× and ~98.7% figures are third-party. Our contribution is the decomposition and ablation, not independent confirmation of those studies.

**Simulated transcripts may not reflect real agent behavior [U].** Real models may consume turns differently across interfaces. This could narrow the gap we report, and no result in §6 is safe from it.

**Governance is not "nearly free" [M].** v0.1.0 said it was. At ~3.5× CLI on paired tasks and ~4.4× over a multi-turn workflow, it is a real cost that deployments should weigh.

**A logging proxy is cheaper than GAX [M].** Where prevention is not required, it is the better tool (§7.4).

**Pinning covers the declared contract, not the implementation [A].** The hash covers a tool's name, description, and input schema. A server that changes what a tool *does* while advertising the same contract is not detected. Pinning closes the description-poisoning vector; it is not a substitute for trusting, sandboxing, or auditing the server.

**Better selection depends on a remote model [M] + [A].** The Jev results require a network call to a third party (~250 ms, query and command descriptions leave the machine). Without a key GAX falls back to keyword matching, which scored 0.33 at 87 commands. The selection result is therefore a property of GAX-plus-a-vendor, not of ACSP.

**Enterprise claims are unproven [A].** Vault, SPIFFE, OPA, and compliance export are hooks and stubs. No production deployment, no threat model at security-venue rigor, no conformance suite at scale.

### 8.3 When to use what

| Context | Recommendation | Basis |
|---------|----------------|-------|
| Single-user, trusted creds, no audit need | **Raw CLI** | Cheapest; premium buys unneeded properties |
| Token-constrained, governance not required | **Optimized MCP / code mode** | ~1,088 tok, mature |
| Multi-tenant, audit or policy required | **ACSP / GAX** | Pre-invoke enforcement at ~3.5× CLI tokens (~170 absolute) |
| Record of actions needed, prevention not required | **CLI + logging proxy** | Cheaper than GAX; cannot refuse |
| Existing MCP investment, context pressure | **ACSP bridge over MCP** | ~87% cheaper than naive (n = 2), schema stays in sidecar |
| Untrusted third-party MCP servers | **ACSP with pinned import** | Contract changes refused pre-invoke |
| Regulated environment | **ACSP — with caveats** | Protocol fits; enterprise integrations are stubs |

### 8.4 Generalizable lessons

Independent of ACSP's fate, three findings should transfer **[A]**:

1. **Discovery cost should scale with use, not catalog size.** §7.2 shows this is the dominant term; any protocol can adopt it.
2. **Audit belongs in the response contract.** An identifier produced by the same code path as the result cannot be omitted by a misconfigured deployment.
3. **Post-hoc logging is not authorization.** §7.3 and §6.3 show the distinction is empirical, not semantic — and §7.4 shows it is not free.
4. **Compare paired, and check the environment.** This paper's own largest error came from comparing different task subsets, and its worst run from a revoked credential that failed silently. Both produce plausible numbers.

---

## 9. Conclusion

The CLI-versus-MCP debate treats a coupling artifact as a fundamental tradeoff. By decomposing agent tool access into invocation, control, and data planes organized by model visibility, and enforcing lazy discovery, per-invocation capabilities, and a uniform envelope, ACSP obtains MCP-class governance at a context cost within an order of magnitude of CLI and far below eager-discovery MCP.

Our measurements are mixed and we report them mixed. On paired tasks CLI costs 79 tokens and GAX 248; a logging proxy is cheaper than GAX; naive MCP costs 4,450 schema tokens for one live server and 44,062 with the 43-tool fixture. What the premium buys is measurable: every mutating command refused to a read-only credential, every tested tool rewrite refused before running. Ablations attribute the token result to lazy discovery — reproducible by any protocol — and refusal to capability enforcement, which post-hoc logging does not replicate. The strongest honest summary is not that GAX wins, but that **governance costs a few hundred tokens, eager schema injection costs thousands, and treating them as the same tradeoff is a design error.**

The most important open problem is the one that most threatens these results: real-agent trials replacing simulated transcripts, to establish whether interface choice changes how many turns a model takes (§10.2, `OPEN_QUESTIONS.md` Q1).

---

## 10. Reproducibility

### 10.1 Regenerating results

```bash
pip install -r eval/requirements.txt
cd gax && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python ../eval/run_comparison.py --mock-only --extended   # CI-safe, no credentials
python ../eval/run_comparison.py --live-mcp --extended    # full; needs a *valid* GITHUB_TOKEN
python ../eval/import_mcp_servers.py ../eval/results/mcp_registry
python ../eval/run_security_eval.py --live
JEV_API_KEY=... python ../eval/run_search_eval.py --backend keyword --backend jev \
    --extra-dir ../eval/results/mcp_registry --json ../eval/results/search-eval-87.json
python ../eval/case_study/run_case_study.py
```

Before trusting a live run, confirm `cli` completion is non-zero and the live probe reports `ok: true` — a revoked token produces a complete but meaningless run (§5.1).

Outputs: `eval/results/comparison.json` (all rows), `comparison.md` (base), `extended-comparison.md` (ablations).

Live-server probes require `npx` and network access; individual server failures are tolerated and reported as `fail` (see the `fetch` row in §6.3 of the extended results).

### 10.2 Provenance of every number in this paper

| §  | Claim | Tier | Source |
|----|-------|------|--------|
| 6.1 | paired cli 79 → gax 248, 3.48× (1.3–5.9×), n = 6 | **[M]** | `comparison.json` → `paired_by_modality_pair.cli_vs_gax` |
| 6.1 | bridge 579 vs naive 4,489, 87% cheaper, n = 2 | **[M]** | `paired_by_modality_pair.gax_mcp_bridge_vs_mcp_naive_live` |
| 6.1 | per-modality medians and completion rates | **[M]** | `comparison.json` → `aggregate_by_modality` |
| 6.1 | github MCP 4,450 tok / 26 tools | **[M]** | `comparison.json` → `live_mcp_probe` |
| 6.1 | filesystem 3,345 / memory 2,955; 3-server sum 10,750 | **[M]** | `comparison.json` → `mcp_catalog_probes` |
| 6.1 | 3-turn workflow cli 158 / gax 689 (4.4×) | **[M]** | `eval/case_study/results.json` |
| 6.2 | `gax` fail_closed 0.50 (n = 4) | **[M]** | `aggregate_by_modality.gax` |
| 6.3 | 41/41 refused, 41/41 allowed, 4/4 attacks, 0/65 false alarms | **[M]** | `security-eval.json` |
| 6.4 | keyword 0.47 / 0.33, Jev 1.00 / 1.00; intent 0.00 vs 1.00 at 87; p50 253 / 272 ms | **[M]** | `search-eval-22.json`, `search-eval-87.json` (0 fallbacks) |
| 7.1 | envelope ~78 tok (65 → 143, n = 10) | **[M]** | `paired_by_modality_pair.gax_ablation_no_envelope_vs_gax` |
| 7.2 | preload 44,163 ≈ naive 44,062 | **[A]** | Same fixture added to both — arithmetic, not independent |
| 7.3 | policy denial reverses without cap | **[M]** | `policy_denied` rows |
| 7.4 | proxy 93 vs gax 161, n = 5 | **[M]** | `paired_by_modality_pair.gax_vs_cli_logged_proxy` |
| 2.1 | 4×–32× tokens; 18/25 (72%) MCP completion; 44,026-tok fixture | **[E]** | Scalekit — source re-verified 2026-07-29; *not replicated* |
| 2.2 | ~98.7% (150k→2k tokens) | **[E]** | Anthropic — source re-verified 2026-07-29; *not replicated* |
| 2.2 | ~1k vs ~1.17M tokens | **[E]** | Cloudflare — *not replicated* |
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
