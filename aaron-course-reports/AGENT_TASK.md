# Task: automated course-level lecturer reports (AaronOwl)

You are taking over a working Python package that builds a **full lecturer report for a course** from the per-lesson reports Aaron already produces. Your job is to harden it for production and close the open items below. Do not redesign the reports. Their content and visual rules are fixed in `docs/GUIDELINES.md`.

## 1. What the product is

For each course, one report with an overview and three sub-reports, plus a page per lesson:

| Report | Question | Source |
| --- | --- | --- |
| 01 · מה לימדתי (what I taught) | Where did course time go, what sub-topics, how much interaction | `lecturer_report` (Class Analysis) per lesson |
| 02 · איך לימדתי (how I taught) | 16 pedagogic dimensions, recurring owl recommendations and whether they were adopted, progress | `snapshot_report` (Teaching Snapshot) per lesson |
| 03 · מה למדו (what students learned) | KPIs, struggles, what worked, quiz vs assessment gap, risk tiers | course learning report (`learning_report.md`), optional |

If the learning report is missing, report 03 is shown as "missing student feedback". If class reports are missing, report 01 is omitted. Outputs: one self-contained **HTML** file, and/or one polished **Markdown** file, plus the `analysis.json` that both are rendered from.

## 2. Current state (2026-10-19: P0 done, 27 tests green)

```
pip install -e ".[dev,llm,browser]" && playwright install chromium
pytest -q
course-reports build --reports examples/psychology/export.json --learned examples/psychology/learning_report.md \
  --course examples/psychology/course.json --out out --slug psychology            # LLM prose (needs ANTHROPIC_API_KEY)
course-reports build ... --no-llm                                                    # deterministic prose
course-reports batch --manifest courses.json --out out                               # many courses, LLM via the Batch API
course-reports eval --reports examples/psychology/export.json --course examples/psychology/course.json \
  --learned examples/psychology/learning_report.md --golden examples/psychology/golden_analysis.json
```

Measured against the hand-made analyses (`examples/*/golden_analysis.json`), with the lexicon classifier:

| Course | Items | Top-1 dimension in golden | Any overlap | Dimension level within one step |
| --- | --- | --- | --- | --- |
| Psychology | 90 | 88.9% | 94.4% | 16/16 |
| Informal education | 90 | 91.1% | 94.4% | 16/16 |

Layer 3 has run against the real API. Both examples build with `source: llm` and zero guard violations on the first call, with no retry. The raw replies are the replay fixtures in `tests/fixtures/llm/`.

**LLM choice (decided by the user):** `claude-sonnet-5-5`, sent through the Message Batch API in `batch` mode (the default). The measured cost is about $0.065–0.072 per course with a direct call, and about $0.035 through the batch. `claude-haiku-5-5` (~$0.004) was tested and rejected. It passed the guards, but its prose was more generic, it repeated the tile labels ("בדרגה הדורשת תשומת לב"), and its tone slipped ("לא נצפה שיפור").

## 3. Architecture and non-negotiable rules

```
Layer 0  ingest.py      parse export JSON / snapshot txt / class reports / learning report         (code)
Layer 1  signals.py     item -> dimension mapping, dimension state, recommendation themes,
                        adoption, units                                                             (code, data-driven)
Layer 2  facts.py       every number the report may show                                            (code)
Layer 3  narrative.py   ONE LLM call: facts -> prose, with guards and per-section fallback          (LLM)
         pipeline.py    assembles analysis.json (the render contract)
         render_html.py + assets/template.html, render_md.py
```

Rules, enforced in code and tests. Keep them:

