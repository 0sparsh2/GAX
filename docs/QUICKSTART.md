# Quickstart — 5 minutes to a governed agent

> **Measured, not estimated.** We ran this in a clean virtualenv with a fresh
> `$HOME`. Install → governed command → destructive command refused → `doctor` all
> green: **4 seconds**. Remaining gaps are listed at the bottom rather than hidden.

---

## Do you need GAX?

Be honest about this first — pitching it too early is how it gets dismissed.

**You probably don't need it yet if:** solo engineer, your own credentials, one repo,
no auditor. Raw `bash` is cheaper (GAX costs ~3.5× the tokens), simpler, and zero setup.

**You need it the moment one of these is true:**

| Trigger | The question that shows up |
|---|---|
| Agent gets write access to something real | "What stops it deleting prod?" |
| Agent acts for someone else | "Whose credentials? Who's accountable?" |
| Second agent, second person | "Which agent did that?" |
| Security review / SOC2 / an incident | "Prove what your agents did last quarter." |
| Installing MCP servers you didn't write | "Can this change what it does after I approved it?" |

---

## The 5-minute path

### 1. Install — 30s

```bash
pip install gax-cli      # [gap] not yet published; wheel builds clean
```

**Today:**

```bash
git clone https://github.com/0sparsh2/GAX && cd GAX/gax
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. `gax init` — 3s

```bash
gax init --profile k8s          # or: --profile github, or both
```

```text
GAX is ready.

  ✓ created ~/.gax
  ✓ installed profile 'k8s' (6 commands: 4 read, 1 write, 1 destructive)
  ✓ wrote config.json (random dev signing secret)
  ✓ minted 30-day read-only dev capability (11 commands) → ~/.gax/dev_cap.jwt
  ✓ started gaxd on 127.0.0.1:9477
```

Idempotent — re-running keeps a capability you already exported. The dev capability
is **read-only**: it cannot delete anything, and raising that is a conscious act.

**Profiles** are bundled command sets, so your first task isn't authoring YAML:

```bash
gax profile list          # see what each registers, by danger level
gax profile add github    # install into ~/.gax/manifests/ (survives upgrades)
```

| Profile | Commands |
|---------|----------|
| `k8s` | `pod.list` `pod.logs` `pod.describe` `deployment.list` `service.list` · `deployment.restart` (write) · `pod.delete` `namespace.delete` (destructive) |
| `github` | `pr.list` `pr.view` `issue.list` `issue.view` `run.list` · `pr.comment` (write) · `pr.merge` (destructive) |

**Installing a profile grants nothing.** It registers commands; invoking still needs a
capability naming the command, holding its scope, and reaching its ceiling. `init` only
adds the profile's **read** commands to your dev capability — write and destructive ones
stay out of reach until you mint for them deliberately.

### 3. First governed command — 5s

No exports, no flags. The CLI reads the capability `init` saved:

```bash
gax demo.echo --message "hello"
```

```json
{
  "v": 1, "ok": true, "cmd": "demo.echo@1.0.0",
  "audit_id": "aud_6fc1bf2e2ad64dbb",
  "data": { "echo": "hello" },
  "meta": { "duration_ms": 1.2 }
}
```

That `audit_id` is on disk:

```bash
grep aud_6fc1bf2e2ad64dbb ~/.gax/audit.jsonl
```

### 4. See it refuse something dangerous — 5s

The part that matters, and it needs no extra setup — the capability `init` gave you
is read-only:

```bash
export GAX_K8S_MOCK=1     # no cluster needed
gax k8s.pod.delete --namespace prod --pod web-1
```

```json
{
  "ok": false,
  "error": {
    "kind": "policy_denied",
    "message": "side_effects 'destructive' exceeds capability ceiling 'read': k8s.pod.delete"
  },
  "audit_id": "aud_cef808f0fadd41e7"
}
```

Refused **before `kubectl` was ever spawned**, and the denial is audited with its
arguments. Exit code `2`.

The sharper version of this: put the destructive command **on the token's allowlist**
and it is *still* refused, because the ceiling is a separate control.

```bash
export GAX_CAP="$(gax auth cap-mint --command k8s.pod.delete \
  --scope k8s:pods:write --max-side-effect read --raw)"

gax k8s.pod.delete --namespace prod --pod web-1
# → policy_denied: side_effects 'destructive' exceeds capability ceiling 'read'
```

**Two independent things must be wrong before something gets deleted** — that's the
property no MCP gateway has.

To actually run it, raise the ceiling deliberately, with `--dry-run` first:

```bash
export GAX_CAP="$(gax auth cap-mint --command k8s.pod.delete \
  --scope k8s:pods:write --max-side-effect destructive --raw)"

gax k8s.pod.delete --namespace prod --pod web-1 --dry-run --surface full
# → { "deleted": false, "dry_run": true, ... }
```

### 4b. Check your setup any time

```bash
gax doctor
```

```text
  ✓ gax home           ~/.gax
  ✓ config             config.json present
  ✓ registry           11 commands registered
  ✓ capability         valid from ~/.gax/dev_cap.jwt, expires in 29d 23h, ceiling=read
  ✓ gaxd sidecar       responding on 127.0.0.1:9477
  ✓ gh binary          /opt/homebrew/bin/gh
  ✓ kubectl binary     /usr/local/bin/kubectl
  ✓ audit log          ~/.gax/audit.jsonl (499 bytes)

  All checks passed.
