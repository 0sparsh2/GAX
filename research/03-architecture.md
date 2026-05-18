# GAX architecture

## System context

![GAX system context](./diagrams/png/architecture.png)

```mermaid
flowchart TB
  subgraph model_ctx["Model context (small)"]
    LLM["LLM / Agent"]
    INV["gax gh.pr.list --surface model"]
    DOC["gax doc / gax search"]
  end

  subgraph control["Control plane (not in context)"]
    AUTH["OAuth / SSO broker"]
    CAP["Capability issuer"]
    POL["Policy engine"]
    AUD["Audit / SIEM"]
    TEN["Tenant credential vault"]
  end

  subgraph runtime["gaxd sidecar"]
    GAXD["gaxd"]
    REG["Command registry"]
    PROJ["Projection layer"]
    ADP["Adapters"]
  end

  LLM --> INV
  LLM --> DOC
  INV --> GAXD
  DOC --> GAXD
  GAXD --> AUTH
  GAXD --> CAP
  GAXD --> POL
  GAXD --> TEN
  GAXD --> AUD
  GAXD --> REG
  GAXD --> PROJ
  GAXD --> ADP
  PROJ --> LLM
```

Source: [diagrams/architecture.mmd](./diagrams/architecture.mmd)

## Three planes

![Three planes](./diagrams/png/planes.png)

```mermaid
flowchart LR
  I["Invocation plane\n(short commands)"]
  C["Control plane\n(auth, caps, policy, audit)"]
  D["Data plane\n(envelope + schemas)"]

  I -->|"gax CLI"| GAXD["gaxd"]
  GAXD --> C
  GAXD --> D
```

Source: [diagrams/planes.mmd](./diagrams/planes.mmd)

## Invocation sequence

![Invocation sequence](./diagrams/png/sequence-invoke.png)

```mermaid
sequenceDiagram
  participant A as Agent / LLM
  participant C as gax CLI
  participant D as gaxd
  participant P as Policy
  participant X as Adapter (gh)
  participant L as Audit log

  A->>C: gax gh.pr.list --surface model
  C->>D: POST /invoke + GAX-Capability
  D->>D: Verify cap + tenant
  D->>P: Allow command?
  P-->>D: allow
  D->>L: audit_id created
  D->>X: execute(args)
  X-->>D: raw result
  D->>D: validate schema + project
  D-->>C: envelope JSON
  C-->>A: stdout (model surface)
```

Source: [diagrams/sequence-invoke.mmd](./diagrams/sequence-invoke.mmd)

## Prototype layout (this repo)

```
gax/
  gax/           # Python package
    cli.py       # gax entrypoint
    daemon.py    # gaxd HTTP server
    envelope.py
    caps.py
    registry.py
    projection.py
    policy.py
    audit.py
    adapters/
  manifests/     # Command manifests (YAML)
  schemas/       # JSON Schema
```

## Adapter model

Each command manifest declares:

- `command` / `version`
- `adapter` — `exec`, `http`, `mock`
- `required_scopes` — cap must include
- `input_schema` / `output_schema`
- `side_effects` — `read` | `write` | `destructive`

MCP servers can be wrapped as adapters without exposing MCP tool schemas to the model.
