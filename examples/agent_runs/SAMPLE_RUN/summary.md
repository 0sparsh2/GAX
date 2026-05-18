# Agent PR triage — operational receipts

**Run ID:** `20260518T193305Z`
**Repo:** `octocat/Hello-World`
**Model:** `gemini:gemini-2.5-flash-lite`

## Governance (deterministic, real invoke + audit)

- All scenarios passed: **True**
- Audit log correlation: **True**

| Scenario | Pass | audit_id |
|---|:---:|---|
| policy_denied_command | True | `aud_6d171edc76924b3d` |
| scope_mismatch | True | `aud_b9b8afe214bd4f86` |
| expired_cap | True | `aud_c78e05d063554cf4` |
| allowed_invoke | True | `aud_a3ecf6bc4f2546ea` |

## Agent loop (LLM + GAX tools only)

- Gemini model used: **gemini-2.5-flash-lite**
- Gemini API key: **fallback_key**
- Recovery probe (pre-LLM): **True** (`adapter_error` → retry ok=True)
- Completed: **True**
- Turns: **7**
- Discovery before first invoke: **True**
- Doc before first invoke: **True**
- Recovery after error: **True**
- Tool calls: search=2 doc=3 invoke=5
- Agent audit correlation: **True**

### Audit IDs (agent invokes)

- `aud_6d171edc76924b3d`
- `aud_b9b8afe214bd4f86`
- `aud_c78e05d063554cf4`
- `aud_a3ecf6bc4f2546ea`
- `aud_3f495338b39840f4`
- `aud_c762b61d3d444faa`
- `aud_a02644c1b984473d`
- `aud_7721441aa4fc4c18`
- `aud_002ad5c9ac7e4ca6`

### Final answer (excerpt)

FINAL_ANSWER
Hi there! Thanks for your contribution. This PR seems to be a very small change. Could you please provide a bit more context on what this change is intended to do? This will help us review it more effectively. Thanks!

## Files

- `governance.jsonl` — governance scenarios
- `transcript.jsonl` — full LLM + tool trace
- `manifest.json` — run metadata

## Verify audit log

```bash
grep aud_ ~/.gax/audit.jsonl | tail -20
```