```

Every failing check prints the exact command that fixes it.

### 5. Connect your agent — 60s

**Using Claude Code / Cursor / any MCP client [works]:**

```bash
claude mcp add gax -- gax-mcp
```

Your agent now has three tools — `gax_search`, `gax_doc`, `gax_invoke` — and nothing
else. It discovers commands at runtime instead of carrying a catalog, so the schema cost
stays constant no matter how many commands you register.

**Writing your own agent loop [works]:** three HTTP calls against `gaxd`
(`GET /search`, `GET /commands/{id}/doc`, `POST /invoke`). Working reference with a real
LLM: [`examples/agent_pr_triage.py`](../examples/agent_pr_triage.py). Provider-agnostic.

### 6. Add your own command — 90s **[works]**

The whole extension model is one YAML file in `manifests/`:

```yaml
command: k8s.namespace.delete
version: "1.0.0"
description: Delete a namespace
adapter: k8s
required_scopes: [k8s:namespaces:write]
side_effects: destructive        # ← sets the ceiling required to invoke it
input_schema:
  type: object
  properties:
    namespace: { type: string, description: Namespace to delete }
    dry_run:   { type: boolean, description: Validate without deleting }
  required: [namespace]
```

Restart `gaxd`. Every agent in the org can now call it — and *only* it, under whatever
capability they hold. No agent code changes, and **CLI flags are generated from the
schema**, so `--namespace` and `--dry-run` work immediately.

`side_effects` is load-bearing: declare it wrong and the command becomes reachable by
weaker tokens. Omit it and GAX fails closed — an undeclared command is treated as
`destructive` and refused by anything below that ceiling.

Don't hand-write these at scale:

- `gax openapi generate spec.json` — any OpenAPI spec becomes commands **[works]**
- Pinned MCP import — point at any MCP server, get manifests with frozen schema
  hashes **[gap]**

---

## How flexible is it?

**Flexible:**

- Four adapter types: `exec` (wrap a CLI), `mcp` (bridge one tool), `http` (OpenAPI), `mock` (test with no creds)
- Swap the backend under a command name — agent code doesn't change
- `--surface model|human|full` — same call, different projection for LLM / TTY / automation
- `gax plan run workflow.yaml` composes multi-step work into one envelope
- Framework- and provider-agnostic

**The limit, and it's deliberate:** an agent cannot do anything you didn't register.
No arbitrary shell. That is the security property, not a rough edge.

> **Raw bash: infinite flexibility, zero guarantees.**
> **GAX: bounded flexibility, hard guarantees.**

If you want an agent inventing shell commands on the fly, don't use GAX. If you need to
answer *"what can this thing possibly do?"* with a finite list, this is the trade.

## How adaptive is it?

**At runtime — yes.** Agents discover commands they weren't told about (`gax_search`),
read the contract (`gax_doc`), and recover from failures: `error.kind` is machine-readable,
and [SAMPLE_RUN](../examples/agent_runs/SAMPLE_RUN/) shows a real LLM hitting an
`adapter_error` and retrying successfully. Add a manifest and every existing agent can use
it immediately — no redeploy.

**In capability — deliberately no.** It cannot invent an action.

---

## The honest gaps

What a new engineer hits today, measured:

| # | Friction | Status |
|---|---|---|
| 1 | `pip install gax-cli` fails — not on PyPI | **open** — wheel builds clean; needs publishing |
| 2 | First command returned a bare `[Errno 61] Connection refused` | **fixed** — `gax init` starts the sidecar; errors now name the fix |
| 3 | `--local` then failed with `missing capability token` | **fixed** — CLI falls back to the capability `init` saved |
| 4 | Documented `sed` pipeline yielded a broken token | **fixed** — `--raw` flag |
| 5 | All commands read-only; nothing dangerous to govern | **fixed** — `k8s.pod.delete` (destructive), `k8s.deployment.scale` (write) |
| 6 | CLI flags hardcoded, so new manifests had no usable flags | **fixed** — options derive from `input_schema` |
| 7 | Wheel shipped **no policy.yaml** — every tenant allowlist silently vanished on `pip install` | **fixed** — data bundled inside the package |
| 8 | A daemon from another `~/.gax` failed every call with `Signature verification failed` | **fixed** — `/health` fingerprint; `init`/`doctor` flag the mismatch |
| 9 | 11 commands, mostly mocks; first task was authoring YAML | **fixed** — `k8s` + `github` profiles ship 11 real commands (22 total) |
| 10 | `sync_package_data.py` copies shadowed the editable sources — edits to `config/policy.yaml` appeared to do nothing | **fixed** — repo copy wins when both exist |

**Biggest remaining is #1** — publishing to PyPI. Everything else in the first-run path
is closed: `gax init --profile k8s --profile github` takes a fresh machine from nothing to
**22 registered commands** in about a second, with the destructive ones already refused by
the capability it hands out.

**Found by actually running it.** #7 and #8 were invisible from the repo — a
`pip install -e .` checkout hides both. They only appeared when installing the built
wheel into a fresh virtualenv with a clean `$HOME`, which is why the measured
walkthrough matters more than a written one.
