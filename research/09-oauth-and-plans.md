# OAuth device flow & multi-step plans

Implemented in GAX v0.2 (prototype).

## OAuth (RFC 8628)

**Flow:** `gax auth login` → user visits verification URL → tokens saved → `gax auth cap-from-oauth` → `GAX_CAP` JWT for agents.

| Piece | Location |
|-------|----------|
| Provider config | `gax/config/oauth_providers.yaml` |
| Device flow | `gax/gax/oauth.py` |
| Token storage | `~/.gax/tokens/<tenant>/<provider>.json` (mode 600) |
| gh adapter | Uses `GH_TOKEN` from stored GitHub OAuth when present |

**GitHub setup:** OAuth App with Device Flow enabled; `export GAX_GITHUB_CLIENT_ID=...`

## Plans

**Run:** `gax plan run examples/plan-demo.yaml`

Plans are **sequential** steps with template args:

```yaml
steps:
  - id: list
    command: gh.pr.list
    args: { repo: octocat/Hello-World, limit: 5 }
  - id: view
    command: gh.pr.view
    args:
      repo: octocat/Hello-World
      number: "{{ steps.list.data.items[0].number }}"
```

**Output:** single envelope with `data.steps` (per-step results) and `data.summary`.

**Roadmap:** parallel branches, conditional steps, OPA gates between steps.

## Architecture note

OAuth sits in the **control plane**; plans run in **gaxd** / executor without expanding model context for intermediate payloads when `surface=model`.
