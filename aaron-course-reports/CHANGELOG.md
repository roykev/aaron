# Changelog

## 2026-10-19: P0 production hardening

**Layer 3 (LLM)**
- Ran against the real API (`claude-sonnet-5-5`). Both examples have zero guard violations.
- Prompt tuning:
  - numbers as digits only, and few of them;
  - the hub `sub` walks through the course units by name;
  - the hero names an adopted recommendation as an observed change.
- The guard also rejects spelled-out Hebrew numbers from 6 up that are not in the facts. This tightens the guard; it was not loosened.
- Record/replay fixtures in `tests/fixtures/llm/`. Tests never call the API.
- `max_tokens` raised from 6000 to 16000, because thinking counts toward it. Refusals and truncated replies fall back to deterministic copy.
- `_meta.narrative` records the model, calls, tokens and estimated cost.

**Batch**
- `course-reports batch --manifest`:
  - per-course logs and a `summary.json`;
  - keeps going on failure and exits 1 if any course failed.
- Narrative calls go through the Message Batch API by default, at half price. `--no-llm-batch` calls the model per course, and `--batch-id` resumes an interrupted batch.

**Inputs**
- A duplicated lesson number keeps the richer report and warns.
- Class-report sections without titles: a warning, and "אין חלוקה לנושאים" in both formats.
- Label matching is case-insensitive. This fixes lost "Full Action" text in lessons whose labels are in English.
- Tested: missing snapshots, English labels, 4- and 20-lesson courses.

**Dimension levels**
- Computed only in `signals.dim_state`, scaled to the number of lessons (unchanged at 10 lessons), and stored in `analysis.dims[id]`.
- The template and the Markdown renderer read the stored level; the duplicate JS rule is gone.
- Re-renders recompute the levels from an edited `item_dims`.

**HTML**
- Heebo is embedded, so the report opens offline with no network requests. A Playwright test checks this.
- Fixed a minute-rounding bug that could show "2:60 שעות".
- The student noun comes from `course.json` (new `analysis.course.student_noun`); "סטודנטיות" was hardcoded before.

**Markdown**
- Rewritten to follow the HTML layout:
  - section kickers, a nav line, the same anchor ids;
  - card rows as tables, and `<details>` where the HTML opens detail on click;
  - the course timeline;
  - the lesson pages with their cubes and dimension tags.
- Graceful color in the HTML palette through inline styles. GitHub shows it uncolored.
- Tests check that internal links resolve, tags are balanced, there are no emoji, and the observational-framing sentence is present.
