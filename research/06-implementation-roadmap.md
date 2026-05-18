# Implementation roadmap

## Phase 0 — Reference prototype ✅

- [x] Envelope v1, manifests, gaxd, CLI, JWT caps, policy, audit, projection, adapters

## Phase 1 — Hardening ✅

- [x] OAuth device flow, cap-from-oauth, plan run (sequential + parallel)
- [x] Mermaid PNG, deep-research Phase 1–2, keyring, macaroons, YAML policy, OTEL audit
- [x] Evaluation harness

## Phase 2 — Adapters & ecosystem ✅ (MVP)

- [x] **MCP bridge** — `adapter: mcp`, `mcp.github.list_pulls`, `gax/mcp_client.py`
- [x] **OpenAPI generator** — `gax openapi generate`
- [x] **Manifests** — kubectl, aws, jira (mock); petstore OpenAPI example
- [x] **ACSP spec site** — `docs/acsp/`
- [x] deep-research report + eval `--live-mcp`

## Phase 3 — Enterprise ✅ (MVP)

- [x] **Vault** — `gax vault put/get`; file store + `GAX_HASHICORP_VAULT_ADDR` hook
- [x] **SPIFFE** — `GAX_SPIFFE_*` env → audit metadata
- [x] **Hosted gaxd** — `gaxd start --host 0.0.0.0` (TLS at gateway)
- [x] **Compliance** — `gax compliance export --format csv|json`
- [x] **OPA/Rego** — `config/policy.rego` + `opa eval` when `opa` binary present

## Evaluation ✅

```bash
cd gax && source .venv/bin/activate && pip install -e ".[dev]"
python ../eval/run_full.py          # pytest + comparison + report
python ../eval/run_comparison.py    # quick matrix
python ../eval/run_comparison.py --live-mcp   # + real tools/list
```

Outputs: `eval/results/comparison.md`, `full_eval.json`

**Expected leader:** `gax` / `gax_mcp_bridge` on composite score (tokens + governance + structure).

## Post-MVP (production hardening)

- [ ] MCP connection pool / persistent gaxd sessions
- [ ] Real kubectl/aws/jira exec adapters
- [ ] Provider-native token counting (Anthropic/OpenAI APIs)
- [ ] Hosted SSO gateway in front of gaxd
- [ ] Formal ACSP RFC / independent conformance tests
