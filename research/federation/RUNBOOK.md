# Aaron Owl — Federated Analysis RUNBOOK (v3)

Operator's guide: how to run the whole federated learning-analytics pipeline end to end.
For the *why/design*, see `DESIGN_v3.md`; for repo/dev notes, see `research/CLAUDE.md`.

**Privacy model in one line:** Aaron Owl holds only grade-free activity. Grades stay on the
teacher's machine; the teacher runs a local script that returns **aggregates only** (effect sizes +
sufficient statistics). Nothing that identifies a student's grade ever leaves.

---

## 0. The pipeline at a glance

```
config.yaml (course block)
      │
      ▼  pipeline.py                 → windowed activity features + course_meta_<key>.json + usage report
      ▼  cluster_students.py         → cluster_id written into every feature CSV (whole-platform archetypes)
      ▼  build_teacher_package_v2.py → teacher_package_<key>_v2_*.zip  (features + grades template + scripts + HOW_TO)
   ── send zip to teacher ──
      ▼  (teacher) fills course_metadata.yaml (exam dates, type, delivery mode, tasks) + grades
      ▼  (teacher) match_roster.py   → roster_matched.csv (optional: adoption)
      ▼  (teacher) analysis_script_v2.py → results.json
   ── teacher returns results.json + course_metadata.yaml ──
      ▼  meta_analysis_v2.py         → meta.json + meta_report.html   (pool across courses)
      ▼  program_dashboard.py        → program_dashboard.html         (portfolio + findings)
      ▼  weekly_timeline.py / combined_timeline.py / early_warning_leadtime.py  (grade-free visuals)
```

Run everything from `research/`. Requires the `aaron` conda env (pandas, numpy, scipy, scikit-learn, yaml).

---

## 1. One-time setup

- `config.yaml` → `data:` block holds `weekly_events_dir`, `user_export_csv`, output dirs,
  `exclude_emails` / `exclude_email_domains` (staff/instructors — dropped before features),
  and `warmup_days` (default 21).
- Mixpanel exports: `SiteAnalytics/mixpanel_export.py --config config.yaml --from <d> --to <d> -o <week.csv>`
  (secret from env `MIXPANEL_SECRET`). Weekly files go in `weekly_events_dir` as `week_YYYY-MM-DD_YYYY-MM-DD.csv`.

---

## 2. Add a course (pick the recipe by course type)

Add a block under `courses:` in `config.yaml`. `course_type` is **inferred** if omitted.

**Exam course (Moed A [+ Moed B retake]):**
```yaml
  my_course:
    course_id: <uuid>
    name: "Course name"
    moed_a_date: 2026-01-29
    moed_b_date: 2026-02-19        # omit if no retake / unknown → open-ended
    eval_csv: /path/eval.csv       # optional (in-platform eval scores → richer features)
    delivery_mode: asynchronous    # optional moderator (synchronous/asynchronous/hybrid)
    attendance_required: optional   # optional moderator (mandatory/optional/partial)
    output_dir: /path/out
    federation_dir: /path/out
```

**Coursework course (n tasks + final work, no exam):**
```yaml
  my_course:
    course_id: <uuid>
    name: "Course name"
    course_type: coursework        # optional; inferred from milestones anyway
    milestones:
      - {name: "HW 1",       date: 2026-03-01, type: assignment, weight: 0.2}
      - {name: "HW 2",       date: 2026-04-01, type: assignment, weight: 0.2}
      - {name: "Final Work", date: 2026-06-15, type: project,    weight: 0.6}
    delivery_mode: asynchronous
    output_dir: /path/out
    federation_dir: /path/out
```
Windows are built automatically: exams → `preA`/`postA`; milestones → `pre_<task>` / `post_<last>`;
plus a `warmup` (first `warmup_days`) block for the causal baseline.

---

## 3. Aaron-side: build + package

```bash
# 1) windowed features (+ course_meta_<key>.json + usage report). --target avoids grade coupling.
python pipeline.py --course my_course --target synthetic_random

# 2) whole-platform clustering → writes cluster_id/cluster_name into every feature CSV
python federation/cluster_students.py --k 5 --out <clusters_dir> --write-back

# 3) build the teacher zip. Contents: feature CSV (with warmup + cluster_id), grades_template.csv,
#    analysis_script_v2.py, match_roster.py, course_metadata.yaml (fill-in form), course_meta_<key>.json,
#    HOW_TO.html, FEDERATED_QUESTIONS_SPEC.md
python federation/build_teacher_package_v2.py --course my_course
#    coursework: add --grade-mode final (or supply milestones in config for a per-task template)
```
Send `teacher_package_my_course_v2_*.zip` to the teacher.

---

## 4. Teacher-side (runs locally; returns two non-sensitive files)

**Step A — fill `course_metadata.yaml`** (bilingual form, pre-filled with what we know): exam dates
(Moed A/B), course type, **delivery mode** (frontal/online/hybrid), attendance policy, and — for
coursework — the graded-task list (name/date/weight). This is the one-shot metadata collection.

**Step B — fill grades** in `grades_template.csv` (exam courses: `moed_a`,`moed_b`; coursework: a
column per task named to match the metadata form).

