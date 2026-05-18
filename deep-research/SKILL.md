---
name: deep-research
description: >-
  Runs phased deep research with human checkpoints: outline (outline.yaml),
  field schema (fields.yaml), one JSON file per research item, optional
  PyYAML validation, then a markdown report. Adapted for Cursor from
  Weizhena/Deep-Research-skills (RhinoInsight-style control). Use when the user
  wants deep research, benchmark surveys, structured comparisons, or mentions
  Deep Research, outline+JSON workflow, or Weizhena skills.
disable-model-invocation: true
---

# Deep research (Cursor)

Upstream inspiration: [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills) and [RhinoInsight (arXiv)](https://arxiv.org/html/2511.18743v1). This project vendors the JSON validator under `.cursor/skills/deep-research/scripts/`.

## How the user runs it in Cursor

This is a **project skill**: it lives under `.cursor/skills/deep-research/` in this repo so everyone who opens the workspace can use the same workflow and validator paths.

1. In Agent chat, **attach this skill**: `@.cursor/skills/deep-research/SKILL.md`, or pick **deep-research** from the skills UI if it appears there.
2. Give a **topic** and optional **time range** for web supplementation.
3. Ask the agent to execute **Phase 1 → Phase 2 → Phase 3** below (or one phase at a time).

All paths below are **relative to the project workspace root** unless noted.

### Validator path (fixed in this repo)

```text
.cursor/skills/deep-research/scripts/validate_json.py
```

Dependency: `pip install pyyaml` (use a project venv if macOS PEP 668 blocks global install).

Example:

```bash
python3 .cursor/skills/deep-research/scripts/validate_json.py \
  -f "<topic_dir>/fields.yaml" \
  -j <topic_dir>/results/*.json
```

---

## Phase 1 — Outline (`/research` equivalent)

1. Propose **research items** (who/what to cover) and a **field framework** (what each JSON must capture).
2. **Web supplement:** search or fetch current sources; add missing items/fields for the stated time range.
3. Create a **slug** from the topic (lowercase, underscores), e.g. `ai_agent_memory_2026`.
4. Write:

```text
<topic_slug>/
  outline.yaml    # topic, items[], execution{}
  fields.yaml     # field_categories[] → fields[] (name, description, detail_level, required)
```

**`outline.yaml` minimum shape**

- `topic`: string  
- `items`: list of `{ name, category, description }`  
- `execution`: `{ batch_size, items_per_agent, output_dir }` — use `output_dir: "./<topic_slug>/results"`  

**`fields.yaml`:** copy structure from `.cursor/skills/deep-research/templates/fields.example.yaml` or from `ai_agent_context_management_research/fields.yaml` in this repo. Every field used in JSON must appear under `field_categories`.

**Human checkpoint:** confirm items and fields before Phase 2.

---

## Phase 2 — Deep item JSON (`/research-deep` equivalent)

For each item in `outline.yaml`:

1. Build **one JSON file** per item under `execution.output_dir` (e.g. `<topic_slug>/results/Item_Name.json`). Use **flat keys** at the top level matching every `name` in `fields.yaml`.
2. Fill unknowns with `[uncertain]` in the value string when needed; list those field names in top-level `"uncertain": []`.
3. Include `primary_sources` as a list of `{ "title", "url" }` objects.
4. After each file (or the whole batch), run the **validator** (command above). **Do not declare Phase 2 done until all required fields pass.**

**Resume:** skip items whose JSON already exists and validate as PASS.

**Human checkpoint:** optional between batches using `execution.batch_size`.

---

## Phase 3 — Report (`/research-report` equivalent)

1. Read `outline.yaml` (topic) and every `results/*.json`.
2. Write `<topic_slug>/report.md` with:
   - Title + methodology (cite upstream + RhinoInsight).
   - **Table of contents** with anchor links to each item.
   - **Per-item sections:** all field categories; omit or shorten fields whose value contains `[uncertain]` or whose key is listed in that JSON’s `uncertain` array.

No separate `generate_report.py` is required unless the user asks for a reusable script.

---

## Optional phases

- **Add items:** append to `outline.yaml` items list; re-run Phase 2 for new files only.  
- **Add fields:** edit `fields.yaml`; backfill new keys into existing JSON or mark `[uncertain]`.

---

## Templates

See `.cursor/skills/deep-research/templates/` for starter `fields.example.yaml` and `outline.example.yaml`.

## Examples

**Invocation**

```text
@.cursor/skills/deep-research/SKILL.md
Topic: vector databases for RAG in 2026. Run Phase 1 only; stop for my approval on outline.yaml and fields.yaml.
```

**Validate after Phase 2** (replace `<topic_slug>` with your folder, e.g. `vector_dbs_rag_2026`):

```bash
python3 .cursor/skills/deep-research/scripts/validate_json.py \
  -f "<topic_slug>/fields.yaml" \
  -j <topic_slug>/results/*.json
```
