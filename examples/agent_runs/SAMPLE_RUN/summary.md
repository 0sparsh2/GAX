# Agent PR triage — operational receipts

**Run ID:** `20260518T184829Z`
**Repo:** `octocat/Hello-World`
**Model:** `gemini:gemini-3.1-pro-preview`

## Governance (deterministic, real invoke + audit)

- All scenarios passed: **True**
- Audit log correlation: **True**

| Scenario | Pass | audit_id |
|---|:---:|---|
| policy_denied_command | True | `aud_c0fd20ca24554b62` |
| scope_mismatch | True | `aud_b20a128702e94aa7` |
| expired_cap | True | `aud_f0e2cba821c34640` |
| allowed_invoke | True | `aud_73957599b3d54a79` |

## Agent loop (LLM + GAX tools only)

- Completed: **True**
- Turns: **9**
- Discovery before first invoke: **True**
- Doc before first invoke: **True**
- Recovery after error: **False**
- Tool calls: search=2 doc=3 invoke=3
- Agent audit correlation: **True**

### Audit IDs (agent invokes)

- `aud_c0fd20ca24554b62`
- `aud_b20a128702e94aa7`
- `aud_f0e2cba821c34640`
- `aud_73957599b3d54a79`
- `aud_789d5f7937fa4d37`
- `aud_d92e323c38d44869`
- `aud_b4551434c21b449a`

### Final answer (excerpt)

```
FINAL_ANSWER
Drafted GitHub review comment:
"Hi @little-blueberry, thanks for your contribution! To help us review this PR, could you please add a brief description in English explaining the changes you've made and why they are beneficial? This will help us understand your contribution better. Thank you!"
```

## Files

- `governance.jsonl` — governance scenarios
- `transcript.jsonl` — full LLM + tool trace
- `manifest.json` — run metadata

## Verify audit log

```bash
grep aud_ ~/.gax/audit.jsonl | tail -20
```

