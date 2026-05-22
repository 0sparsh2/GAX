# GAX / ACSP — public narrative (May 2026)

One-page story for README visitors, reviewers, and posts. **Bias disclosure:** GAX is our protocol and reference implementation; we separate **external benchmarks**, **our harness**, and **live agent receipts**.

---

## 1. The problem

Agents need to call GitHub, Kubernetes, SaaS APIs, and internal tools. Two common patterns fail in different ways:

| Pattern | Wins on | Loses on |
|---------|---------|----------|
| **Raw CLI** (`gh`, `kubectl`) | Token-efficient invocations, composability | Ambient credentials, weak per-invoke audit, no standard envelope |
| **Naive MCP** | Typed tools, OAuth stories | Full tool schemas in context every session (44k+ tokens), remote connect flakiness |

**Hybrid** (CLI locally + MCP in prod) doubles auth models, output shapes, and discovery paths.

---

## 2. What GAX is (three planes)

GAX is **not** “replace MCP” or “wrap gh.” It is a **third surface** — **ACSP** (Agent Capability Shell Protocol) — that splits responsibility:

| Plane | Model sees? | Runtime owns |
|-------|-------------|--------------|
| **Invocation** | Yes — short commands (`gax gh.pr.list`, or `gax_search` / `gax_doc` / `gax_invoke`) | Registered commands only |
| **Control** | No — sidecar `gaxd` | OAuth, vault, policy, capability mint/revoke, audit |
| **Data** | Filtered — Envelope v1 | Projection, truncation, `audit_id`, `error.kind` |

**Trust boundary:** the model proposes *which registered command + args*; **`gaxd` enforces* before any adapter runs.

---

## 3. Headline numbers — what is ours vs borrowed

### External synthesis (not a new 75-trial study by us)

Cited in [mcp_vs_cli_benchmarks_2026/report.md](../mcp_vs_cli_benchmarks_2026/report.md) — **literature review**, not independent replication at scale:

| Claim | Source | Notes |
|-------|--------|-------|
| **4×–32×** tokens (naive MCP vs CLI) | [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use) | 75 trials, Claude Sonnet 4, five GitHub tasks |
| **~28% MCP run failures** | Scalekit | **7/25 MCP runs** failed with **`ConnectTimeout`** to remote Copilot MCP; **CLI 25/25** run completion. **Not** “28% task logic failure when connected.” |
| **~98.7%** token reduction (example) | [Anthropic code execution + MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) | Programmatic / lazy tool use — closes naive schema gap |
| **~1k vs ~1.17M** tokens (example) | [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/) | Optimized MCP pattern |

We use these to motivate the problem; **we do not claim we reproduced Scalekit’s 75-run suite across multiple models.**

### Our harness (`eval/run_comparison.py`)

- **18 tasks**, **tiktoken** `cl100k_base`, **no weighted composite** — see [eval/METHODOLOGY.md](../eval/METHODOLOGY.md).
- Transcripts are **simulated** for token comparison ([eval/session_transcript.py](../eval/session_transcript.py)); not full multi-model agent trials per modality.
- **Pareto per axis** (example live run):

| Modality | Median tokens | Audit-id rate | Structured envelope |
|----------|---------------|---------------|---------------------|
| **cli** | **104** (lowest) | 0% | 0% |
| **gax** | 137 | 80% | 80% |
| **gax_mcp_bridge** | 732 | 100% | 100% |
| **mcp_live** (26 tools) | 4,483 | 0% | 0% |
| **mcp_naive_43** (fixture) | 44,062 | 0% | 0% |

**Honest conclusion:** CLI wins **tokens**; GAX wins **governance + structure** without naive schema tax. There is **no single “GAX wins overall”** score.

Publishable table: [eval/results/live-run-summary.md](../eval/results/live-run-summary.md) · [Gist](https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340)

### Live agent proof (not the harness)

[`examples/agent_runs/SAMPLE_RUN/`](../examples/agent_runs/SAMPLE_RUN/) — real LLM (`gemini-2.5-flash-lite`), only `gax_search` / `gax_doc` / `gax_invoke`, live `gh.pr.*`, governance block, recovery probe, `audit_id` correlation. This is **operational evidence**, not a 75-trial benchmark.

---

## 4. Why not just `gh` + a logging proxy?

A logging proxy wraps **whatever** the model already ran (shell or MCP). It does **not**:

- Shrink the **action surface** (model still sees full MCP schemas or arbitrary shell).
- **Fail closed** before invoke on capability / scope / command allowlist.
- Return a **uniform envelope** (`ok`, `error.kind`, projected `data`, `next`) for agents.
- Offer **lazy discovery** (`search` / `doc`) without shipping the full registry.
- Bind **OAuth → per-invoke capability** in one protocol.

GAX’s delta vs **optimized MCP** (code mode, gateway filtering, programmatic tools) is similar: those patterns fix **tokens**; ACSP also standardizes **per-invoke caps + audit_id + CLI-shaped commands + one sidecar** in one spec. Comparisons to CLI Agent Spec and MCP gateways are tracked in [docs/REVIEWER_RESPONSE.md](./REVIEWER_RESPONSE.md) (planned ablations).

---

## 5. What we do not claim (yet)

- Enterprise production: Vault cluster, SPIFFE, hosted multi-tenant control plane — mostly **stub / prototype** ([research/06-implementation-roadmap.md](../research/06-implementation-roadmap.md)).
- Security venue–grade threat model and measured policy enforcement beyond envelope + audit demos.
- Independent ACSP conformance suite at scale — **teaser tests** only ([docs/acsp/CONFORMANCE.md](../docs/acsp/CONFORMANCE.md)).

---

## 6. Verify yourself

```bash
# Harness (optional live MCP)
pip install -r eval/requirements.txt
cd gax && pip install -e ".[dev]"
python ../eval/run_comparison.py --live-mcp

# Real LLM agent + receipts
pip install -r examples/requirements-agent.txt
python examples/agent_pr_triage.py

# ACSP conformance (reference impl)
pytest gax/tests/test_acsp_envelope_conformance.py -q
```

---

## Links

| Artifact | URL |
|----------|-----|
| Repo | https://github.com/0sparsh2/GAX |
| ACSP-1.0 | [docs/acsp/ACSP-1.0.md](./acsp/ACSP-1.0.md) |
| Eval gist | https://gist.github.com/0sparsh2/cea07652091fc4d47637e87d958ed340 |
| SAMPLE_RUN | [examples/agent_runs/SAMPLE_RUN/](../examples/agent_runs/SAMPLE_RUN/) |
