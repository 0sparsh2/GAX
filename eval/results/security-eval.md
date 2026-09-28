# Security benchmark

Generated 2026-09-28T03:42:32.450248+00:00 by `eval/run_security_eval.py`.

## A. Side-effect ceiling

41 mutating commands of 87 (3 write, 38 destructive).

| Check | Result |
|---|---:|
| Read-only capability refused (command explicitly allowlisted) | **41/41** |
| Capability at the command's level allowed | **41/41** |
| Leaks (read cap got through) | 0 |
| Over-blocks (correct cap refused) | 0 |

End to end: `k8s.namespace.delete` with a read-only capability → `policy_denied`, exit 2, audited: True.

## B. Pin tampering (live stdio MCP server that mutates itself)

| Server behaviour | ok | error kind | retryable | audited |
|---|---|---|---|---|
| honest | True | — | — | True |
| description | False | pin_mismatch | False | True |
| schema | False | pin_mismatch | False | True |
| rename | False | pin_mismatch | False | True |
| vanish | False | pin_mismatch | False | True |

**4/4 attacks refused before the tool ran**; honest server passed: True.

## C. Pin false positives (real public MCP servers)

65 pins re-verified against live servers: {'ok': 65}. False alarms: **0**.
