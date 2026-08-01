# GAX — Governed Agent eXecution

**Your MCP gateway can't see `bash`. GAX governs both.**

GAX is a governed execution layer for agent shell commands. Agents get a
command-line-shaped surface; OAuth, policy, audit, and tenancy live in a sidecar the
model never sees.

The guarantee: **an agent can only run commands you registered, every invoke is checked
against a capability token before any backend runs, and every invoke produces an
`audit_id`.**

It **complements MCP** rather than competing with it — MCP servers become adapters behind
stable command names, so one policy file and one audit trail cover both your MCP calls
and your shell calls.

Full docs, research, and evaluation: **https://github.com/0sparsh2/GAX**

---

## Install

```bash
pip install gax-cli
gax init --profile k8s --profile github
```

That creates `~/.gax`, mints a 30-day **read-only** capability, starts the sidecar, and
registers 22 real commands. Measured on a clean machine: about a second.

```bash
gax k8s.pod.logs --pod web-1     # works immediately, no exports needed
gax doctor                       # diagnose config, capability, sidecar, backends
```

## See it stop something dangerous

```bash
export GAX_K8S_MOCK=1            # no cluster needed
gax k8s.namespace.delete --namespace prod
```

```json
{
  "ok": false,
  "error": {
    "kind": "policy_denied",
    "message": "side_effects 'destructive' exceeds capability ceiling 'read'"
  },
  "audit_id": "aud_cef808f0fadd41e7"
}
```

Refused before `kubectl` was ever spawned, and the denial is audited with its arguments.

Even if the command sits on the token's allowlist it is *still* refused, because the
danger ceiling is a separate control — **two independent things must be wrong before
something gets deleted.**

To run it, raise the ceiling deliberately, with `--dry-run` available first:

```bash
export GAX_CAP="$(gax auth cap-mint --command k8s.namespace.delete \
  --scope k8s:namespaces:write --max-side-effect destructive --raw)"

gax k8s.namespace.delete --namespace staging --dry-run
```

## Use it from any MCP client

```bash
claude mcp add gax -- gax-mcp
```

Publishes exactly three tools — `gax_search`, `gax_doc`, `gax_invoke` — keeping the
registry behind them, so schema cost stays constant no matter how many commands you
register.

## Add your own command

One YAML file in `~/.gax/manifests/`:

```yaml
command: db.migration.run
version: "1.0.0"
description: Apply pending migrations
adapter: exec
required_scopes: [db:schema:write]
side_effects: destructive     # sets the ceiling required to invoke it
input_schema:
  type: object
  properties:
    env:     { type: string, description: Target environment }
    dry_run: { type: boolean, description: Validate without applying }
  required: [env]
```

CLI flags are generated from the schema. Omit `side_effects` and GAX fails closed —
undeclared commands are treated as `destructive`.

Generate manifests instead of writing them: `gax openapi generate spec.json`.

## Commands

| | |
|---|---|
| `gax init` / `gax doctor` | Setup and diagnostics |
| `gax profile list` / `add` | Bundled command sets (`k8s`, `github`) |
| `gax search` / `doc` / `schema` | Lazy discovery |
| `gax <command>` | Invoke a registered command |
| `gax auth cap-mint` | Mint a capability (`--max-side-effect read\|write\|destructive`) |
| `gax auth login` | OAuth 2.0 device flow |
| `gax plan run <file>` | Multi-step / parallel workflows |
| `gax vault put` / `get` | Tenant secrets (file or HashiCorp) |
| `gax compliance export` | SOC2-aligned audit export |
| `gaxd start` / `stop` / `status` | Sidecar lifecycle |
| `gax-mcp` | Run GAX as an MCP server (stdio) |

Audit log: `~/.gax/audit.jsonl`, one JSON object per invocation, including denials.

## Honest scope

- Raw CLI costs ~3.5× fewer tokens than GAX on like-for-like tasks. Governance is not
  free, and we publish that number rather than a flattering one.
- Vault, SPIFFE, and OPA integrations are hooks and stubs, not production features.
- The evaluation is a self-assessment by the author; methodology and known defects are
  documented in the repository.

MIT licensed. Issues and contributions: https://github.com/0sparsh2/GAX