1. **No LLM before Layer 3.** All metrics, mappings, statuses and groupings are computed in code. The LLM only phrases facts. Do not add LLM calls to layers 0-2. An embedding model in layer 1 is allowed, because it is not generative.
2. **Every number comes from facts.** `narrative.check()` rejects any number not present in the facts. It retries once with the violations, then replaces only the failing sections with deterministic copy. Never loosen this guard to make output pass.
3. **Observational framing.** Adoption is "a matching practice was observed in a later lesson", which is correlation and never causation. Keep that sentence in both renderers.
4. **Privacy.** Individual student cards from the learning report are never passed to the LLM (`learned_facts()` drops them). They appear only in the as-is learning report HTML, for the lecturer.
5. **House style (Hebrew).** No em dashes (auto-fixed), no "לא X אלא Y" construction (rejected), no emoji, a positive tone that leads with strengths, short sentences.
6. **The render contract is `analysis.json`.** Both renderers consume only `analysis.json` plus parsed inputs. A human can edit `analysis.json` and re-render with `--analysis`, or apply `--overrides`. Keep that loop working.

## 4. Inputs contract

- `export.json`: `{"rows": [{"name": "שיעור 4", "event_time": "...", "snapshot_report": "<md+html>", "lecturer_report": "<md+html>"}]}`. Rows are sorted by `event_time`, and the lesson number is taken from `name`. Rows without `snapshot_report` are skipped, with a note.
- `learning_report.md`: Aaron's inline-styled HTML course learning report. It is rendered as-is in report 03 and also parsed for KPIs and per-lesson scores.
- `course.json`: `{"name": "...", "student_noun": "סטודנטים|סטודנטיות", "units": [{"name","short","lessons"}] (optional), "title" (optional)}`.

Full format notes: `README.md`. Real examples: `examples/psychology` (all three reports) and `examples/informal` (no learning report).

## 5. Work items (in priority order)

### P0. Make it production-ready (done 2026-10-19; see CHANGELOG.md)

1. **Run Layer 3 for real.** Verify the model id (`AARON_LLM_MODEL`, default `claude-sonnet-5-5`), run both examples, and compare the prose with the golden hub and hero text. Tune `SYSTEM` and `SCHEMA` in `narrative.py` until no guard violations remain on both examples. Save the raw LLM replies as fixtures and add a record/replay test so CI never calls the API.
2. **Batch mode.** Add `course-reports batch --manifest courses.json --out DIR`. The manifest is a list of courses, each with `{course.json fields, reports, learned}`. Write per-course logs, keep going on failure, and exit non-zero if any course failed. Write a `summary.json` with per-course status, narrative source and guard violations.
3. **Input robustness**, each with a fixture test:
   - missing `snapshot_report`;
   - class-report sections without titles (seen in psychology lesson 11 and informal lessons 3, 5 and 6; warn and render "אין חלוקה לנושאים");
   - duplicated lesson numbers;
   - English section headers (`Key Message`, `The Solution`);
   - a course with 4 lessons and one with 20.
4. **Lesson-count scaling.** Dimension levels use absolute thresholds tuned on 10 lessons (`signals.LEVELS`). Normalize by the number of lessons, and make `template.html` read the computed level from `analysis.dims[id]` instead of recomputing it in JS. Today the rule exists in both Python and JS and must match exactly. Remove the duplication.

### P1. Quality (open)

Ideas raised while doing P0, not yet scheduled:
- **Cheaper Layer 3:** move `dim_notes` (45% of output tokens), `rec_notes` and the hub card `points` to deterministic templates. The LLM would keep the hero, insights, hub `sub` and links. Estimated saving is about 50% per course.
- **Hours mismatch between views:** report 01 sums Class Analysis section durations (14:22), while report 02 sums snapshot `משך השיעור` (14:24). Both are correct for their source, but the totals differ.

5. **Embedding classifier (Layer 1.5).** `signals.EmbeddingClassifier` with `paraphrase-multilingual-MiniLM-L12-v2` is written but untested (the model could not be downloaded in the build environment). Evaluate it with `course-reports eval --classifier embeddings`. Adopt it as default only if it beats the lexicon on both goldens (any overlap ≥ 0.944 and level within one = 16/16). Otherwise keep the lexicon and use embeddings only to break ties.
6. **Recommendation taxonomy.** `assets/recommendation_themes.json` holds 14 themes. Run the pipeline on more courses, list opportunities and actions that match no theme (add a `course-reports unmatched` command), and extend the taxonomy. Theme names and `next_*` copy follow the house style.
7. **Learning report parsing.** `parse_learning_report()` keys on inline style attributes, which is brittle. Rewrite it to key on visible labels and headings, or better, ask the Aaron backend to emit the learning report's JSON next to the HTML and parse that.
8. **Sharing mode.** Add `--no-student-cards` to strip individual student cards from the as-is learning report, for reports shared beyond the lecturer.

