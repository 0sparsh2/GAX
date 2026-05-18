# Implementation roadmap (honest status)

Labels: **Prototype** = works in repo/demo · **Stub** = interface/hook only · **Aspirational** = design only

## Phase 0 — Reference prototype ✅ Prototype

- [x] Envelope v1, manifests, gaxd, CLI, JWT caps, policy, audit, projection, adapters

## Phase 1 — Hardening ✅ Prototype

- [x] OAuth device flow, cap-from-oauth, plan run (sequential + parallel)
- [x] Mermaid PNG, deep-research Phase 1–2, macaroons, YAML policy, OTEL audit hooks
- [x] Evaluation harness v2 (18 tasks, tiktoken, no composite score)

## Phase 2 — Adapters & ecosystem — mixed

| Item | Status | Notes |
|------|--------|-------|
| MCP bridge | **Prototype** | `mcp.github.list_pulls`; needs `GITHUB_TOKEN`; eval integration tasks |
| OpenAPI generator | **Prototype** | `gax openapi generate` |
| kubectl / aws / jira | **Stub** | Mock adapters only |
| ACSP-1.0 spec | **Prototype** | `docs/acsp/ACSP-1.0.md` (implementation-agnostic) |
| deep-research report | **Prototype** | cited external benchmarks |
| Live MCP eval | **Prototype** | `--live-mcp`; optional token |

## Phase 3 — Enterprise — mostly stub

| Item | Status | Notes |
|------|--------|-------|
| Vault | **Stub** | File store + env hook; not production Vault cluster |
| SPIFFE | **Stub** | Metadata from env vars |
| Hosted gaxd | **Prototype** | `gaxd start --host 0.0.0.0`; TLS at gateway is deployment concern |
| Compliance export | **Prototype** | CSV/JSON from audit log |
| OPA/Rego | **Stub** | Optional `opa eval` when binary present |

## Evaluation — Prototype

```bash
pip install -r eval/requirements.txt
cd gax && pip install -e ".[dev]"
python ../eval/run_comparison.py          # mock-friendly
export GITHUB_TOKEN=...
python ../eval/run_comparison.py --live-mcp
python ../eval/case_study/run_case_study.py
```

Outputs: `eval/results/comparison.md` — **separate metrics**, no team-weighted “winner.”

## Post-MVP (aspirational)

- [ ] MCP connection pool / persistent sessions
- [ ] Real kubectl/aws/jira exec adapters
- [ ] Provider-native token APIs (Anthropic/OpenAI usage fields)
- [ ] Independent ACSP conformance suite
- [ ] External adopters / second implementation (Go/Rust)
