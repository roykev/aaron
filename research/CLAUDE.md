# Aaron Owl Research — CLAUDE.md

Standalone learning analytics project. Run from `/media/roy/hdd/git/aaron/research/`.

## What this project does

Post-semester analysis of student platform usage (Mixpanel events) to predict academic outcomes.
Federated design: Aaron Owl sends feature vectors to teachers → teacher adds grades locally →
teacher returns only 4 aggregated result files → Aaron Owl runs cross-course meta-analysis.

## Project structure

```
research/
├── config.yaml                        # courses, data paths, session/event/ALS settings
├── pipeline.py                        # main entry point — runs full pipeline per course
├── requirements.txt
│
├── modules/                           # pipeline stages
│   ├── event_loader.py                # load weekly CSVs, filter by course_id, mark active events
│   ├── identity_resolver.py           # distinct_id → email via user-export CSV
│   ├── session_builder.py             # session segmentation (30-min idle, 120-min cap)
│   ├── student_features.py            # 48 features per student + load_academic_csv()
│   ├── active_learning_score.py       # ALS composite score (0-100, percentile-ranked)
│   └── normalization.py               # z-score and percentile columns
│
├── targets/
│   ├── synthetic.py                   # SyntheticRandom, SyntheticFormula
│   ├── final_grade.py                 # FinalGrade (reads grades_csv from config)
│   └── base.py                        # TargetStrategy ABC
│
└── federation/
    ├── build_teacher_package.py       # builds zip to send teacher (run once per course)
    ├── analysis_script.py             # teacher runs this locally — never shares grades
    ├── meta_analysis.py               # combines results from multiple teachers
    ├── usage_report.py                # generates teacher-facing usage HTML
    └── FEDERATED_ANALYSIS_GUIDE.md    # how to receive + run meta-analysis
```

## Typical workflow

### 1. Run pipeline (produces feature CSVs + usage reports)
```bash
python pipeline.py                        # all courses
python pipeline.py --course psy           # single course
python pipeline.py --course psy --target synthetic_formula
```
Outputs land in the `output_dir` / `federation_dir` configured per course in config.yaml.

### 2. Build teacher package (zip to send)
```bash
python federation/build_teacher_package.py --course psy
python federation/build_teacher_package.py --course example_course
```
Package contains: feature CSV, usage_report HTML, analysis_script.py, grades_template.csv, HOW_TO.html (Hebrew, RTL).
Teacher fills in grades → runs analysis_script.py → sends back 4 files only.

### 3. Teacher runs locally (simulation)
```bash
python federation/analysis_script.py \
    --features student_features_psy_federation.csv \
    --grades   grades.csv \
    --out      results/
```
Outputs: correlation_report.csv, regression_summary.txt, feature_importance.csv, als_tier_profile.csv, analysis_report.html.

### 4. Meta-analysis (combine across courses)
```bash
python federation/meta_analysis.py \
    --courses "Psychology:/path/psy/results,Math:/path/math/results" \
    --out     /path/meta/
```
Outputs: meta_correlation.csv, meta_importance.csv, meta_tier_profile.csv, meta_r2.json, meta_report.html.

## Configured courses

| Key | Course | Notes |
|---|---|---|
| `example_course` | Math for Business Administration | CSV eval/quiz data |
| `psy` | Introduction to Psychology | Excel (.xlsx) with sheet names; per-course output_dir |

Add a new course: copy a block in config.yaml under `courses:`, set course_id, name, eval_csv, quiz_csv.
Per-course output: add `output_dir` and `federation_dir` keys (optional; falls back to global).

## Active Learning Score (ALS)

```
ALS = 0.35 * active_weeks_ratio     (percentile-ranked within cohort)
    + 0.25 * total_active_events
    + 0.20 * feature_diversity_count
    + 0.20 * meaningful_sessions_ratio
```
Classified as Low (<30) / Medium (30–60) / High (>60).
Active events: quiz_start/complete, evaluation_start/complete, concept_select, tab_change to learning tabs.
Meaningful session: duration ≥ 5 min AND ≥ 3 events AND ≥ 1 active event.

## Federation privacy model

- Feature CSV sent to teacher contains usage data only — no grades.
- `anonymize_ids: false` in config (teacher needs emails to join their grade file).
- Teacher returns 4 aggregate files — no individual grades ever leave their machine.
- als_tier_profile.csv: 3 rows (Low/Med/High mean grade). Suppressed if tier has <3 students.
- Meta-analysis pools correlations via Fisher z-transform (weighted by n), importances via N-weighted avg.
- Grades z-scored within each course before pooling tier profiles (scale-independent comparison).

