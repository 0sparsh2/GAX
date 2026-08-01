# GAX / ACSP — public narrative (May 2026)

One-page story for README visitors, reviewers, and posts. **Bias disclosure:** GAX is our protocol and reference implementation; we separate **external benchmarks**, **our harness**, and **live agent receipts**.

---

## 1. The problem

**The token problem GAX was founded on has largely been solved upstream — by the model
vendors.** Anthropic's [Tool Search Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
(`defer_loading: true`) cuts ~85% of schema tokens and *improves* accuracy; OpenAI
shipped defer-loading; [Code Mode](https://www.getmaxim.ai/articles/code-execution-with-mcp-how-code-mode-cuts-agent-token-costs-by-90/)
reaches 92.8% reductions at 500+ tools. Lazy discovery is now a platform feature, not a
differentiator. We say this up front because a reader who knows it will otherwise stop
reading.

**What remains unsolved is enforcement, and it is getting worse:**

| Gap | Evidence |
|-----|----------|
| **The shell is ungoverned** | Every MCP gateway (Docker, Cloudflare, Kong, Bifrost, Lunar) governs *MCP traffic*. Agents act overwhelmingly through `bash` — an MCP gateway sees none of it. [NVIDIA OpenShell](https://www.tigera.io/blog/nvidia-openshell-secures-the-agent-who-governs-the-fleet/) works at the syscall layer, with no notion of registered command + capability + audit record. |
| **Governance is the standard's own gap** | The [MCP 2026 roadmap](https://blog.gitguardian.com/mcp-governance-framework/) names enterprise governance, audit trails, and SSO auth as priorities it does not yet address. |
| **The ecosystem outgrew its security model** | [30+ CVEs in Jan–Feb 2026](https://chatforest.com/guides/mcp-ecosystem-2026-state-of-the-standard/): Asana cross-tenant leak, Smithery path traversal (3,243 apps), tool poisoning. |

**Hybrid** (CLI locally + MCP in prod) doubles auth models, output shapes, and discovery paths — and leaves the shell half unaudited in both.

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

**We corrected two defects in our own aggregation** (details in [METHODOLOGY](../eval/METHODOLOGY.md), plan in [PLAN-2026H2](./PLAN-2026H2.md)):

- Earlier versions published **cli 104 vs gax 137 (~1.3×)**. Those medians ran over
  *different task subsets* — `cli` skips every mock/discovery task, which dragged the
  GAX median down. **The paired, like-for-like figure is ~3.5×.**
- `success_rate` read 1.0 for every modality because expected failures were rewritten
  to `ok=True`. It is now split into `completion` / `expected_outcome` / `fail_closed`.

**Paired token comparison** — only tasks where both modalities produced a real row:

| Pair | n paired | median A | median B | median ratio |
|------|---------:|---------:|---------:|-------------:|
| **cli → gax** | 6 | 80 | 250 | **~3.5×** (range 1.3–5.9×) |
| **cli → gax_mcp_bridge** | 1 | 114 | 456 | ~4.0× |

Governance properties are **by design, verified by test** — not measured outcomes:
`cli` emits no `audit_id`; `gax` emits one on every invoke.

**Honest conclusion:** CLI wins **tokens by roughly 3.5×** on like-for-like tasks.
GAX buys **pre-invoke enforcement, uniform envelopes, and audit correlation** for that
cost. There is **no single “GAX wins overall”** score, and the token gap is larger than
we previously published.

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

GAX’s delta vs **optimized MCP** (code mode, gateway filtering, programmatic tools) is similar: those patterns fix **tokens**; ACSP also standardizes **per-invoke caps + audit_id + CLI-shaped commands + one sidecar** in one spec. Harness comparisons and ablations: [docs/ABLATIONS.md](./ABLATIONS.md) (`eval/run_comparison.py --extended`). Reviewer checklist: [docs/REVIEWER_RESPONSE.md](./REVIEWER_RESPONSE.md).

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
