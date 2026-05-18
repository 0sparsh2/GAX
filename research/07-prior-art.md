# Prior art & references

## OAuth for CLIs

- RFC 8628 — OAuth 2.0 Device Authorization Grant
- [cli/oauth](https://github.com/cli/oauth) — Go library for device + web flow
- [oauth2c](https://github.com/SecureAuthCorp/oauth2c) — CLI for testing OAuth flows

**GAX uses:** tokens live in `gaxd` / OS keychain; model never sees refresh tokens. MVP uses dev JWT mint.

## Agent-first CLI design

- [CLI Spec](https://clispec.dev/) — structured output, schema commands
- [CLI Agent Spec](https://github.com/cli-agent-spec/cli-agent-spec) — failure modes, exit codes
- [Joel Claw — CLI design for AI agents](https://joelclaw.com/cli-design-for-ai-agents) — JSON-only, `next_actions`

**GAX uses:** envelope v1, semantic exit codes, optional `next` hints.

## Capability tokens

- Google — [Macaroons: Cookies with Contextual Caveats](https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/)
- [SatGate — Agent Capability Tokens](https://satgate.io/agent-capability-tokens)

**GAX target:** macaroon attenuation per task; MVP JWT scopes.

## Identity & audit

- [Teleport Workload Identity](https://goteleport.com/docs/machine-workload-identity/workload-identity/workload-attestation/) — SPIFFE SVIDs, attestation in audit logs

**GAX target:** optional SPIFFE for `gaxd` in Kubernetes.

## MCP optimizations

- Anthropic — programmatic tool calling (filesystem/SDK discovery)
- Cloudflare — Code Mode (`search` + `execute` over OpenAPI)

**GAX parallel:** lazy discovery without loading full schemas; differs by CLI-shaped commands and cap-per-invoke.

## Research workflow

- [deep-research/SKILL.md](../deep-research/SKILL.md) — phased outline → JSON → report

Add citations to this file as new sources are validated.