## Key data paths (from config.yaml)

| Item | Path |
|---|---|
| Weekly events | `/home/roy/FS/Dropbox/WORK/Ideas/aaron/Analytics/weekly_data/` |
| User export CSV | `/home/roy/FS/Dropbox/WORK/Ideas/aaron/research/user-export-*.csv` |
| Global output | `/home/roy/FS/Dropbox/WORK/Ideas/aaron/research/output/` |
| Global federation | `/home/roy/FS/Dropbox/WORK/Ideas/aaron/research/federation/` |
| Psy output | `/home/roy/FS/Dropbox/WORK/Ideas/aaron/research/psy/output/` |

## What to do when a teacher returns results

1. Create a folder: `federated_results/<CourseName>/`
2. Drop the 4 files into it.
3. Run `meta_analysis.py --courses "..." --out federated_results/meta/`
4. Open `meta_report.html` for the combined view.

## Exam-window models & Federated Questions v2 (2026-06-15)

Two-sitting courses (Moed A + Moed B retake) caused a Simpson's-paradox sign-flip when
all activity was pooled. Fix: **window activity by exam date and model A/B separately.**

- **Windowing** (`pipeline.py`): per-course `moed_a_date` / `moed_b_date` in `config.yaml`
  produce a `preA` feature block (activity < Moed A) + a `postA_`-prefixed block
  (Moed A → Moed B retake/cram window; open-ended if no `moed_b_date`). No dates → single
  `all` window (backward-compatible; math unchanged). `--cutoff none` forces baseline.
- **Grade schema**: `email, moed_a, moed_b` (blank = absent; strip fail-words). No more `min()`.
- **The contract**: `federation/FEDERATED_QUESTIONS_SPEC.md` — read first. All scores
  standardized within course; only aggregated effect sizes leave a teacher.

New federation scripts (outputs go to Dropbox `…/research/federated_v2_demo/`, never git):

| Script | Role |
|---|---|
| `analysis_script_v2.py` | teacher-local: Q1 (ALS~moed_a), Q2 (ALS~improvement), Q3 (within-person ΔRate→grade), **risk** (R1 fail-A, R2 no-show-A), **predictive** (Ridge/RF + ALS audit). Emits `results.json` (grades never leave). |
| `meta_analysis_v2.py` | DerSimonian-Laird random-effects pooling + Cochran's Q; `meta.json` + `meta_report.html` (overview, plain-language verdicts ✅/🟡/◻️, per-course detail). |
| `churn_analysis.py` | R3 churn — grade-FREE, Aaron-Owl-side; course-length-relative windows; N/A for cram courses (<8wk span). |
| `simulate_course.py` / `simulate_grades.py` | synthetic course / synthetic grades-from-real-activity for dry-runs. |
| `build_teacher_package_v2.py` | bundles features + `grades_template` (moed_a/moed_b) + script + spec + Hebrew HOW_TO; teacher returns `results.json`. |

```bash
python pipeline.py --course bio                          # windowed two-block features
python federation/analysis_script_v2.py --features <fed.csv> --grades <moed_ab.csv> --course "<name>" --out <dir>
python federation/churn_analysis.py --course <key> --out <dir>
python federation/meta_analysis_v2.py --results <dirA> <dirB> ... --out <meta_dir>
python federation/build_teacher_package_v2.py --course bio
```

## What comes next (not yet built)

- Real grades: set `target.type: final_grade` and provide `grades_csv` in config — pipeline ready.
- More courses: add to config.yaml, re-run pipeline, rebuild teacher package, re-run meta.
- Heterogeneity test (Cochran's Q): **DONE** (2026-06-14) in `meta_analysis.py`. Per-feature Q/df/p/I² on Fisher-z correlations; `het_flag` ∈ {disagree, substantial, consistent, single}; columns added to `meta_correlation.csv`; "Cross-Course Heterogeneity" section + consistency badges in `meta_report.html`. With 3 courses (psy+math+bio, n=211), 8/35 features significantly disagree (p<0.05) — all driven by Cell Biology's inverted correlations (e.g. total_events I²=88%, p=0.0002).
- Clustering / student archetypes: local k-means + centroid sharing — discussed, not coded.
- Subgroup analysis by ALS tier — discussed, not coded.
