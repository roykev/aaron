# aaron-course-reports

Builds AaronOwl's **full lecturer report** for a course, from the lesson reports Aaron already produces:

- **מה לימדתי** (what I taught): course time by unit and sub-topic, interactions and questions per lesson
- **איך לימדתי** (how I taught): 16 pedagogic dimensions, recurring owl recommendations and their adoption, progress
- **מה למדו** (what students learned): the course learning report, when one exists

Output: one self-contained HTML file and/or one Markdown file, plus `analysis.json` (the editable layer between data and design).

## Quick start

```bash
pip install -e ".[llm]"            # core has no dependencies; [llm] adds the Anthropic SDK
export ANTHROPIC_API_KEY=...        # optional; without it the prose is deterministic

course-reports build \
  --reports export.json \           # Aaron lectures export (rows with snapshot_report + lecturer_report)
  --learned learning_report.md \    # optional: course learning report
  --course course.json \            # {"name": "מבוא לפסיכולוגיה", "student_noun": "סטודנטיות"}
  --out out/ --slug psychology --format both
```

The command writes `out/psychology.html`, `out/psychology.md` and `out/psychology.analysis.json`.

## Markdown output

The Markdown follows the HTML layout and uses the same anchor ids (`#overview`, `#taught`, `#how`, `#learned`, `#l4`). It relies on inline HTML (`<details>`, `<sub>`, `<span style>`), which GitHub, VS Code, Obsidian and Typora all render. Colors use the HTML palette through inline styles: VS Code, Obsidian and Typora show them, and GitHub strips them and shows the same text uncolored. Every colored mark (●○ levels, ■□ lesson strips, ▼▲ scores, status labels) still reads without color. No emoji.

## Review loop

1. Build. Read the report.
2. Edit `psychology.analysis.json` (any text, a status, a dimension mapping), or put small edits in an overrides file.
3. Re-render without recomputing: `course-reports build ... --analysis out/psychology.analysis.json`, or recompute with `--overrides edits.json`.

## How it works

| Layer | What | LLM |
| --- | --- | --- |
| 0 · ingest | parse the export, class reports and learning report | no |
| 1 · signals | map every report item to a dimension (Hebrew lexicon; optional embeddings), dimension positions, recurring recommendations and adoption, course units | no |
| 2 · facts | every number the report can show | no |
| 3 · narrative | one call turns facts into Hebrew prose. Guards reject invented numbers and banned phrasing, and failing sections fall back to deterministic copy | yes, optional |

Commands: `build`, `batch`, `items` (list report items and their mapped dimensions), `eval` (compare with a hand-made `golden_analysis.json`).

Dimension levels are computed once, in `signals.dim_state`, scaled to the number of lessons, and stored in `analysis.dims[id]` (`level`, `level_he`, `improving`, `pos`). Both renderers read them. A re-render with `--analysis` or `--overrides` recomputes them from `item_dims`.

## Batch

```bash
course-reports batch --manifest courses.json --out out/ [--no-llm | --no-llm-batch]
```

`courses.json` is a list of courses: the `course.json` fields plus `reports` (path or list), optional `learned` and `slug`. Relative paths resolve against the manifest folder. Each course writes its reports, plus a log in `out/logs/<slug>.log`. `out/summary.json` holds the status, lesson count, narrative source, guard violations and warnings for each course. A failed course does not stop the batch, and the command exits 1 if any course failed.

By default, `batch` sends every course's narrative call to `claude-sonnet-5-5` as one Message Batch, at half price. Use `--no-llm-batch` to call the model per course instead. The batch usually finishes in minutes and can take up to 24 hours. The batch id is saved to `out/llm_batch.json`, so an interrupted run resumes with `--batch-id`. Guards, the single retry (a direct call) and the fallback still run per course. A request that fails inside the batch falls back to a direct call.

Every LLM build records the model, calls, tokens and estimated cost under `_meta.narrative` (prices are in `narrative.PRICES`). `summary.json` includes them per course. Measured on the examples: `claude-sonnet-5-5` costs about $0.065–0.072 per course, or about $0.035 through the batch. `claude-haiku-5-5` costs about $0.004 (about $0.002 through the batch). Use `--model` or `AARON_LLM_MODEL` to choose.

## Inputs

**export.json**

```json
{"rows": [{"name": "שיעור 4", "event_time": "2025-11-26 14:00:00+00",
           "snapshot_report": "# Teaching Snapshot ...", "lecturer_report": "# Class Analysis Report ..."}]}
```

- `snapshot_report` sections: title, `המסר המרכזי`, `משך השיעור`, `Outstanding Performance`, `Long-Term Growth Opportunity`, `Successful Practices`, `Opportunities for Enhancement`, `Recommended Actions for Next Session` (items in `<details>`).
- `lecturer_report` sections: `Class Structure` (sections with times), `Examples from Class`, `Questions for Students`, `Class Interactions`, `Challenging Topics`.

**learning_report.md**: Aaron's course learning report (inline-styled HTML), shown as-is and parsed for KPIs and lesson scores.

**course.json**: `name` (required), `student_noun`, optional `units` (`[{"name", "short", "lessons"}]`) and `title`.

## Development

```bash
pip install -e ".[dev]" && pytest -q
pip install -e ".[browser]" && playwright install chromium   # optional: enables the offline HTML browser test
```

The LLM tests replay real model replies from `tests/fixtures/llm/` and never call the API. To re-record them after changing `SYSTEM`, `SCHEMA` or the facts, set `AARON_LLM_RECORD=tests/fixtures/llm/<course>` on a real `build`. The Heebo font (SIL OFL, `assets/heebo-OFL.txt`) is embedded, so the HTML makes no network requests.

See `AGENT_TASK.md` for the roadmap and the rules the code must keep, and `docs/GUIDELINES.md` for content and design rules.
