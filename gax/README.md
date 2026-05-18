# GAX — Governed Agent eXecution

Reference implementation of the **GAX** protocol: CLI-shaped invocations, capability-gated sidecar, structured envelopes.

Research docs: [`../research/`](../research/)

## Install

```bash
cd gax
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

```bash
# Terminal A — sidecar
gaxd start

# Terminal B — client
export GAX_CAP="$(gax auth cap-mint --command gh.pr.list --command gh.pr.view --scope github:pull_request:read --export | sed 's/export GAX_CAP=//')"

gax search "pull request"
gax doc gh.pr.list
gax demo.echo --message "hello gax"
gax gh.pr.list --repo octocat/Hello-World --surface model

# Without gaxd (in-process)
gax --local demo.echo --message "local"
```

## Commands

| Command | Description |
|---------|-------------|
| `gaxd start` | HTTP sidecar on `127.0.0.1:9477` (`--host 0.0.0.0` for hosted) |
| `gax auth login` | OAuth device flow (GitHub default) |
| `gax auth cap-mint --macaroon` | Macaroon-style capability |
| `gax auth cap-from-oauth` | Mint `GAX_CAP` from stored OAuth |
| `gax plan run plan.yaml` | Multi-step / parallel plans |
| `gax openapi generate spec.json` | OpenAPI → manifests |
| `gax vault put/get KEY` | Tenant secrets (file or HashiCorp) |
| `gax compliance export` | SOC2-aligned audit CSV/JSON |
| `gax mcp.github.list_pulls` | MCP bridge (no schema in model context) |
| `gax search` / `gax doc` / `gax schema` | Lazy discovery |
| `gax <cmd>` | Any registered command |

Spec: [../docs/acsp/](../docs/acsp/)

### OAuth (GitHub)

1. Create OAuth App with **Device Flow** at GitHub Developer Settings
2. `export GAX_GITHUB_CLIENT_ID=Ov23li...`
3. `gax auth login --tenant acme`
4. `export GAX_CAP="$(gax auth cap-from-oauth --export | sed "s/export GAX_CAP=//")"`

### Plans

```bash
gax plan run examples/plan-demo.yaml
```

## Audit log

`~/.gax/audit.jsonl` — one JSON object per invocation.

## Manifests

Add YAML under `manifests/` and restart `gaxd`.
