# ACSP conformance (reference implementation)

**Spec:** [ACSP-1.0.md](./ACSP-1.0.md) · **Status:** Teaser suite for the Python `gax` package — not a full third-party certification program.

## What we test today

Run:

```bash
cd gax && pytest tests/test_acsp_envelope_conformance.py -q
```

| Test | ACSP guarantee |
|------|----------------|
| Success envelope shape | §4 — `v`, `ok`, `cmd`, `audit_id`, `data`, `surface`, `meta` |
| Failure envelope shape | §4 — `ok: false`, `error.kind`, `error.message` |
| Policy denial | §8 — fail closed; audit still correlates |
| Missing capability | §3 — invoke without token → `capability_invalid` |
| Discovery bounded | §6 — `gax search` returns limited hits, not full registry dump |

## Conformance levels (spec §9)

| Level | Reference impl |
|-------|----------------|
| **Core** | Registry, envelope v1, capability validation, `gax doc` / `search` |
| **Governed** | Core + audit log + policy YAML + OAuth device flow |
| **Composed** | Governed + plans + MCP bridge adapter |

## Not in teaser scope

- Cross-language implementations (Go/Rust)
- Formal JSON Schema validation of every manifest
- Fuzzing policy engine
- TLS/mTLS between agent and `gaxd`

Contributions: add tests under `gax/tests/test_acsp_*.py` that map 1:1 to ACSP-1.0 section numbers.
