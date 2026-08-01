# Case study results: 3-turn PR triage

Repo: `octocat/Hello-World` · Counter: tiktoken cl100k_base

| modality | tokens | ok | notes |
|---|---:|---:|---|
| cli | 154 | True |  |
| mcp_naive_43 | 44062 | True | includes 44026 schema tax/session (Scalekit fixture) |
| gax | 692 | True |  |
| gax_mcp_bridge | 725 | True |  |

Regenerate: `python eval/case_study/run_case_study.py`

