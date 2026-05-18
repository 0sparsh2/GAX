# GAX proposal: Governed Agent eXecution

## Thesis

Do not choose MCP **or** CLI. Introduce a **governed execution protocol** that:

1. **Feels like a CLI** to the model (short commands, lazy `doc` / `search`)
2. **Embeds governance** in a sidecar the model never sees (OAuth, tenancy, audit, policy)
3. **Returns a stable envelope** for automation (`data`) and a **projection** for the model (`surface=model`)

## Name

**GAX** — Governed Agent eXecution  
Alternate protocol name: **ACSP** (Agent Capability Shell Protocol)

## Five invariants

### 1. Split planes

| Plane | In model context? | Holds |
|-------|-------------------|--------|
| Invocation | Yes | `gax gh.pr.list --repo org/r --surface model` |
| Control | No | OAuth, cap mint/revoke, OPA policy, tenant vault, audit bus |
| Data | Filtered | Full JSON in envelope; model may see truncated `data` |

### 2. Capability per call (or short batch)

Attenuated token bound to: `tenant_id`, `subject`, allowed commands, budgets (calls, rows, bytes, TTL), optional `workflow_id`.

Verified in `gaxd` **before** any adapter runs. Fail closed.

### 3. Uniform envelope v1

Every command returns: `ok`, `cmd`, `schema`, `audit_id`, `surface`, `data`, `meta`, `error`, optional `next` (HATEOAS hints).

### 4. Lazy discovery

```bash
gax search "open pull requests"
gax doc gh.pr.list
gax schema gh.pr.list
```

Registry of thousands of commands lives in `gaxd` — not in the system prompt.

### 5. Composable without arbitrary shell

- Filters via `--jq` inside `gaxd` after policy check
- Multi-step: `gax plan run plan.yaml` (DAG executor, one envelope out)

No `bash -c` for agents.

## Example session

```bash
gax auth login --tenant acme-corp
export GAX_CAP="$(gax auth cap-mint --command gh.pr.list --ttl 300)"
gax gh.pr.list --repo acme/api --surface model
```

Response (model surface, truncated):

```json
{
  "v": 1,
  "ok": true,
  "cmd": "gh.pr.list@1.0.0",
  "audit_id": "aud_…",
  "surface": "model",
  "data": { "items": [ … ] },
  "meta": { "truncated": true, "row_count": 10 }
}
```

## Relation to hybrid

Hybrid = two runtimes, two auth stories. **GAX** = one runtime; MCP servers and raw CLIs become **adapters** behind registered commands.

→ Architecture: [03-architecture.md](./03-architecture.md)  
→ Protocol: [04-protocol-envelope.md](./04-protocol-envelope.md)