### P2. Nice to have

9. Markdown: `--md-split` for a folder with an index plus one file per lesson.
10. PDF export of the HTML via Playwright (`page.pdf`, A4, print CSS).
11. Units: optional single structural LLM call that only renames deterministic units. It must not regroup lessons, so the time shares stay code-computed.

## 6. Acceptance criteria

- `pytest -q` is green. New tests cover every P0 item.
- Both examples build in HTML and Markdown with the real LLM, with zero remaining guard violations, and `_meta.narrative.source == "llm"`.
- `course-reports eval` on both goldens: any overlap ≥ 0.94 and dimension level within one step for 16/16.
- No `__PLACEHOLDER__` left in the HTML. The HTML opens offline with no console errors (Playwright check in CI).
- Re-rendering an edited `analysis.json` with `--analysis` reproduces the edit in both formats.
- A course with no learning report shows the "missing student feedback" card. A course with no class reports shows no report 01.

## 7. File map

| Path | Purpose |
| --- | --- |
| `src/course_reports/ingest.py` | Layer 0 parsers, `load_course()` |
| `src/course_reports/signals.py` | Layer 1: classifiers, dimension state, themes and adoption, units |
| `src/course_reports/facts.py` | Layer 2: facts and the allowed-numbers set |
| `src/course_reports/narrative.py` | Layer 3: prompt, schema, guards (digits and Hebrew number words), fallback, usage and cost, record (`AARON_LLM_RECORD`) |
| `src/course_reports/llm_batch.py` | Layer 3 through the Message Batch API: submit, wait, collect, resume (`--batch-id`) |
| `src/course_reports/cli.py` | `build`, `batch`, `items`, `eval`; `build_course()` is the shared build path |
| `src/course_reports/pipeline.py` | Builds `analysis.json` |
| `src/course_reports/validate.py` | Contract checks before rendering |
| `src/course_reports/render_html.py`, `assets/template.html` | HTML renderer (single file, inline CSS and JS, embedded Heebo `assets/heebo-*.woff2`) |
| `src/course_reports/render_md.py` | Markdown renderer: follows the HTML layout and anchors, uses graceful inline color |
| `src/course_reports/assets/dimension_lexicon.json` | Hebrew stem patterns per dimension |
| `src/course_reports/assets/recommendation_themes.json` | Recurring-recommendation taxonomy |
| `src/course_reports/assets/dimensions.json` | 16 dimensions in 3 categories |
| `docs/GUIDELINES.md` | Content and design rules (read before changing any output) |
| `examples/*/golden_analysis.json` | Hand-made analyses used as the evaluation reference |
| `tests/test_pipeline.py` | Ingest, mapping vs golden, adoption, both formats, guards, per-section fallback |
| `tests/test_robustness.py` | P0.3 inputs, 4- and 20-lesson courses, level scaling, re-render loop, batch, missing reports |
| `tests/test_llm_replay.py` | Replay of the recorded real replies, plus batch mode with a mocked API |
| `tests/test_html_browser.py` | Opens the HTML offline in headless Chromium: no console errors, no network (skipped without Playwright) |
| `sample_output/` | Both examples built with real Sonnet prose |

## 8. Things not to do

- Do not let the LLM produce, change or "round" numbers, statuses, lesson lists or dimension mappings.
- Do not change the visual design or section order. The user has iterated on it. Raise suggestions instead.
- Do not pass student-level data to the LLM or into Markdown.
- Do not make the API key or network a requirement for `--no-llm` builds or for tests.
