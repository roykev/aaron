# DESIGN v4 — Longitudinal & multi-course analysis

**Status:** design only. Parked 2026-07-26, to be picked up next semester.
**Prereq for everything here:** more than one semester of event history per student.
Follows [`DESIGN_v3.md`](DESIGN_v3.md); reuses the v3 pipeline, `analysis_script_v2.py`,
`meta_analysis_v2.py`, `churn_analysis.py`.

---

## 0. Why this document exists

v1–v3 analyse **one student in one course in one semester**. Every question worth asking next
is about **the same student across courses and across time**:

- Is a student at risk *in the department*, not just in a course?
- Did a student who used to engage stop engaging — and is that a dropout warning?
- Does course-to-course variation in usage identify anything causal?

The first evidence that this is possible: in the 7 Azrieli courses (2025-11 → 2026-05),
**16 of 195 students appear in two courses** (`azrieli/output/az_cross_course_students.csv`).
None in three or more, and all overlaps are concurrent — the event export only spans one
academic year, so no student is yet observed across semesters. That is the binding constraint,
and §5 is about lifting it.

---

## 1. What multi-membership makes possible

Ranked by value, with what each needs.

| # | analysis | identifies | needs | grades? |
|---|---|---|---|---|
| 1 | Department early warning | at-risk students across all their courses | rosters + multi-course coverage | optional |
| 2 | Personal-baseline drop / dropout signal | within-student change over time | ≥2 semesters of events | no |
| 3 | Churn survival model | time-to-disengagement, hazard curve | ≥2 semesters | no |
| 4 | Effort substitution across concurrent exams | displacement between courses | exam dates for ≥2 concurrent courses | no |
| 5 | Trait vs. state variance decomposition | is engagement a person or a course property | crossed student×course data | no |
| 6 | ALS reliability / disattenuation | measurement quality of ALS | same student in ≥2 courses | no |
| 7 | Prior-course baseline for value-added | real prior-ability control (v3's known gap) | grades in ≥2 courses per student | yes |
| 8 | Course value-added adjusted for student mix | course/lecturer effect net of who enrolled | many shared students per course pair | yes |
| 9 | Student fixed effects on ALS→grade | ~~causal effect of usage~~ — see §2 | grades in ≥2 courses per student | yes |

Note how many are **grade-free**. 2–6 run entirely on Aaron Owl's own event data with no teacher
participation at all. That is the cheapest, highest-leverage part of this document.

---

## 2. Student fixed effects — demoted, and why

The original pitch: regress `z(grade)_ic = α_i + β·ALS_ic + γ_c + ε_ic` with a student dummy α_i,
sweeping out ability, motivation, language, SES — every *stable* confounder — and claiming β as
causal.

**It doesn't hold.** Fixed effects remove what's stable about a student, not what varies *within*
a student across courses. The obvious violator: **a student uses Aaron Owl more in the subject
they're weak at.** Compensatory usage is course-varying, correlated with usage, and correlated
with the grade. Same structure as "students who study more get worse grades."

What survives:

- The bias sign is **known and negative**. So a within-student β that still comes out **positive**
  is a conservative lower bound — report it as a robustness check, never as the headline.
- A null is uninformative. Do not interpret it.

Honest routes to the causal claim, if ever wanted:

- **Pre-feedback window.** Measure ALS in the first 2–3 weeks, before the student has learned they
  are struggling. Compensation needs feedback to trigger; early usage is much less contaminated.
- **Exogenous variation in usage.** Content upload timing (which lectures were available when),
  exam calendar spacing, platform outages. Requires the content timeline in §5.C — which is why
  that snapshot matters even though it looks like housekeeping.

---

## 3. Department-level early warning (the flagship)

**Change the unit of analysis from student×course to student×semester.** The department's object
of concern is the student.

### 3.1 The core feature: two normalisations, crossed

Neither alone is enough:

|  | **low vs. own average** | **normal vs. own average** |
|---|---|---|
| **low vs. course cohort** | **systemic** — disengaging from everything | course is hard for everyone |
| **normal vs. course cohort** | **localized** — dropping this one course | fine |

Per-course early warning cannot distinguish systemic from localized, and they need opposite
interventions: a tutor vs. student services. That distinction *is* the department-level product,
and it exists only with multi-course coverage.

### 3.2 Why this fixes the `low_power` blocker

Every course analysed so far (psy, ceramics, math) is high-passing — too few failures to train a
classifier, hence per-course `low_power` flags everywhere. Aggregating to the student fixes it
arithmetically: a 5% per-course fail rate over 6 courses gives
**P(at least one fail) ≈ 26%**. The fix is not finding a harder course — it is seeing *all* of a
student's courses.

### 3.3 Outcomes, ascending value

1. per-course fail / no-show at Moed A — exists (R1/R2 in `analysis_script_v2.py`)
2. **count of failed courses**, semester GPA, credits earned
3. **not registered next semester** — what the department is actually measured on, and grade-free

### 3.4 Two tests specific to this data shape

- **Leading-indicator course.** Does disengagement in one course precede it in others by a lag? If
  so, that course is a canary and alerts fire while the rest still look normal. Purely temporal,
  no grades.
- **Leave-one-course-out transfer.** Train on k−1 courses, predict the k-th. Tests whether the
  model generalises across subjects or memorises each course's quirks — the first question any
  skeptic asks about a department-wide score.

---

## 4. The personal-baseline drop signal, and churn as survival

### 4.1 Relative, never raw

A student whose ALS is low may simply be a low-usage person. A student who *was* 80 and is now 30
has changed — and change is where the information is.

But raw ALS drops for reasons that aren't about the student: this semester's courses have less
material on the platform, are lab/project heavy, the product changed, the calendar shifted. Any of
those fires the alarm for a whole cohort. So the signal is **change in relative standing**:

```
p_ic     = ALS percentile of student i within course c's cohort
P_is     = median of p_ic over student i's courses in semester s
B_i      = P_i,s-1   (or mean over prior semesters)     ← their own baseline
D_is     = B_i − P_is                                    ← the drop
breadth  = fraction of their courses where p_ic fell > X
```

The percentile cancels course difficulty, content coverage and product drift, because the whole
cohort is exposed to the same conditions. `D` large **and** `breadth` high → systemic/dropout
signal. `D` large in one course only → course-failure signal.

### 4.2 Prior state changes the meaning

| prior semester | ALS drops now | reading |
|---|---|---|
| high ALS, **succeeded** | strongest signal | someone who could and did, stopped — life event, overload, crisis |
| high ALS, failed | different flavour | discouragement after effort didn't pay |
| low ALS, succeeded | weak | low usage is their normal |
| low ALS, failed | confirmation | already flagged |

### 4.3 Three churn targets — keep them separate

| | target | labels from | status |
|---|---|---|---|
| **T1** | stops using Aaron *within* a course | own events | **built** — `churn_analysis.py` |
| **T2** | doesn't return to Aaron *next semester* | own events | needs prior-year history |
| **T3** | doesn't register — academic dropout | the college | needs registration data |

Build T2 regardless: it is the product-retention KPI, fully observable, and vastly more data than
T3 will ever have. Then the research question is *how well T2 predicts T3* on the small labelled
set — a far better position than learning T3 from a handful of dropouts.

### 4.4 The seasonality trap

A standard "N days inactive → churned" rule **labels the entire cohort churned every January**.
Already measured: ~90% engagement collapse after Moed A, dz ≈ −0.93, k=3. A naive churn model
learns the academic calendar and nothing else.

**Churn must be defined relative to the academic calendar, not elapsed time:** *did not return
during the first K weeks of the next semester's active window.* All time is measured in
semester-phase. This is the single most important definitional decision here.

### 4.5 Discrete-time survival, not binary classification

It's logistic regression on a student×week (or ×semester) panel — no new machinery — and it buys:

- **correct censoring** — a student who hasn't dropped *yet* is censored, not a negative example
- **time-varying covariates** — weekly ALS goes in directly
- **a hazard curve** — "risk is rising" instead of a static score, and the onset week falls out of
  the model rather than needing a separate changepoint pass

Cox with time-varying covariates is the continuous analogue; discrete-time logistic is simpler,
handles ties, and reuses the existing OOF / `low_power` evaluation harness.

### 4.6 Features to add (churn practice; all missing from `early_features()`)

`early_features()` is pure volume/frequency. The strongest churn predictors usually aren't:

- **Recency** — days since last active. Dominates in nearly every consumer churn model.
- **Slope** — Δ over trailing weeks. Separates "quiet person" from "person who went quiet."
- **Regularity** — variance/entropy of inter-session gaps. Erratic beats infrequent as a signal.
- **Breadth** — number of courses currently active in.
- **Personal z** — everything expressed against the student's own history, not raw.

RFM analogue: Recency / Frequency / Depth (active events, lecture coverage, feature diversity).

### 4.7 Model choice, matched to n

Penalised logistic as a discrete-time hazard. Gradient boosting only at thousands of
student-semesters; skip deep survival models. Two evaluation changes:

- **Split by time, not randomly** — train on earlier cohorts, test on later. Random CV leaks
  semester-level information and flatters the result.
- **Report precision@k with AUC** — the deliverable is a ranked watchlist, and AUC doesn't say
  whether the top 20 names are worth a human's hour.

### 4.8 Ship as a watchlist, not a classifier

Dropout base rates are low; any threshold has poor precision. Return the **top N by change score**
with onset week and per-course breakdown, for human review. Recall matters more than precision
because the intervention (someone checks in) is cheap and benign — but a named at-risk list is a
much heavier artifact than a usage report, and it ships with an agreed protocol for who sees it
and what they do, or it doesn't ship.

---

## 5. Data to collect NOW (see also §6 checklist)

Split by whether it decays. **Decaying items are the only genuinely urgent thing in this
document** — the rest can be reconstructed later.

### A. Event history backfill — *on a clock*
`Analytics/weekly_data/` starts 2025-10-18; first Azrieli event 2025-11-09. Every student is
observed in exactly one academic year, so §4 has no baseline to fall from. Pull backwards
(`SiteAnalytics/mixpanel_export.py`) as far as Mixpanel retention allows, **and check what the
retention limit actually is** — if it's shorter than the gap, this design starts from today's
data and cannot be backdated. Never delete a weekly export.

### B. Identity-map snapshots — *silently decays*
`user-export-*.csv` (`$distinct_id → $email → $name`) is a **current-state dump**. When a student
changes email, graduates, or is deleted, the ability to link last year's events to this year's
person is gone — and nothing warns you. Take a dated export **every semester** and keep them all.
This is the linkage backbone for every longitudinal analysis here.

### C. Content timeline per course — *unrecoverable*
Which lectures/materials existed in each course, and when they were uploaded. Needed twice: as
the normaliser for "ALS dropped because there was less material," and as the only plausible source
of exogenous variation for §2's causal route. Editing or removing a lecture destroys the history —
snapshot weekly.

### D. Product changelog + frozen ALS definition — *unrecoverable*
Dated record of shipped features, UI changes, and any change to event types or names. Cross-year
ALS comparisons are invalid if the event schema moved underneath them. Freeze a **`ALS_v1`**
computed from a stable event subset, keep computing it alongside whatever ALS becomes, and use
ALS_v1 for all longitudinal comparisons.

### E. Enrollment table — student × course × semester
Which student took which course when. Without it there are no denominators: a student inactive in
a course they never enrolled in is not churn. The Azrieli rosters supply this for 2025–26 — make
it a standing per-semester ask, not a one-off.

### F. Program / track / year of study, per student
Defines what "the department" *is* in department-level early warning, and separates a first-year
overload signal from a final-year one. Two extra columns on a roster sheet now; painful to
retrofit later.

### G. Academic calendar per institution
Semester start/end, exam periods, holidays, disruptions. All of §4 is measured in semester-phase,
which is undefined without it. Trivial to record, tedious to reconstruct.

### H. Outcome labels — registration status next semester
The T3 label. Establish it now as a **recurring** ask so it's expected rather than a surprise —
and note it is far easier to obtain than grades ("who registered" is not sensitive in the way a
grade sheet is).

### I. Immutable weekly per-student aggregates
Insurance against A. Even if raw events age out, a weekly student×course aggregate table is tiny
and preserves everything §3–4 need. Run the pipeline weekly and archive the output.

### J. Legal basis and retention policy
Longitudinal tracking of named students across years, plus a named at-risk list, is a different
governance object from a per-course usage report. Settle the basis and the retention window before
the first watchlist exists, not after.

---

## 6. Collection checklist

Recurring, per semester:

- [ ] weekly Mixpanel export never skipped; archive raw
- [ ] dated `user-export-*.csv` snapshot (identity map)
- [ ] course content timeline snapshot
- [ ] enrollment table: student × course × semester
- [ ] program / track / year per student
- [ ] academic calendar (semester bounds, exam periods)
- [ ] registration status of last semester's students ← the dropout label
- [ ] append to product changelog; confirm ALS_v1 still computable
- [ ] archive weekly per-student aggregates

One-off, as soon as possible:

- [ ] check Mixpanel data-retention limit
- [ ] backfill events as far back as retention allows
- [ ] assign persistent pseudonymous `student_uid` (salted hash), keep an append-only
      email→uid crosswalk so identity survives email changes and analysis can drop emails

---

## 7. Pick-up order next semester

1. Verify §5.A/B — how much history exists, how many students appear in ≥2 semesters. Everything
   downstream is gated on that count.
2. Build the percentile-baseline series (§4.1) and eyeball the drop distribution before modelling.
3. Add recency / slope / regularity / personal-z to `churn_analysis.py` (§4.6) — small, improves
   T1 immediately, independent of everything else.
4. T2 as discrete-time survival (§4.5) on whatever multi-semester students exist.
5. Department early warning (§3) once an enrollment table covers a full program.
6. Grade-dependent items (§1 rows 7–9) last — they need the college in the loop, and 9 is a
   robustness check, not a headline.

## 8. Open items

- The Azrieli roster workbook (`azrieli/manager_request/`) does **not** yet have program/year
  columns (§5.F). Cheap to add while the request is still unsent.
- `churn_analysis.py` requires `moed_a_date` and gates on an 8-week pre-exam span, so T1 currently
  runs on ceramics only. The manager's exam dates unblock it for the other six courses.
- Whether the consolidated college package computes cross-course blocks in one session — six
  independent per-course tokens make §1 rows 7–9 permanently unrecoverable (`teacher_app.py` is
  one course per token today).