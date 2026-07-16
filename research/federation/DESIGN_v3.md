# Aaron Owl — Federated Analysis v3 Design (generalized, one-shot collection)

Status: **design** (2026-07). Supersedes the exam-only v2 model; v2 (Moed A/B) becomes a
special case. Goal: a **single teacher ask** that supports every current and future
analysis — because collection is one-shot.

## 0. Design principles

1. **Collect a superset of inputs** once; never assume we can go back to a teacher.
2. **Return sufficient statistics, not only effect sizes.** The local script ships back
   moment matrices (n, sums, sums-of-squares, cross-products) over
   `activity × outcomes × covariates`, per relevant subgroup, small-cell-suppressed. Any
   future correlation / OLS / subgroup-mean is then recomputable **without re-contacting
   the teacher**. Pre-specified effect sizes are also returned for convenience.
3. **Grade-free stays central (Aaron-side); grades stay local (teacher-side).** Clustering,
   activity dynamics, and cluster assignment are computed centrally on pooled usage; grades
   and covariates never leave the teacher — only aggregates do.
4. **Course type drives model selection.** Different course structures → different windows,
   outcomes, targets, and possibly different trained models.

## 1. Course-type flag (first-class)

`course_type` ∈:
- `exam` — single exam (Moed A) [+ optional Moed B retake]. The v2 model.
- `coursework` — several graded tasks + a final work; **no exam**.
- `mixed` — tasks + exam(s).
- `project` — a single final work / thesis.
- `pass_fail` — only a pass/fail outcome (no numeric grade).

Drives: which windows are built, how the composite outcome is formed, and which targets/models
apply (see §6). A `non_exam` boolean is derivable (`course_type not in {exam, mixed}`) for quick gating.

**Self-describing (auto-detected, like grade_mode).** If `course_type` is declared, use it;
otherwise infer from the data via a fallback hierarchy — so a teacher who sends the minimum
still gets classified:
1. grades are only pass/fail → `pass_fail`
2. exactly one numeric score, no task dates → `exam`
3. one final score + a single deadline, no interim grades → `project`
4. ≥2 dated components, none an exam → `coursework`
5. ≥2 dated components incl. an exam → `mixed`
The inferred type is stamped into `results.json` so the meta pools by type.

## 2. Generalized outcome — declared components + weights

Replace the fixed `grade_mode` with a **component list**. The course declares its graded items:

```yaml
components:
  - {name: task_1,    type: assignment, weight: 0.10, max: 100, date: 2026-03-01}
  - {name: task_2,    type: assignment, weight: 0.10, max: 100, date: 2026-04-01}
  - {name: midterm,   type: exam,       weight: 0.30, max: 100, date: 2026-04-20, pass_mark: 60}
  - {name: final_work,type: project,    weight: 0.50, max: 100, date: 2026-06-15}
```

- **Composite outcome** = weighted sum of components (within-course standardized for pooling).
- Individual components enable **mediation, dose-response, per-task** analysis.
- Exam-only (`moed_a` [,`moed_b`]) and `final` are just special component lists → v2 is subsumed.

## 3. Timeline — milestone-anchored windows (not exam-anchored)

Every component with a `date` is a **milestone**. Activity is windowed relative to each
milestone (`pre_<name>`, `post_<name>`), using the exam-anchored **day-based** binning we
fixed for timelines (bin 0 = 7 days ending on the milestone). Rules:
- `exam` → Moed A/B windows (as today).
- `coursework` → a window per task deadline + the final-work deadline.
- no dated milestones → relative-time windows (course thirds) + single `all`.
Exam windowing is the special case where the only milestones are Moed A/B.

## 4. Input schema (what the teacher provides)

**Required (realistic budget: roster + grades + type + dates):**
| File | Columns |
|---|---|
| `roster.csv` | `email` (+ optional `name`) — **all enrolled**, not just app-users |
| `grades.csv` | `email`, one column per declared component |
| `course_meta.yaml` | `course_type`, `components[]` (name/type/weight/date/max/pass_mark), discipline, level, credits, **`attendance_required`** (mandatory / optional / partial %), **`delivery_mode`** (synchronous / asynchronous / hybrid) |

**Optional — accepted if available, auto-detected, never required:**
| File | Columns | Unlocks |
|---|---|---|
| `prior.csv` | `email`, `prior_gpa` / `entry_score` / `prereq_grade` | *strengthens* causal robustness — but **likely unavailable** (registrar). Default baseline is first-weeks in-platform signal (§7.1) |
| `demographics.csv` | `email`, `year`, `major`, `status` (full/part-time) | heterogeneity |
| `attendance.csv` | `email`, `session_date`, `present` | attendance × online-activity correlation |
| `status.csv` | `email`, `withdrawn`/`dropped`/`retook` (+ dates) | dropout / retake as **model targets** |

