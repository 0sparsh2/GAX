# GAX prototype guide (v0.1)

Implementation lives in [`../gax/`](../gax/).

## Components

| Piece | Path | Role |
|-------|------|------|
| CLI | `gax/cli.py` | `gax`, `gax search`, `gax doc`, command aliases |
| Daemon | `gax/daemon.py` | `gaxd` HTTP on port **9477** |
| Executor | `gax/executor.py` | cap → policy → adapter → envelope |
| Registry | `gax/registry.py` | YAML manifests |
| Caps | `gax/caps.py` | JWT mint/verify (dev) |
| Audit | `gax/audit.py` | `~/.gax/audit.jsonl` |
| Projection | `gax/projection.py` | `surface=model` truncation |

## Registered commands (default)

- `demo.echo` — mock adapter, no `gh` required
- `gh.pr.list` — exec `gh` or mock fallback
- `gh.pr.view` — exec `gh` or mock fallback

## HTTP API

```bash
curl -s http://127.0.0.1:9477/health
curl -s "http://127.0.0.1:9477/search?q=pull"
curl -s http://127.0.0.1:9477/commands/gh.pr.list/doc
```

Invoke:

```bash
curl -s -X POST http://127.0.0.1:9477/invoke \
  -H "Content-Type: application/json" \
  -H "GAX-Capability: $GAX_CAP" \
  -d '{"command":"demo.echo","args":{"message":"api"},"surface":"model"}'
```

## Adding a command

1. Create `gax/manifests/my.cmd.yaml`
2. Implement adapter handler if not mock/exec pattern
3. Restart `gaxd`
4. `gax doc my.cmd`

## Tests

```bash
cd gax && pytest -q
```

## Changelog

| Date | Change |
|------|--------|
| 2026-05-18 | Initial prototype + research hub |

_Add rows as the prototype evolves._
