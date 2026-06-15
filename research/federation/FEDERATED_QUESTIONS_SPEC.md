# Aaron Owl — Federated Questions Spec (v2)

The contract every course follows so that weak per-course signals pool into strong
cross-course inference. Target scale: ~30 courses. Grades **never leave the teacher** —
only standardized, aggregated effect sizes + sufficient statistics are returned.

## Core principles
1. **Federation pools effect sizes, not raw data.** Each course computes locally and
   returns `results.json`; Aaron Owl runs random-effects meta-analysis.
2. **Within-course standardization** makes courses of different difficulty comparable.
3. **ALS is the interpretable claim; a data-driven model is the benchmark.** Report both.
4. **Privacy:** suppress any group with n < `SUPPRESS_K` (3 now → 5 as courses grow).
   Only aggregates + sufficient stats (n, Σ, Σ²) leave a teacher's machine.

## Standardization
- **Grades** → z-scored within course against the **Moed-A distribution**:
  `g_z = (g − mean_A) / sd_A`. Puts `moed_a`, `moed_b` on one scale;
  improvement `Δ_z = (moed_b − moed_a) / sd_A` is in course-SD units.
- **"High score"** = relative top tertile of Moed A (not an absolute cut) → comparable
  across easy/hard courses. Also emit Spearman/rank versions (robust to ceiling skew).
- **ALS** → already cohort-percentile (0–100), inherently cross-course comparable.
- **Activity rate** (Q3) → z-scored within course → standardized β.

## Grade file schema
`email, moed_a, moed_b` — numeric per sitting; blank = did not sit. Strip fail-words
(`52 נכשל`→52); `לא השתתף`/blank → absent (NaN). Math: only `moed_a`.

---

## Question families

### A. Outcome — ALS-centered (confirmatory)  [needs grades]
| | Question | Population | Predictor → Outcome | Emitted effect(s) | Pooled via |
|---|---|---|---|---|---|
| **Q1** | Does ALS *correlate with* the Moed-A outcome? | all w/ moed_a | ALS tier/score ~ `moed_a_z` | r(ALS,score)+n; d(High−Low)+SE; logOR(high-score)+SE; tier suff-stats | Fisher-z; DL |
| **Q2** | Does ALS *correlate with* A→B improvement? | retakers (moed_a & moed_b) | ALS ~ `Δ_z` | r(ALS,Δ)+n; d(High−Low)+SE; paired {n,mean_diff,sd_diff} | Fisher-z; DL |
| **Q3** | Does *increasing* activity raise the grade? | retakers | within-person `Δ_z ~ ΔRate_z + moed_a_z` | standardized β(ΔRate)+SE+n | DL |

- Q3 is a **student fixed-effects** design (each student own control), **controlling baseline
  `moed_a_z`** for regression-to-the-mean. Strongest causal design, smallest n → bio/pooled.
- **B-only students** (absent A, sat B): excluded from Q1/Q2 (no `moed_a`); reported as a
  separate descriptive group. Do **not** relabel B as A (truncated-window bias).

### B. Predictive — data-driven (benchmark + ALS audit)  [needs grades]
Regularized regression (Ridge-CV) + RF importance on **all** features → `moed_a_z`.
Returns: CV R² (+SE), standardized coefficients, RF importances (per feature, poolable
by N-weighted avg — existing meta convention). Purpose: best prediction **and** check
whether learned weights beat / resemble ALS's a-priori weights.

### C. Risk / early-warning (classification)
Predict from **early-window** activity (e.g. first 4 weeks) to be actionable *before* the exam.
| | Target | Population | Needs grades? | Note |
|---|---|---|---|---|
| **R1 Fail-A** | failed vs passed A | sat A | yes (pass mark) | underperformance |
| **R2 No-show-A** | absent vs sat A | enrolled roster | partial | disengagement; ≠ fail. **Coverage gap:** never-engaged students have no features |
| **R3 Churn** | activity drop-off before exam | all platform users | **NO** | upstream of R1/R2; **Aaron-Owl-side, no teacher** |
Emitted: per-feature logOR+SE, model AUC+SE, base rate. Pooled via DL (logOR) / AUC pooling.

- **Churn (R3)** is grade-independent → Aaron Owl computes it directly from events, no
  federation round-trip, and can run mid-semester as a live early-warning signal.
  - Windows are course-length-relative (early ≤ min(4w, span/3); late ≥ min(3w, span/4)).
  - **Applicability gate:** churn is N/A when pre-exam span < 8 weeks — cram-style courses
    (e.g. bio, 36-day span) concentrate engagement near the exam, so there is no early→late
    split. The module returns `applicable:false` + reason rather than a degenerate number.

---

## Return contract — `results.json`
Per course, written by `analysis_script_v2.py` (+ churn by `churn_analysis.py`):
```
course, course_id(hashed), standardization{mean,sd,high_cut,suppress_k},
Q1{n, tiers_score_z{tier:{n,mean,sd,sum,sumsq,suppressed}}, r_ALS_score, d_high_low_score, logOR_high_score},
Q2{n_retakers, n_b_only, paired, tiers_imp_z, r_ALS_imp, d_high_low_imp},
Q3{n, beta_dRate{dRate_z:{beta,se}, moed_a_z:{...}, n}},
predictive{cv_r2, coefs, rf_importance},        # family B (planned)
risk{fail_a, no_show_a, churn}                   # family C (churn first)
```

## Meta layer — `meta_analysis_v2.py`
DerSimonian-Laird random-effects pooling per effect; correlations via Fisher-z;
Cochran's Q + I² heterogeneity; forest-plot HTML (`meta_report.html`). Pools any
number of courses; new courses auto-ingested by dropping a `results.json` in.

## Status
- ✅ Q1/Q2/Q3 (`analysis_script_v2.py`), DL meta + HTML (`meta_analysis_v2.py`),
  simulator (`simulate_course.py`). Validated: psy (real) + 2 sims; Q1/Q2/Q3 recover planted signal.
- ⏳ B (predictive block), C-R3 (churn) — next. C-R1/R2 after.
- Outputs live in Dropbox `…/research/federated_v2_demo/`; never in git.