Aaron-side supplies (grade-free, rides along in the feature CSV): windowed activity features,
ALS, and **`cluster_id`** (§5).

## 5. Central clustering → cluster_id as a feature

Usage data is grade-free and already centralized → **cluster centrally on pooled activity
across all courses** (a single course is too small to cluster). Output: student archetypes
(e.g. *consistent-deep / crammer / quiz-only / browser / early-fade*). Then:
- **Attach `cluster_id` to each feature CSV** → it reaches the teacher and can condition any
  local analysis (`cluster × outcome`).
- Use `cluster_id` as a **feature in the early-warning model** (per-course data too sparse to
  cluster locally; the central cluster injects cross-course structure).
- Clusters double as a **description / marketing** device ("the 5 learner types on our platform").

## 6. Analysis battery — what runs per course type

| Analysis | exam | coursework | mixed | project | needs |
|---|---|---|---|---|---|
| Activity → outcome (Q1) | ✓ | ✓ | ✓ | ✓ | grades |
| Pre/post-milestone activity change (grade-free) | ✓ | ✓ | ✓ | ✓ | dates |
| Fail-risk (R1) | ✓ | per-task non-submission | ✓ | — | grades + pass_mark |
| No-show (R2) | ✓ | non-submission | ✓ | — | roster + grades |
| Improvement (Q2/Q3, retake or task→task) | ✓ (A→B) | ✓ (task→task) | ✓ | — | ≥2 dated components |
| Adoption (users vs non-users) | ✓ | ✓ | ✓ | ✓ | full roster |
| **Causal / value-added** (activity above prior ability) | ✓ | ✓ | ✓ | ✓ | **prior.csv** |
| **Early-warning lead-time** (cumulative milestone-k → target) | ✓ | ✓ | ✓ | ✓ | grades/status |
| **Sequential task model** (task *n* from tasks 1…*n*−1 + activity) | — | ✓ | ✓ | — | ≥2 dated graded tasks |
| Dropout / retake model | ✓ | ✓ | ✓ | ✓ | **status.csv** |
| Attendance × online-activity | if attendance | if attendance | — | — | **attendance.csv** |
| Cluster × outcome heterogeneity | ✓ | ✓ | ✓ | ✓ | cluster_id |

**Course-level moderators (metadata only — no per-student data needed):** `attendance_required`,
**`delivery_mode`**, `discipline`, `level`, `credits`, `course_type`, cohort size. In the meta
these become moderators of the pooled effect. The two that most directly test our thesis — *is
engagement more predictive where the platform is the primary channel?*:
- **`delivery_mode`**: expect ALS→outcome strongest in **asynchronous** (platform = primary),
  weaker in **synchronous** (live class primary, online supplementary).
- **`attendance_required`**: expect stronger where attendance is **optional** than **mandatory**.
Both are useful even with no per-student attendance data, and they condition how the
attendance×activity analysis (when data exists) is read.

## 7. Flagship analyses (sequenced 1 → 2, + sequential)

1. **Causal robustness — value-added.** Does *sustained* activity/ALS predict the outcome
   **above a baseline signal**? Registrar prior-ability (prev GPA / entry score) is likely
   **unavailable**, so the baseline is the **first-weeks in-platform signal** — early-window
   activity **and** early in-platform performance (first eval/quiz scores, which proxy ability
   better than volume). Local OLS: `outcome ~ early_signal + ALS_rest (+ controls)`; report the
   ALS partial effect + ΔR². Claim: "engagement predicts outcomes **beyond what early
   behavior/performance already signals**." `prior.csv` is an optional strengthener, not a gate.
2. **Early-warning lead-time.** Cumulative activity up to milestone-*k* → predict at-risk
   (fail / **dropout** / low outcome); report **AUC vs lead-time**. `cluster_id` as a feature.
   Actionable, prospective. Pools across courses via §0.2 sufficient stats.
3. **Sequential task model (coursework / mixed).** For courses with several dated, graded tasks,
   predict **task *n*** from **tasks 1…*n*−1** (grades + activity) plus activity in the window
   leading to task *n*. A rolling model whose accuracy grows through the term — the actionable
   per-task version of #2 (flag a student before the *next* task, not just the final). Prior-task
   grades are strong features and are a within-course baseline (partially addresses #1's
   confounding too). Returns per-step AUC/R² + coefficients; pools across courses by step index.

## 8. The sufficient-statistics return (future-proofing core)

