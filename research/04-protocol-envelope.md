# GAX protocol: envelope v1 & capabilities

## Envelope v1

Canonical schema: [`../gax/schemas/envelope.v1.json`](../gax/schemas/envelope.v1.json)

| Field | Type | Description |
|-------|------|-------------|
| `v` | integer | Protocol version (always `1` for v1) |
| `ok` | boolean | Success flag |
| `cmd` | string | Command id with version, e.g. `gh.pr.list@1.0.0` |
| `audit_id` | string | Correlation id for audit log |
| `schema` | string | URI of output schema |
| `surface` | string | `model` \| `human` \| `full` |
| `data` | object | Structured payload |
| `meta` | object | `truncated`, `cursor`, `row_count`, `duration_ms`, … |
| `error` | object \| null | `{ "kind", "message", "retryable" }` |
| `next` | array | Optional suggested follow-up commands |

### Surfaces

| Surface | Consumer | Behavior |
|---------|----------|----------|
| `model` | LLM | Truncate rows, redact secrets, cap JSON size |
| `human` | Terminal TTY | Optional pretty tables (future) |
| `full` | Automation | No projection; full validated output |

### Exit codes (CLI process)

| Code | Meaning |
|------|---------|
| 0 | `ok: true` |
| 1 | Generic failure |
| 2 | Policy denied |
| 3 | Capability invalid / expired |
| 4 | Command not found |
| 5 | Adapter / backend error |
| 6 | Schema validation failed |

## Capability tokens (MVP: JWT)

Production target: macaroon attenuation (Google macaroons paper; agent capability token vendors).

MVP (`gax` prototype) uses HS256 JWT in header `GAX-Capability` or env `GAX_CAP`.

Claims:

```json
{
  "sub": "user@acme.com",
  "tenant_id": "acme-corp",
  "scopes": ["github:pull_request:read"],
  "commands": ["gh.pr.list", "gh.pr.view"],
  "exp": 1710000000,
  "budget": { "max_calls": 100, "max_rows": 500 }
}
```

Mint (dev):

```bash
gax auth cap-mint --tenant acme-corp --command gh.pr.list --ttl 300
```

## HTTP API (gaxd)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/commands` | List registered commands |
| GET | `/commands/{id}/doc` | Doc stub |
| GET | `/search?q=` | Fuzzy search |
| GET | `/schema/{id}` | JSON Schema |
| POST | `/invoke` | Run command |

### POST /invoke body

```json
{
  "command": "gh.pr.list",
  "args": { "repo": "org/repo", "limit": 10 },
  "surface": "model",
  "jq": null
}
```

Headers: `GAX-Capability: <jwt>`

## Discovery token budget (design target)

| Operation | Target size |
|-----------|-------------|
| `gax search` (3 hits) | ~150–250 tokens |
| `gax doc <cmd>` | ~80–120 tokens |
| `gax schema <cmd>` | On demand only |

Compare: naive MCP GitHub server ~44k+ tokens upfront.
