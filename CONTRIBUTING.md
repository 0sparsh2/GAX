# Contributing to GAX / ACSP

Thank you for helping make governed agent execution more credible and portable. This repo contains the **ACSP protocol** (spec) and a **Python reference implementation** (`gax/`).

## Before you start

1. Read [docs/acsp/ACSP-1.0.md](docs/acsp/ACSP-1.0.md) for protocol vs implementation boundaries.
2. Read [eval/METHODOLOGY.md](eval/METHODOLOGY.md) before changing benchmarks or scores.
3. Open an issue for **protocol changes** (envelope shape, capability format, discovery contracts) before large PRs.

## Development setup

```bash
cd gax
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install -r ../eval/requirements.txt
pytest -q
```

## Adding a new adapter

1. Implement `run(manifest, args, *, tenant_id)` in `gax/gax/adapters/your_adapter.py`.
2. Register the adapter name in `gax/gax/adapters/base.py` (`run_adapter`).
3. Add one or more manifests under `gax/manifests/`.
4. Add tests in `gax/tests/`.
5. Document in README **Adapters** table.

**Good manifest:** clear `command`, semver `version`, JSON Schema for inputs, `required_scopes`, `side_effects`, realistic `description`.

## Adding an eval task

1. Edit `eval/tasks.yaml` — pick a `category`: `happy_path`, `error`, `truncation`, `discovery`, `multi_turn`, `plan`, `integration`.
2. Set `expect_ok` per modality where applicable.
3. Run `python eval/run_comparison.py` from repo root.
4. Do **not** add weighted composite scores; extend `eval/scoring.py` only with separate metrics.
5. Update `eval/METHODOLOGY.md` if methodology changes.

Live MCP / GitHub tasks require `GITHUB_TOKEN` and `--live-mcp`.

## Protocol changes (need discussion)

- Envelope v1 required fields
- Capability token claims
- Discovery response shapes
- New conformance levels

Open a GitHub issue labeled `protocol` with: problem, proposed change, backward compatibility, example envelope.

## Pull requests

- One logical change per PR when possible (adapter vs eval vs docs).
- Include test plan in PR description.
- For eval changes, paste aggregate table from `eval/results/comparison.md`.
- We do not require DCO; keep commits descriptive.

## Code style

- Match existing Python in `gax/`: type hints, small modules, minimal comments.
- No drive-by refactors in unrelated files.

## Questions

Open an issue or discussion on GitHub. Known gaps are tracked as issues (MCP bridge, live eval, roadmap honesty).