`results.json` carries, in addition to effect sizes:
- **Global moment block**: for the vector `z = [standardized activity features, ALS,
  cluster one-hots, composite outcome, each component, prior_ability, demographic dummies]` —
  return `n`, `sum(z)`, and the upper triangle of `sum(z zᵀ)`. → any correlation / linear
  regression / partial effect is recoverable later.
- **Conditional moment blocks** by `cluster_id`, by `course_type`, by demographic (suppressed
  if a cell < K). → subgroup questions answerable post-hoc.
- Provenance: `course_type`, component/milestone declaration, `answered[]`, standardization
  constants, suppression K.

## 9. Migration / back-compat

- v2 exam courses map onto v3 as `course_type: exam` with `components: [moed_a, moed_b]`.
- The current pipeline, `analysis_script_v2`, and meta continue to work; v3 generalizes the
  outcome/window layer and adds the moment-matrix return + optional covariates.

## 10. Build order (proposed)

1. **[DONE 2026-07]** `course_type` flag — declared or inferred (`_infer_course_type`); threaded
   through `pipeline.py`, printed, and stamped to `course_meta_<key>.json` (type, windows,
   milestones, delivery_mode, attendance_required, discipline, level).
2. **[DONE]** Milestone windowing: `_resolve_windows` generalized to
   `milestones: [{name,date,type,weight}]` → `pre_<task>` / `post_<last>` interval blocks;
   exam path (`preA`/`postA`) unchanged (verified byte-identical on bio). **Outcome side DONE:**
   `analysis_script_v2` has a `components` mode (`--course-meta`) — `composite_from_components`
   builds the weighted composite (match milestone↔grade column by normalized name, missing→0),
   runs Q1/R1/R2/predictive on it, and stamps `course_type` + `components` + `delivery_mode` +
   `attendance_required` into `results.json`. Verified on a coursework course end-to-end; exam
   modes unchanged (psy identical). (Q2/Q3 = sequential task→task, still TODO — flagship #3.)
3. **[DONE]** Sufficient-statistics return — `moment_block` in `analysis_script_v2` ships means +
   SDs + correlation matrix over outcome/ALS/activity/warmup/performance → any future linear
   analysis recoverable without re-asking the teacher. In `results.json.sufficient_stats`.
4. **[DONE]** Central clustering — `cluster_students.py` clusters the WHOLE platform from raw
   events (698 students / 70 courses, not just pipeline-run courses; staff auto-excluded by the
   domain rule). k-means on within-course-standardized behavioral features → archetypes
   (consistent / intense-sessions / frequent / low-engaged …); `--write-back` appends
   `cluster_id`+`cluster_name` to each course's federation CSV (grade-free feature + lens).
5. **[DONE]** Value-added (causal) block `value_added_block` — OLS `outcome ~ baseline + ALS`;
   baseline = **early-activity `warmup_` features** (first `WARMUP_DAYS`=21, a pipeline block, a
   propensity confounder — not a mediator) + in-platform performance (eval/quiz). Returns ALS
   partial std-coef + SE (poolable) + CV ΔR². Verified on psy: controlling for early engagement +
   in-platform performance, **ALS β=0.47±0.10 (p<0.001), ΔR²=+0.05** — the effect survives and
   improves prediction. Pipeline `warmup` window built (§ run_course 5c) + stamped in course_meta.
   **TODO:** pool `als_partial` in the meta so it renders as a forest finding.
6. **[DONE — demo]** Early-warning lead-time — `early_warning_leadtime.py`: cumulative activity up
   to (exam − k weeks) → OOF-AUC per lead → AUC-vs-lead-time curve + chart. Verified on psy (flat
   ~chance: psy is high-passing with ~3 real fails → no at-risk population to detect; awaits a
   course with real failures). Production step: move cumulative-feature build into the pipeline
   (ship `lead<k>w_` blocks) so the AUC runs federated (grades never leave).
7. **[DONE]** Sequential task model — `sequential_task_block` (coursework/mixed): predict task *n*
   from tasks 1…*n*−1 (grades) + `pre_<task_n>` run-up activity; per-step CV R² priors-only vs
   +activity. Validated on a synthetic coursework course: prediction grows with history
   (priors R² 0.28→0.38) and activity adds at every step (Δ +0.14 → +0.26). Awaits a real
   coursework course to report real numbers.

**ALL 7 v3 STEPS BUILT (2026-07).** Framework generalized past exams end-to-end: course-type-aware,
milestone-windowed, composite-outcome, cluster-enriched, with value-added + early-warning +
sequential flagships and a sufficient-statistics return. Remaining is real data (bio v2 return,
Azrieli grades, a real coursework course) — not code.