**Step C — run** (from inside the unzipped package):
```bash
# (optional) find students who sat the exam but never used the app → adoption analysis
python match_roster.py --roster roster.csv --directory name_email.csv \
    --features student_features_<key>_federation.csv --out roster_matched.csv

# the analysis — grades never leave; emits results.json (aggregates only)
python analysis_script_v2.py \
    --features    student_features_<key>_federation.csv \
    --grades      grades_template.csv \
    --course-meta course_metadata.yaml \      # moderators + (coursework) composite/sequential
    --course      "Course name" \
    [--roster    roster_matched.csv]           # enables adoption contrast
    [--pass-mark 60] [--grade-mode ...] \
    --out results
```
Return **two files**: `results/results.json` + the filled `course_metadata.yaml`.

> If the returned metadata brings **new exam/task dates**, re-run `pipeline.py` with them (add
> `moed_*_date` / `milestones` to config) to enable the windowed questions (Q3, subgroups, pre/post,
> sequential) — then the teacher re-runs on the refreshed feature CSV. Everything else works round 1.

---

## 5. Aaron-side: pool + visualize

```bash
# pool across courses (random-effects) → meta.json + meta_report.html
python federation/meta_analysis_v2.py --results <dirA> <dirB> ... --out <meta_dir>

# portfolio dashboard (status/findings/forest bars/coloured Q&A/links)
python federation/program_dashboard.py --config config.yaml \
    --results psy:<dir> my_course:<dir> --meta <meta_dir> \
    --timelines <timelines_dir> --out program_dashboard.html

# grade-free visuals
python federation/weekly_timeline.py   --course my_course --out <timelines_dir>
python federation/combined_timeline.py --courses psy bio my_course --out <timelines_dir>   # aligned to Moed A, % active
python federation/early_warning_leadtime.py --course my_course --grades <grades> --out <dir>  # AUC vs lead-time

# legacy v1 teacher return (4-file bundle) → v2 results.json
python federation/adapt_v1_to_v2.py --v1-dir <dir> --course "Name" --grade-mode final \
    --external <correlates.json> --out <dir>
```

---

## 6. Questions the analysis answers (self-describing)

Each `results.json` stamps `course_type`, `grade_mode`, and an `answered[]` list — a course only
answers what its data supports; the meta pools each question only over courses that answered it.

| Key | Question | Needs |
|---|---|---|
| **Q1** | Does ALS relate to the outcome? | any grades |
| **Q2/Q3** | Does ALS relate to A→B improvement / within-person ΔRate? | exam A+B + dates |
| **R1 / R2** | Predict fail / no-show from pre-exam activity (OOF AUC + confusion + coef signs) | grades + pass_mark |
| **predictive** | Does a free model beat ALS alone? | grades |
| **value_added** | Does ALS predict **above** early-activity + in-platform performance? *(causal robustness)* | warmup features |
| **sequential** | Predict task *n* from tasks 1…*n*−1 + run-up activity | coursework, ≥2 tasks |
| **adoption** | Do app-users outscore non-users? | full roster |
| **subgroups / pre_post_a** | post-A segment ALS→outcome; grade-free pre→post-A activity change | exam windows |
| **sufficient_stats** | means + SD + correlation matrix → any future linear analysis, no re-ask | always |

---

## 7. Where outputs land

| Output | Location |
|---|---|
| Feature CSV (to teacher) | `<federation_dir>/student_features_<key>_federation.csv` |
| Course metadata | `<federation_dir>/course_meta_<key>.json` |
| Usage report (per course) | `<federation_dir>/usage_report_<key>.html` |
| Teacher package zip | `<federation_dir>/teacher_package_<key>_v2_*.zip` |
| ↳ current (2026-07) | 7 Azrieli → `azrieli/output/teacher_package_az_*_v2_20260707.zip` · math → `federation/teacher_package_example_course_v2_final_20260707.zip` |
| Cluster profiles / assignments | `<clusters_dir>/cluster_profiles.csv`, `cluster_assignments.csv` |
| Pooled meta | `<meta_dir>/meta.json`, `meta_report.html` |
| Program dashboard | `program_dashboard.html` |
| Timelines | `<timelines_dir>/weekly_timeline_<key>.html`, `combined_timeline.html` |

---

## 8. Notes & gotchas

- **Staff exclusion** is automatic (config lists + domain rule); every excluded email is logged.
- **ALS is percentile-ranked within a window** → its *mean* is ~50 by construction; never compare
  pre vs post ALS as levels — use raw activity or the fixed-scale tier-transition (usage report).
- **Timelines use % students active** (size-independent) and **day-bins anchored on the exam**
  (not ISO weeks) so courses align regardless of exam weekday.
- **High-passing courses** (few fails) will show null R1/early-warning — that's honest, not a bug;
  the signal needs a course with real failures.
- **Re-running is safe/idempotent**; exam courses are byte-identical to v2.
- After changing feature CSVs (e.g., re-running the pipeline), **re-run clustering** to refresh
  `cluster_id`, then rebuild the teacher package.
