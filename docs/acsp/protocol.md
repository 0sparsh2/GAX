# ACSP protocol overview

## Planes

1. **Invocation** — `gax <command> [args]` visible to the model (~tens–hundreds of tokens)
2. **Control** — OAuth, vault, policy, capability mint (not in model context)
3. **Data** — Envelope v1 JSON with optional `surface=model` projection

## Capability tokens

- **JWT** (`eyJ…`) or **macaroon** (`gaxm_…`)
- Claims: `tenant_id`, `sub`, `commands[]`, `scopes[]`, `exp`
- Header: `GAX-Capability` or env `GAX_CAP`

## Adapters

| Type | Purpose |
|------|---------|
| `exec` | Wrap CLIs (`gh`, `kubectl`) |
| `mcp` | Single MCP tool per command (schema not in model) |
| `http` | OpenAPI-generated GET |
| `mock` | Tests and demos |

## Sidecar

`gaxd` listens on `127.0.0.1:9477` by default; hosted mode: `--host 0.0.0.0` with TLS termination at gateway.

## Compliance

Every invoke returns `audit_id`; logs in `~/.gax/audit.jsonl` and optional OTEL export. `gax compliance export --format csv` for SOC2-aligned bundles.
