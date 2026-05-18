# ACSP-1.0 — Agent Capability Shell Protocol (implementation-agnostic)

**Status:** Draft · **Version:** 1.0 · **Date:** 2026-05

This document defines **protocol guarantees** any conforming implementation may provide. It is independent of Python, `gaxd`, or this repository’s reference code.

## 1. Scope

ACSP standardizes how **agents** invoke **registered capabilities** under **tenant policy**, with **lazy discovery** and **structured responses**. It does not mandate MCP, HTTP, or a specific CLI binary.

## 2. Roles

| Role | Responsibility |
|------|----------------|
| **Agent** | Chooses commands, passes args, holds capability token |
| **Shell / gateway** | Validates token, enforces policy, routes to adapter |
| **Adapter** | Maps command → backend (exec, MCP tool, HTTP, etc.) |
| **Control plane** | OAuth, vault, audit store (optional, out-of-band) |

## 3. Protocol guarantees

1. **Registered commands only** — Agents cannot invoke arbitrary shell; only manifests in the registry.
2. **Capability on every invoke** — Opaque token bound to tenant, subject, allowed commands/scopes, expiry.
3. **Uniform envelope** — Success and failure share schema (see §4).
4. **Lazy discovery** — Discovery endpoints return bounded payloads (doc/search/schema), not full registry dumps.
5. **Audit correlation** — Every invoke yields `audit_id` suitable for log correlation.
6. **Projection** — Responses may be filtered per `surface` (e.g. `model` vs `human`).

## 4. Envelope v1 (normative shape)

```json
{
  "v": 1,
  "ok": true,
  "cmd": "gh.pr.list@1.0.0",
  "surface": "model",
  "audit_id": "aud_…",
  "data": {},
  "meta": { "latency_ms": 12 },
  "error": null,
  "next": []
}
```

On failure, `ok` is `false`, `data` may be empty, `error` contains `kind`, `message`, `retryable`.

Implementations MAY add fields; agents MUST ignore unknown fields.

## 5. Command manifest (minimal)

Each command MUST declare:

- `command` (stable id, e.g. `gh.pr.list`)
- `version` (semver)
- `adapter` (implementation hint)
- `input_schema` / `output_schema` (JSON Schema subset)
- `required_scopes` (strings)
- `side_effects` (`read` | `write` | `none`)

## 6. Discovery

Implementations MUST offer discovery with **bounded** responses:

- **search** — query → ranked command ids + short blurbs
- **doc** — one command’s parameters, scopes, example
- **schema** — JSON Schema for input/output

Agents MUST NOT be required to load all manifests at session start.

## 7. Plans (optional)

ACSP implementations MAY support **plans**: ordered steps with optional `parallel` groups. A plan produces one envelope summarizing step outcomes.

## 8. Security

- Tokens MUST be validated before adapter execution (fail closed).
- Policy MAY deny by command, scope, args, tenant, or time.
- Secrets MUST NOT appear in envelopes on `surface=model`.

## 9. Conformance levels

| Level | Requirements |
|-------|----------------|
| **Core** | Registry, envelope v1, capability validation, doc |
| **Governed** | Core + audit + policy + OAuth/cap mint |
| **Composed** | Governed + plans + MCP/HTTP adapters |

## 10. Reference implementation mapping

| ACSP concept | GAX reference (`gax/` package) |
|--------------|--------------------------------|
| Shell | `gax` CLI + `gaxd` HTTP |
| Manifest | `gax/manifests/*.yaml` |
| Capability | JWT / macaroon via `gax auth cap-mint` |
| Discovery | `gax search`, `gax doc`, `gax schema` |
| Adapters | `gax/adapters/*` |

Other teams MAY implement ACSP in Go, Rust, etc. using this spec without importing Python code.

## 11. Non-goals (v1)

- Transport authentication between agent and shell (TLS/mTLS left to deployment)
- Standard OAuth server (device flow is reference-only)
- MCP wire format (adapters may wrap MCP internally)
