#!/usr/bin/env python3
"""
Aaron Owl — Local Analysis Script v2  (Teacher / Institution)
=============================================================
Run on your own machine. Your grade data NEVER leaves — only standardized,
aggregated effect sizes + sufficient statistics are written out.

Answers as many research questions as your grade data supports, all on
WITHIN-COURSE STANDARDIZED scores so results pool across courses:

  Q1  Does ALS correlate with the outcome?          (cross-sectional, all students)
  Q2  Does ALS correlate with A->B improvement?     (retakers; needs moed_a + moed_b)
  Q3  Does *increasing* activity raise the grade?   (within-person FE; needs A/B + dates)
  R1  Who fails? / R2  Who is absent?               (early-warning risk)
  subgroups  ALS->outcome within post-A activity segments (needs exam-window features)

SELF-DESCRIBING grade modes (auto-detected; override with --grade-mode):
  full_ab    email, moed_a, moed_b   -> every question
  single_a   email, moed_a           -> Q1, R1, R2, predictive
  final      email, final            -> Q1, R1, R2, predictive (outcome = final, --final-rule max|last)
  pass_fail  email, passed           -> Q1, R1   (reserved; not yet emitted)
The chosen mode + an `answered` list are stamped into results.json so the
meta-analysis pools each question only across courses that can answer it.

Usage:
    python analysis_script_v2.py \
        --features student_features_<course>_federation.csv \
        --grades   grades.csv \
        --course   "Course Name" \
        --out      results/

Output (no individual grades):  <out>/results.json   (the federation contract)
Requires: pandas, numpy, scipy   (sklearn optional, enables AUC/predictive)
"""
import argparse, json, hashlib, re
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

try:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score, cross_val_predict, LeaveOneOut, StratifiedKFold
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    HAS_SK = True
except ImportError:
    HAS_SK = False

SUPPRESS_K = 3          # suppress any group with fewer than K students
MIN_POS_MODEL = 10      # need >=10 of EACH class before fitting a CV classifier (AUC)
LOO_MAX_N = 40          # <= this many rows -> leave-one-out; else stratified 5-fold
MIN_POWER_N = 30        # below this (or min-class < 8) the early-warning is flagged low_power
TIER_ORDER = ['Low', 'Medium', 'High']
DEFAULT_PASS = 60

# Compact, pre-A-only feature set for the early-warning classifier. A FIXED small
# set (not the full ~40 risk_features) keeps the model stable at small n and makes
# coefficients comparable/poolable across courses. Columns absent or constant in a
# given course are dropped automatically.
CORE_MODEL_FEATURES = [
    'active_learning_score', 'active_weeks_ratio', 'total_active_events',
    'meaningful_sessions_ratio', 'feature_diversity_count', 'lecture_coverage_pct',
    'total_time_minutes', 'eval_submission_rate',
]


# ── grade cleaning ──────────────────────────────────────────────────────────
def clean_grade(v):
    """Extract leading numeric ('52 נכשל'->52); blank/absent/fail-word->NaN."""
    s = str(v).strip()
    if s in ('', 'nan', 'NaN', 'None', '-'):
        return np.nan
    m = pd.Series([s]).str.extract(r'^\s*(\d+(?:\.\d+)?)')[0].iloc[0]
    return float(m) if pd.notna(m) else np.nan


# ── grade-mode detection ────────────────────────────────────────────────────
# Self-describing federation: the analyzer infers which kind of grade data the
# teacher supplied and answers the maximal subset of questions it can. The mode
# is stamped into results.json so meta pools each question only across courses
# that can answer it (see the capability matrix in FEDERATED_QUESTIONS_SPEC.md).
GRADE_MODES = ('full_ab', 'single_a', 'final', 'pass_fail', 'components')

# which result blocks each mode can produce (drives `answered` + meta coverage)
MODE_QUESTIONS = {
    'full_ab':    ['Q1', 'Q2', 'Q3', 'R1', 'R2', 'predictive'],
    'single_a':   ['Q1', 'R1', 'R2', 'predictive'],
    'final':      ['Q1', 'R1', 'R2', 'predictive'],
    'pass_fail':  ['Q1', 'R1'],
    'components': ['Q1', 'R1', 'R2', 'predictive'],   # coursework composite (Q2/Q3 = sequential, later)
}
MODE_OUTCOME = {'full_ab': 'moed_a', 'single_a': 'moed_a',
                'final': 'final', 'pass_fail': 'pass_fail', 'components': 'composite'}


def _norm_col(s):
    """Normalize a name for matching milestone names to grade columns (EN/HE, spacing, case)."""
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


def _san(s):
    """Sanitize a milestone name to its window prefix token (matches pipeline._san)."""
    return re.sub(r'[^a-z0-9]+', '_', str(s).strip().lower()).strip('_') or 'm'


def composite_from_components(G, components, pass_mark=DEFAULT_PASS):
    """Weighted composite outcome from component grade columns (v3 coursework/mixed).
    `components` = [{name, weight, max}] from course_meta. Matches each component to a grade
    column by normalized name; missing component grade -> 0 (final-grade semantics). Returns
    (composite Series 0-100, meta) or (None, None) if no components matched."""
    colmap = {_norm_col(c): c for c in G.columns}
    matched = [(c, colmap[_norm_col(c['name'])]) for c in components if _norm_col(c['name']) in colmap]
    if not matched:
        return None, None
    wsum = sum(float(c.get('weight') or 1) for c, _ in matched) or 1.0
    comp = pd.Series(0.0, index=G.index)
    for c, col in matched:
        vals = G[col].map(clean_grade)
        mx = c.get('max')
        vals = (vals / float(mx) * 100) if mx else vals
        comp += (float(c.get('weight') or 1) / wsum) * vals.fillna(0.0)
    meta = {'components': [col for _, col in matched],
            'weights': {col: float(c.get('weight') or 1) for c, col in matched},
            'n_components': len(matched)}
    return comp, meta


def detect_grade_mode(G):
    """Infer the grade mode from columns + content (override with --grade-mode).
    Priority: real moed_b values -> full_ab; moed_a present -> single_a;
    a 'final' column -> final; only a pass/fail flag -> pass_fail."""
    cols = set(G.columns)
    has_a = 'moed_a' in cols and G['moed_a'].notna().any()
    has_b = 'moed_b' in cols and G['moed_b'].notna().any()
    has_final = 'final' in cols and G['final'].notna().any()
    has_pass = any(c in cols for c in ('passed', 'pass', 'pass_fail'))
    if has_a and has_b:
        return 'full_ab'
    if has_a:
        return 'single_a'
    if has_final:
        return 'final'
    if has_pass:
        return 'pass_fail'
    return 'single_a'           # conservative fallback


# ── effect-size helpers (all return value + standard error) ─────────────────
def cohens_d(a, b):
    """d for group a vs group b (a-b) with Hedges-style SE."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    sp = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    if sp == 0:
        return None
    d = (a.mean() - b.mean()) / sp
    se = np.sqrt((n1 + n2) / (n1 * n2) + d ** 2 / (2 * (n1 + n2)))
    return {'d': round(d, 4), 'se': round(se, 4), 'n1': n1, 'n2': n2}


def log_or(a_pos, a_n, b_pos, b_n):
    """log odds ratio of being 'high' in group A vs B, Haldane-corrected."""
    a, b = a_pos + 0.5, (a_n - a_pos) + 0.5
    c, d = b_pos + 0.5, (b_n - b_pos) + 0.5
    lor = np.log((a * d) / (b * c))
    se = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {'logOR': round(lor, 4), 'se': round(se, 4)}


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~np.isnan(x) & ~np.isnan(y)
    if m.sum() < 5 or np.std(x[m]) == 0 or np.std(y[m]) == 0:
        return None
    r, _ = stats.pearsonr(x[m], y[m])
    rs, _ = stats.spearmanr(x[m], y[m])
    return {'r': round(float(r), 4), 'spearman': round(float(rs), 4), 'n': int(m.sum())}


def ols_beta(y, X, names):
    """OLS y ~ X (X already includes intercept col). Returns coef+SE per name."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    m = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    y, X = y[m], X[m]
    n, k = X.shape
    if n <= k + 1:
        return None
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sigma2 = (resid @ resid) / (n - k)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    return {nm: {'beta': round(float(beta[i]), 4), 'se': round(float(se[i]), 4)}
            for i, nm in enumerate(names)} | {'n': int(n)}


def tier_suff_stats(df, col):
    """Sufficient stats per ALS tier: n, sum, sumsq (poolable), suppressed if n<K."""
    out = {}
    for tier in TIER_ORDER:
        g = df[df['active_learning_level'] == tier][col].dropna()
        if len(g) < SUPPRESS_K:
            out[tier] = {'n': int(len(g)), 'suppressed': True}
        else:
            out[tier] = {'n': int(len(g)), 'mean': round(float(g.mean()), 4),
                         'sd': round(float(g.std(ddof=1)), 4),
                         'sum': round(float(g.sum()), 4),
                         'sumsq': round(float((g ** 2).sum()), 4), 'suppressed': False}
    return out


def risk_features(df):
    """Pre-A numeric predictors only (exclude postA_=leakage, normalized dupes, targets)."""
    drop = {'moed_a', 'moed_b', 'final', 'composite', 'score', 'score_z',
            'moed_a_z', 'moed_b_z', 'high', 'course_id', 'cluster_id', 'in_roster'}
    return [c for c in df.columns
            if not c.startswith('postA_') and not c.endswith(('_z', '_pct'))
            and c not in drop and pd.api.types.is_numeric_dtype(df[c]) and df[c].std() > 0]


def _model_features(df, feat_cols):
    """Compact, pre-A-only, non-constant feature list for the early-warning model."""
    core = [c for c in CORE_MODEL_FEATURES if c in df.columns and df[c].std(ddof=0) > 0]
    return core or feat_cols[:8]


def _oof_early_warning(pop, y, feat_cols):
    """Phase-1 early warning: predict the binary event from PRE-A features only.

    Out-of-fold (leave-one-out at small n) probabilities give a stable AUC and a
    confusion matrix at the base-rate threshold; a full-data standardized logistic
    gives coefficient signs. Everything returned is an aggregate (counts, AUC,
    coefficients) — poolable across courses, no individual grades leave.
    """
    if not HAS_SK:
        return {'available': False, 'reason': 'sklearn not installed'}
    n, n_pos = int(len(y)), int(y.sum())
    n_neg = n - n_pos
    if min(n_pos, n_neg) < SUPPRESS_K:
        return {'available': False, 'reason': 'a class < suppress_k', 'n': n, 'n_pos': n_pos}
    feats = _model_features(pop, feat_cols)
    X = pop[feats].fillna(pop[feats].median(numeric_only=True)).values
    yv = np.asarray(y, int)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))
    # leave-one-out at small n OR when the minority class is too small to stratify 5 ways
    use_loo = n <= LOO_MAX_N or min(n_pos, n_neg) < 10
    cv = LeaveOneOut() if use_loo else StratifiedKFold(5, shuffle=True, random_state=0)
    try:
        proba = cross_val_predict(clf, X, yv, cv=cv, method='predict_proba')[:, 1]
    except Exception as e:
        return {'available': False, 'reason': f'cv failed: {str(e)[:60]}', 'n': n, 'n_pos': n_pos}
    thr = n_pos / n                                   # base-rate threshold favours recall of the rare class
    pred = (proba >= thr).astype(int)
    tp = int(((pred == 1) & (yv == 1)).sum()); fp = int(((pred == 1) & (yv == 0)).sum())
    tn = int(((pred == 0) & (yv == 0)).sum()); fn = int(((pred == 0) & (yv == 1)).sum())
    full = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5)).fit(X, yv)
    coef = full.named_steps['logisticregression'].coef_[0]
    return {
        'available': True, 'n': n, 'n_pos': n_pos,
        'cv': 'loo' if use_loo else 'stratified5',
        'features': feats,
        'auc_oof': round(float(roc_auc_score(yv, proba)), 4),
        'threshold': round(float(thr), 4),
        'confusion': {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn},
        'sensitivity': round(tp / (tp + fn), 4) if (tp + fn) else None,
        'specificity': round(tn / (tn + fp), 4) if (tn + fp) else None,
        'precision': round(tp / (tp + fp), 4) if (tp + fp) else None,
        # standardized logistic coefficients (sign + magnitude), poolable for consistency
        'coef_std_logistic': {c: round(float(v), 4)
                              for c, v in sorted(zip(feats, coef), key=lambda kv: -abs(kv[1]))},
        'low_power': bool(n < MIN_POWER_N or min(n_pos, n_neg) < 8),
    }


def classify(df_pop, y, feat_cols):
    """Binary-risk block: base rate, ALS log-odds (High vs Low), per-feature corr, CV-AUC,
    plus a pre-A-only early-warning model (OOF AUC + confusion + coef signs).
    Returns aggregates only; suppressed if either class < SUPPRESS_K."""
    m = y.notna()
    pop, y = df_pop[m], y[m].astype(int)
    n, n_pos = len(pop), int(y.sum())
    out = {'n': n, 'n_pos': n_pos, 'base_rate': round(n_pos / n, 4) if n else None}
    if n_pos < SUPPRESS_K or (n - n_pos) < SUPPRESS_K:
        out['suppressed'] = True
        return out
    out['suppressed'] = False
    # ALS effect: odds of the event for High vs Low tier
    hi, lo = pop['active_learning_level'] == 'High', pop['active_learning_level'] == 'Low'
    if hi.sum() >= SUPPRESS_K and lo.sum() >= SUPPRESS_K:
        out['logOR_ALS_high_low'] = log_or(int(y[hi].sum()), int(hi.sum()),
                                           int(y[lo].sum()), int(lo.sum()))
    # per-feature point-biserial (poolable)
    eff = {}
    for c in feat_cols:
        x = pop[c].astype(float)
        if x.std(ddof=0) > 0:
            eff[c] = round(float(np.corrcoef(x, y)[0, 1]), 4)
    out['feature_corr'] = dict(sorted(eff.items(), key=lambda kv: -abs(kv[1]))[:8])
    # multivariate CV AUC — only with enough of BOTH classes (else AUC is noise)
    out['auc'] = None
    if HAS_SK and n_pos >= MIN_POS_MODEL and (n - n_pos) >= MIN_POS_MODEL:
        X = pop[feat_cols].fillna(pop[feat_cols].median()).values
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        try:
            a = cross_val_score(model, X, y.values, cv=min(5, n_pos), scoring='roc_auc')
            out['auc'] = {'mean': round(float(a.mean()), 4),
                          'se': round(float(a.std() / np.sqrt(len(a))), 4), 'n': n}
        except Exception as e:
            out['auc'] = {'error': str(e)[:80]}
    # Phase-1 early warning: OOF AUC + confusion + coefficient signs (pre-A only)
    out['early_warning'] = _oof_early_warning(pop, y, feat_cols)
    return out


def predictive_block(df, feat_cols, target='score_z'):
    """Data-driven model for the standardized outcome + ALS audit: does a free
    model beat ALS-only? Returns CV R² (full vs ALS-only), the gap, RF
    importances, Ridge std-coefs."""
    pop = df.dropna(subset=[target])
    n = len(pop)
    out = {'n': int(n)}
    if not HAS_SK or n < 30:
        out['suppressed'] = True
        return out
    out['suppressed'] = False
    y = pop[target].values
    X = pop[feat_cols].fillna(pop[feat_cols].median())
    cv = min(5, n // 6)

    def cv_r2(Xm):
        m = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        s = cross_val_score(m, Xm, y, cv=cv, scoring='r2')
        return {'mean': round(float(s.mean()), 4), 'se': round(float(s.std() / np.sqrt(len(s))), 4)}

    out['cv_r2_full'] = cv_r2(X.values)                              # all features, learned weights
    out['cv_r2_als_only'] = cv_r2(pop[['active_learning_score']].values)  # ALS construct alone
    out['delta_r2_full_minus_als'] = round(out['cv_r2_full']['mean'] - out['cv_r2_als_only']['mean'], 4)

    # RF importances (poolable by N-weighted avg) + Ridge standardized coefficients
    rf = RandomForestRegressor(n_estimators=300, random_state=0).fit(X, y)
    imp = sorted(zip(feat_cols, rf.feature_importances_), key=lambda kv: -kv[1])
    out['rf_importance'] = {c: round(float(v), 4) for c, v in imp[:10]}
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X, y)
    coef = ridge.named_steps['ridge'].coef_
    out['ridge_std_coef'] = {c: round(float(v), 4)
                             for c, v in sorted(zip(feat_cols, coef), key=lambda kv: -abs(kv[1]))[:10]}
    return out


def value_added_block(df, target='score_z'):
    """Flagship #1 — causal robustness / incremental validity: does ALS predict the outcome
    ABOVE a baseline ability proxy? Baseline = in-platform performance (eval/quiz avg scores)
    and any early-activity `warmup_` features (if the pipeline built a warm-up window). OLS
    `outcome ~ baseline + ALS`; reports the ALS **partial standardized coefficient + SE**
    (poolable) and CV ΔR² (baseline vs +ALS). Directly answers the "it's just good students"
    critique. Conservative — eval performance is partly a mediator, so a surviving ALS effect
    is a lower bound. Aggregates only."""
    if not HAS_SK:
        return {'available': False, 'reason': 'sklearn not installed'}
    pop = df.dropna(subset=[target]).copy()
    n = len(pop)
    # baseline = early-engagement (warmup activity) + early in-platform performance (eval/quiz).
    # A compact set — not all 50 warmup columns — to avoid overfitting the baseline.
    cand = ['warmup_active_learning_score', 'warmup_total_active_events',
            'warmup_active_weeks_ratio', 'eval_avg_score', 'quiz_avg_score']
    base = [c for c in cand if c in pop.columns
            and pop[c].notna().sum() >= SUPPRESS_K and pop[c].std(ddof=0) > 0]
    if not base:
        return {'available': False, 'n': int(n),
                'reason': 'no baseline ability proxy (eval/quiz performance or warmup activity)'}
    if n < 20 or 'active_learning_score' not in pop.columns:
        return {'available': True, 'suppressed': True, 'n': int(n), 'baseline': base}
    y = pop[target].values

    def zmat(cols):
        M = []
        for c in cols:
            v = pop[c].astype(float); v = v.fillna(v.median()); s = v.std(ddof=0)
            M.append(((v - v.mean()) / s).values if s > 0 else np.zeros(n))
        return np.column_stack([np.ones(n)] + M)

    beta = ols_beta(y, zmat(base + ['active_learning_score']),
                    ['intercept'] + base + ['active_learning_score'])

    def cv_r2(cols):
        X = pop[cols].fillna(pop[cols].median()).values
        s = cross_val_score(make_pipeline(StandardScaler(), Ridge(alpha=1.0)), X, y,
                            cv=min(5, n // 6), scoring='r2')
        return {'mean': round(float(s.mean()), 4), 'se': round(float(s.std() / np.sqrt(len(s))), 4)}

    r2b, r2f = cv_r2(base), cv_r2(base + ['active_learning_score'])
    return {'available': True, 'suppressed': False, 'n': int(n), 'baseline': base,
            'als_partial': beta.get('active_learning_score') if beta else None,
            'cv_r2_baseline': r2b, 'cv_r2_full': r2f,
            'delta_r2_als': round(r2f['mean'] - r2b['mean'], 4)}


def sequential_task_block(df, components):
    """Flagship #3 — rolling per-task prediction (coursework/mixed). Predict **task n** from the
    **prior tasks 1…n−1** (grades) + activity in the run-up window `pre_<task_n>`. Reports, per
    step, CV R² from priors-only vs priors+activity (does activity add?), so you see prediction
    quality grow with history and quantify activity's incremental value before each next task.
    Aggregates only. Needs ≥2 dated graded tasks."""
    if not HAS_SK or not components:
        return {'available': False, 'reason': 'no components / sklearn'}
    dated = sorted([c for c in components if c.get('date')], key=lambda c: str(c['date']))
    tasks = []
    for c in dated:
        col = next((gc for gc in df.columns if _norm_col(gc) == _norm_col(c['name'])), None)
        if col is not None:
            tasks.append({'name': c['name'], 'col': col, 'win': f'pre_{_san(c["name"])}'})
    if len(tasks) < 2:
        return {'available': False, 'reason': 'need >=2 dated graded tasks', 'n_tasks': len(tasks)}
    ACT = ('total_active_events', 'active_learning_score', 'active_weeks_ratio', 'meaningful_sessions_ratio')
    steps = []
    for n in range(1, len(tasks)):                      # predict tasks[n] from tasks[0..n-1]
        tgt, priors, win = tasks[n]['col'], [tasks[i]['col'] for i in range(n)], tasks[n]['win']
        act = [c for c in df.columns if c.startswith(win + '_') and c.endswith(ACT)]
        sub = df.copy()
        y = pd.to_numeric(sub[tgt], errors='coerce'); m = y.notna()
        sub, y = sub[m], y[m].values
        nn = len(sub)
        if nn < 20:
            steps.append({'step': n + 1, 'task': tasks[n]['name'], 'n': int(nn), 'suppressed': True})
            continue

        def cvr2(cols):
            X = sub[cols].apply(pd.to_numeric, errors='coerce')
            X = X.fillna(X.median()).values
            s = cross_val_score(make_pipeline(StandardScaler(), Ridge(1.0)), X, y,
                                cv=min(5, nn // 6), scoring='r2')
            return round(float(s.mean()), 4)

        r2p = cvr2(priors)
        r2f = cvr2(priors + act) if act else r2p
        steps.append({'step': n + 1, 'task': tasks[n]['name'], 'n': int(nn),
                      'r2_priors': r2p, 'r2_priors_plus_activity': r2f,
                      'delta_activity': round(r2f - r2p, 4), 'n_activity_feats': len(act)})
    return {'available': True, 'n_tasks': len(tasks), 'steps': steps}


def moment_block(df):
    """Sufficient statistics (v3, §8): means, SDs, and the correlation matrix over the key
    variables (outcome, ALS, core activity, early/warmup activity, in-platform performance).
    From means+SD+corr, ANY future linear analysis — partial correlations, regressions,
    incremental validity — is recoverable WITHOUT re-contacting the teacher. Aggregates only;
    this is what makes the one-shot collection future-proof."""
    varlist = ['score_z', 'active_learning_score', 'active_weeks_ratio', 'total_active_events',
               'meaningful_sessions_ratio', 'feature_diversity_count', 'lecture_coverage_pct',
               'eval_avg_score', 'eval_submission_rate', 'warmup_active_learning_score',
               'warmup_total_active_events']
    cols = [c for c in varlist if c in df.columns]
    M = df[cols].apply(pd.to_numeric, errors='coerce')
    n = int(M.dropna(how='all').shape[0])
    if n < 10 or len(cols) < 2:
        return {'available': False, 'reason': 'too few rows/variables', 'n': n}
    corr = M.corr()
    cm = {a: {b: round(float(corr.loc[a, b]), 4)
              for j, b in enumerate(cols) if j >= i and pd.notna(corr.loc[a, b])}
          for i, a in enumerate(cols)}
    return {'available': True, 'n': n, 'variables': cols,
            'mean': M.mean().round(4).to_dict(), 'sd': M.std(ddof=1).round(4).to_dict(),
            'corr_upper': cm, 'pairwise': True,
            'note': 'means + sd + corr → recover any linear analysis among these variables'}


def pre_post_a_block(df):
    """Grade-FREE within-student paired change in activity from pre-A to post-A.
    Tests whether platform engagement drops after Moed A (repeated measures per
    student). Returns a paired standardized effect (Cohen's dz + SE, poolable via
    DL) plus t / Wilcoxon p. Needs exam-window features; grades not used."""
    if 'postA_total_active_events' not in df.columns:
        return {'available': False, 'reason': 'no exam-window features (moed dates not configured)'}
    pre = df['total_active_events'].fillna(0).astype(float)
    post = df['postA_total_active_events'].fillna(0).astype(float)
    n = int(len(df))
    diff = post - pre
    sd = float(diff.std(ddof=1)) if n > 1 else 0.0
    out = {'available': True, 'n': n, 'metric': 'total_active_events',
           'pre_mean': round(float(pre.mean()), 2), 'post_mean': round(float(post.mean()), 2),
           'mean_delta': round(float(diff.mean()), 2)}
    if n < SUPPRESS_K or sd == 0:
        out['suppressed'] = True
        return out
    out['suppressed'] = False
    dz = float(diff.mean() / sd)                      # paired Cohen's dz (poolable)
    out['cohens_dz'] = round(dz, 4)
    out['se'] = round(float(np.sqrt(1.0 / n + dz ** 2 / (2 * n))), 4)
    t, p = stats.ttest_rel(post, pre)
    out['t'] = round(float(t), 3); out['p'] = float(f'{p:.3e}')
    try:
        _, pw = stats.wilcoxon(post, pre)
        out['wilcoxon_p'] = float(f'{pw:.3e}')
    except Exception:
        out['wilcoxon_p'] = None
    return out


def adoption_from_grades(gd):
    """Adoption contrast computed AUTOMATICALLY from the grades file (default path): app-users
    are emails present in the feature CSV; non-users are graded students absent from it (they sat
    the exam but never used the app). `gd` has columns email, grade, is_app_user. Aggregates only;
    suppressed unless ≥K in each group."""
    gd = gd.copy(); gd['grade'] = pd.to_numeric(gd['grade'], errors='coerce')
    gu = gd[gd['is_app_user']]['grade'].dropna()
    gn = gd[~gd['is_app_user']]['grade'].dropna()
    tot = len(gu) + len(gn)
    out = {'available': True, 'source': 'grades_file', 'n_app_users': int(len(gu)),
           'n_non_users': int(len(gn)), 'adoption_rate': round(len(gu) / tot, 4) if tot else None}
    if len(gu) < SUPPRESS_K or len(gn) < SUPPRESS_K:
        out['suppressed'] = True
        out['reason'] = 'need ≥3 graded app-users AND ≥3 graded non-users in the grades file'
        return out
    out['suppressed'] = False
    out['mean_grade_app_users'] = round(float(gu.mean()), 2)
    out['mean_grade_non_users'] = round(float(gn.mean()), 2)
    out['cohens_d_user_minus_non'] = cohens_d(gu.values, gn.values)
    t, p = stats.ttest_ind(gu, gn, equal_var=False)
    out['welch_t'] = round(float(t), 3); out['welch_p'] = float(f'{p:.3e}')
    return out


def adoption_block(roster_path):
    """Adoption contrast: exam grade of app-USERS vs NON-USERS (students who sat the
    exam but never used the platform). Reads roster_matched.csv (email, grade,
    is_app_user — produced by match_roster.py). Answers 'does using Aaron Owl relate
    to the grade?'. Aggregates only; suppressed unless ≥K in EACH group."""
    if not roster_path:
        return {'available': False, 'reason': 'no --roster provided (full exam roster incl. non-users)'}
    r = pd.read_csv(roster_path)
    r.columns = [c.strip().lower() for c in r.columns]
    if 'is_app_user' not in r.columns or 'grade' not in r.columns:
        return {'available': False, 'reason': 'roster needs columns: email, grade, is_app_user'}
    r['grade'] = pd.to_numeric(r['grade'], errors='coerce')
    is_user = r['is_app_user'].astype(str).str.lower().isin(['true', '1', 'yes'])
    gu = r[is_user]['grade'].dropna()
    gn = r[~is_user]['grade'].dropna()
    out = {'available': True, 'n_app_users': int(len(gu)), 'n_non_users': int(len(gn)),
           'adoption_rate': round(len(gu) / (len(gu) + len(gn)), 4) if (len(gu) + len(gn)) else None}
    if len(gu) < SUPPRESS_K or len(gn) < SUPPRESS_K:
        out['suppressed'] = True
        out['reason'] = 'need ≥3 graded students in EACH of app-users / non-users'
        return out
    out['suppressed'] = False
    out['mean_grade_app_users'] = round(float(gu.mean()), 2)
    out['mean_grade_non_users'] = round(float(gn.mean()), 2)
    out['cohens_d_user_minus_non'] = cohens_d(gu.values, gn.values)      # +ve = users score higher
    t, p = stats.ttest_ind(gu, gn, equal_var=False)
    out['welch_t'] = round(float(t), 3); out['welch_p'] = float(f'{p:.3e}')
    return out


# ── the three questions ─────────────────────────────────────────────────────
def analyze(features_path, grades_path, course_name, pass_mark=DEFAULT_PASS,
            grade_mode=None, final_rule='max', roster_path=None, course_meta_path=None):
    F = pd.read_csv(features_path)
    F['email'] = F['email'].str.lower().str.strip()
    G = pd.read_csv(grades_path)
    G.columns = [c.strip().lower() for c in G.columns]
    G['email'] = G['email'].str.lower().str.strip()
    # canonicalize a single-grade column alias -> 'final'
    for alias in ('final_grade', 'grade'):
        if alias in G.columns and 'final' not in G.columns:
            G = G.rename(columns={alias: 'final'})
    for c in ('moed_a', 'moed_b', 'final'):
        if c in G.columns:
            G[c] = G[c].map(clean_grade)

    # v3: course metadata — from the pipeline's course_meta_<key>.json OR the teacher-filled
    # course_metadata.yaml (moderators + task structure). Accept JSON or YAML.
    course_meta = {}
    if course_meta_path and Path(course_meta_path).exists():
        txt = Path(course_meta_path).read_text()
        try:
            course_meta = json.loads(txt)
        except Exception:
            import yaml
            course_meta = yaml.safe_load(txt) or {}
    components = (course_meta.get('components') or course_meta.get('milestones')
                 or course_meta.get('tasks'))

    # v3 components mode: weighted composite outcome from component grade columns
    comp_meta = None
    if components:
        comp, comp_meta = composite_from_components(G, components, pass_mark)
        if comp is not None:
            G['composite'] = comp

    mode = (grade_mode or ('components' if comp_meta else detect_grade_mode(G))).lower()
    if mode not in GRADE_MODES:
        raise SystemExit(f"unknown --grade-mode {mode!r}; choose from {GRADE_MODES}")
    # ensure grade columns exist downstream regardless of what was sent
    for c in ('moed_a', 'moed_b', 'final', 'composite'):
        if c not in G.columns:
            G[c] = np.nan

    roster = set(G['email'])
    comp_cols = comp_meta['components'] if comp_meta else []          # per-task grade columns
    merge_cols = list(dict.fromkeys(['email', 'moed_a', 'moed_b', 'final', 'composite'] + comp_cols))
    df = F.merge(G[[c for c in merge_cols if c in G.columns]], on='email', how='left')
    df['in_roster'] = df['email'].isin(roster)

    # primary outcome by mode
    df['score'] = (df['composite'] if mode == 'components'
                   else df['final'] if mode == 'final' else df['moed_a'])
    outcome_semantics = (f'final_{final_rule}' if mode == 'final' else MODE_OUTCOME[mode])
    course_type = course_meta.get('course_type') or course_meta.get('grading_type') or {
        'full_ab': 'exam', 'single_a': 'exam', 'final': 'exam',
        'pass_fail': 'pass_fail', 'components': 'coursework'}.get(mode, 'exam')

    # within-course standardization against the outcome distribution
    S = df['score'].dropna()
    mu, sd = float(S.mean()), float(S.std(ddof=1))
    high_cut = float(S.quantile(2 / 3))                    # relative 'high' = top tertile
    df['score_z'] = (df['score'] - mu) / sd
    df['high'] = (df['score'] >= high_cut).astype('Int64')
    # A/B z-scores (same scale) — only meaningful in full_ab, used by Q2/Q3
    df['moed_a_z'] = (df['moed_a'] - mu) / sd
    df['moed_b_z'] = (df['moed_b'] - mu) / sd

    # second capability axis: exam-window features (need moed dates in pipeline).
    # No dates -> single 'all' window -> no postA_ block -> Q3 + subgroups disabled.
    has_windows = 'postA_total_active_events' in df.columns
    answered = list(MODE_QUESTIONS[mode])
    if not has_windows and 'Q3' in answered:
        answered.remove('Q3')
    if has_windows:
        answered.append('subgroups')                        # post-A segment analysis
        answered.append('pre_post_a')                       # grade-free paired activity change
    res = {'course': course_name,
           'course_id': hashlib.sha256(course_name.encode()).hexdigest()[:12],
           'n_features': int(len(F)),
           'course_type': course_type,
           'grade_mode': mode,
           'components': comp_meta,
           'delivery_mode': course_meta.get('delivery_mode'),
           'attendance_required': course_meta.get('attendance_required'),
           'outcome_semantics': outcome_semantics,
           'has_exam_windows': has_windows,
           'answered': answered,
           'standardization': {'moed_a_mean': round(mu, 2), 'moed_a_sd': round(sd, 2),
                               'high_cut': round(high_cut, 2), 'suppress_k': SUPPRESS_K,
                               'outcome': outcome_semantics}}

    # ---- Q1: ALS -> outcome (all students with a score) -----------------------
    A1 = df.dropna(subset=['score'])
    hi = A1[A1['active_learning_level'] == 'High']
    lo = A1[A1['active_learning_level'] == 'Low']
    res['Q1'] = {
        'n': int(len(A1)),
        'tiers_score_z': tier_suff_stats(A1, 'score_z'),
        'r_ALS_score': pearson(A1['active_learning_score'], A1['score_z']),
        'd_high_low_score': cohens_d(hi['score_z'], lo['score_z']),
        'logOR_high_score': (log_or(int(hi['high'].sum()), len(hi),
                                    int(lo['high'].sum()), len(lo))
                             if len(hi) >= SUPPRESS_K and len(lo) >= SUPPRESS_K else None),
    }

    # ---- Q2 / Q3: A->B improvement — only when both sittings are present -------
    if mode == 'full_ab':
        B = df.dropna(subset=['moed_a', 'moed_b']).copy()
        B['imp_z'] = (B['moed_b'] - B['moed_a']) / sd
        hiB = B[B['active_learning_level'] == 'High']
        loB = B[B['active_learning_level'] == 'Low']
        res['Q2'] = {
            'n_retakers': int(len(B)),
            'n_b_only': int((df['moed_b'].notna() & df['moed_a'].isna()).sum()),
            'paired': ({'n': int(len(B)),
                        'mean_diff_z': round(float(B['imp_z'].mean()), 4),
                        'sd_diff_z': round(float(B['imp_z'].std(ddof=1)), 4)}
                       if len(B) >= SUPPRESS_K else {'n': int(len(B)), 'suppressed': True}),
            'tiers_imp_z': tier_suff_stats(B, 'imp_z'),
            'r_ALS_imp': pearson(B['active_learning_score'], B['imp_z']),
            'd_high_low_imp': cohens_d(hiB['imp_z'], loB['imp_z']),
        }
        res['Q3'] = ({'n': int(len(B)), 'beta_dRate': None} if has_windows
                     else {'available': False,
                           'reason': 'no exam-window features (moed dates not configured)'})
        if has_windows and len(B) >= SUPPRESS_K + 2 and 'postA_total_active_events' in B.columns:
            def rate(ev, days):
                return np.where(days > 0, ev / np.maximum(days, 1), 0.0)
            pre = rate(B['total_active_events'].values, B['active_days'].values)
            post = rate(B['postA_total_active_events'].fillna(0).values,
                        B['postA_active_days'].fillna(0).values)
            # standardize rates within course (across retakers)
            def z(v):
                s = np.std(v)
                return (v - np.mean(v)) / s if s > 0 else v * 0
            d_rate = z(post) - z(pre)
            Xq3 = np.column_stack([np.ones(len(B)), d_rate, B['moed_a_z'].values])
            res['Q3']['beta_dRate'] = ols_beta(B['imp_z'].values, Xq3,
                                                ['intercept', 'dRate_z', 'moed_a_z'])
    else:
        why = 'no moed_b in this grade file' if mode == 'single_a' else \
              f'{mode} grades carry no A->B improvement signal'
        res['Q2'] = {'available': False, 'reason': why}
        res['Q3'] = {'available': False, 'reason': why}

    # ---- Risk family (early-warning classification) --------------------------
    feat_cols = risk_features(df)
    sat = df.dropna(subset=['score'])                         # R1 population: has a grade
    in_roster = df[df['in_roster']]                           # R2 population: enrolled
    res['risk'] = {
        'pass_mark': pass_mark,
        # R1 Fail: among those with a grade, did they fail (< pass_mark)?
        'R1_fail_a': classify(sat, (sat['score'] < pass_mark), feat_cols),
        # R2 No-show: among the enrolled roster, no grade recorded?
        'R2_no_show_a': (classify(in_roster, in_roster['score'].isna(), feat_cols)
                         if 'R2' in answered else {'available': False,
                         'reason': f'{mode} grades cannot identify exam absence'}),
    }
    if isinstance(res['risk']['R2_no_show_a'], dict) and 'available' not in res['risk']['R2_no_show_a']:
        res['risk']['R2_no_show_a']['coverage_note'] = \
            'platform-users only; never-engaged enrollees have no features'
        if mode == 'final':
            res['risk']['R2_no_show_a']['semantics_note'] = \
                'absence inferred from a missing FINAL grade — weaker than a true Moed-A no-show'

    # ---- Predictive block: data-driven model + ALS audit ---------------------
    res['predictive'] = predictive_block(df, feat_cols, target='score_z')

    # ---- Value-added (causal robustness): ALS above a baseline ability proxy --
    res['value_added'] = value_added_block(df, 'score_z')
    if res['value_added'].get('available') and not res['value_added'].get('suppressed'):
        answered.append('value_added')

    # ---- Sufficient statistics (moment matrix) — future-proofs the one-shot ask -
    res['sufficient_stats'] = moment_block(df)

    # ---- Sequential task model (coursework/mixed): rolling task-n prediction ---
    if comp_meta:
        res['sequential'] = sequential_task_block(df, components)
        if res['sequential'].get('available'):
            answered.append('sequential')

    # ---- Subgroups: post-A activity segments (windowed courses only) ----------
    # A grade-mode-agnostic way to use exam-window behaviour even without A/B
    # grades: split on whether the student was active in the A->B window and
    # report the ALS->outcome relationship within each segment. The segment is
    # defined by *post-A* activity but related to *pre-A* ALS, to limit leakage.
    if has_windows:
        seg = df.dropna(subset=['score']).copy()
        active = seg['postA_total_active_events'].fillna(0) > 0

        def seg_stats(g):
            if len(g) < SUPPRESS_K:
                return {'n': int(len(g)), 'suppressed': True}
            return {'n': int(len(g)),
                    'mean_score_z': round(float(g['score_z'].mean()), 4),
                    'tiers_score_z': tier_suff_stats(g, 'score_z'),
                    'r_ALS_score': pearson(g['active_learning_score'], g['score_z'])}

        A_, I_ = seg[active], seg[~active]
        res['subgroups'] = {
            'by': 'postA_active',
            'definition': 'any active event in the Moed-A -> Moed-B window',
            'segments': {'postA_active': seg_stats(A_), 'postA_inactive': seg_stats(I_)},
            'contrast_d_active_minus_inactive': cohens_d(A_['score_z'], I_['score_z']),
        }
        if outcome_semantics.startswith('final'):
            res['subgroups']['caveat'] = (
                'FINAL=max/last: post-A-active students likely retook, so their higher '
                'outcome is partly mechanical (retake replaces grade) — read as descriptive')
    else:
        res['subgroups'] = {'available': False,
                            'reason': 'no exam-window features (moed dates not configured)'}

    # ---- Pre→Post-A activity change (grade-free, paired within-student) --------
    res['pre_post_a'] = pre_post_a_block(df)

    # ---- Adoption contrast (default): app-users vs non-users -------------------
    # Default path = automatic from the grades file (any graded student NOT in the feature CSV
    # is a non-user). Advanced path = --roster (name-matched full roster).
    if roster_path:
        res['adoption'] = adoption_block(roster_path)
    else:
        gsc = (df['composite'] if mode == 'components' else df['final'] if mode == 'final' else df['moed_a'])
        # rebuild from G so non-users (dropped by the left-join into df) are included
        g_out = (G['composite'] if mode == 'components' else G['final'] if mode == 'final' else G['moed_a'])
        gd = pd.DataFrame({'email': G['email'], 'grade': g_out,
                           'is_app_user': G['email'].isin(set(F['email']))})
        res['adoption'] = adoption_from_grades(gd)
    if res['adoption'].get('available') and not res['adoption'].get('suppressed'):
        answered.append('adoption')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--features', required=True)
    ap.add_argument('--grades', required=True)
    ap.add_argument('--course', required=True)
    ap.add_argument('--pass-mark', type=float, default=DEFAULT_PASS)
    ap.add_argument('--grade-mode', choices=GRADE_MODES, default=None,
                    help='override auto-detection (full_ab | single_a | final | pass_fail)')
    ap.add_argument('--final-rule', choices=['max', 'last'], default='max',
                    help="for FINAL grades: is the single grade the max or the last sitting?")
    ap.add_argument('--roster', default=None,
                    help='roster_matched.csv (email,grade,is_app_user) from match_roster.py '
                         '— enables the app-user vs non-user adoption contrast')
    ap.add_argument('--course-meta', default=None,
                    help='course_meta_<key>.json (from pipeline) — course_type + components/weights '
                         '→ builds the weighted composite outcome for coursework/mixed courses')
    ap.add_argument('--out', default='results/')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = analyze(a.features, a.grades, a.course, pass_mark=a.pass_mark,
                  grade_mode=a.grade_mode, final_rule=a.final_rule, roster_path=a.roster,
                  course_meta_path=a.course_meta)
    (out / 'results.json').write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[{res['course']}] wrote {out/'results.json'}")
    print(f"  grade_mode={res['grade_mode']} ({res['outcome_semantics']})  "
          f"answers: {', '.join(res['answered'])}")
    print(f"  Q1 n={res['Q1']['n']}  r(ALS,score)={res['Q1']['r_ALS_score']}")
    if res['Q2'].get('available') is False:
        print(f"  Q2/Q3 n/a — {res['Q2']['reason']}")
    else:
        print(f"  Q2 retakers={res['Q2']['n_retakers']} (B-only={res['Q2']['n_b_only']})")
    def _ew(block, label):
        if not isinstance(block, dict) or block.get('available') is False:
            print(f"  {label} n/a — {block.get('reason') if isinstance(block, dict) else block}")
            return
        if block.get('suppressed'):
            print(f"  {label}: {block['n_pos']}/{block['n']} (suppressed)")
            return
        ew = block.get('early_warning', {})
        msg = f"  {label}: {block['n_pos']}/{block['n']}"
        if ew.get('available'):
            cm = ew['confusion']
            msg += (f"  | early-warning AUC={ew['auc_oof']} (cv={ew['cv']}"
                    + (", low_power" if ew['low_power'] else "") + ")"
                    f"  sens={ew['sensitivity']} spec={ew['specificity']}"
                    f"  confusion tp={cm['tp']} fp={cm['fp']} tn={cm['tn']} fn={cm['fn']}")
        print(msg)
    _ew(res['risk']['R1_fail_a'], 'R1 fail-A')
    _ew(res['risk']['R2_no_show_a'], 'R2 no-show-A')
    pp = res.get('pre_post_a', {})
    if pp.get('available') and not pp.get('suppressed'):
        print(f"  pre→post-A activity: {pp['pre_mean']:.0f}→{pp['post_mean']:.0f} events "
              f"(dz={pp['cohens_dz']}, paired p={pp['p']}, wilcoxon p={pp.get('wilcoxon_p')})")
    sq = res.get('sequential', {})
    if sq.get('available'):
        for s in sq['steps']:
            if s.get('suppressed'):
                print(f"  seq task {s['step']} ({s['task']}): n={s['n']} (suppressed)")
            else:
                print(f"  seq task {s['step']} ({s['task']}): priors R²={s['r2_priors']} "
                      f"+activity R²={s['r2_priors_plus_activity']} (Δ={s['delta_activity']:+})")
    ad = res.get('adoption', {})
    if ad.get('available') is False:
        print(f"  adoption n/a — {ad['reason']}")
    elif ad.get('suppressed'):
        print(f"  adoption: users={ad['n_app_users']} non-users={ad['n_non_users']} (suppressed — {ad.get('reason')})")
    else:
        print(f"  adoption: users {ad['mean_grade_app_users']} vs non-users {ad['mean_grade_non_users']} "
              f"(d={ad['cohens_d_user_minus_non']['d'] if ad['cohens_d_user_minus_non'] else None}, p={ad['welch_p']})")
    pb = res['predictive']
    if not pb.get('suppressed'):
        print(f"  Predictive: full R²={pb['cv_r2_full']['mean']} vs ALS-only "
              f"R²={pb['cv_r2_als_only']['mean']}  (Δ={pb['delta_r2_full_minus_als']:+}) "
              f"| top RF: {list(pb['rf_importance'])[:4]}")
    va = res.get('value_added', {})
    if va.get('available') is False:
        print(f"  Value-added n/a — {va['reason']}")
    elif va.get('suppressed'):
        print(f"  Value-added: n={va['n']} (suppressed) baseline={va['baseline']}")
    else:
        ap = va.get('als_partial') or {}
        print(f"  Value-added (ALS above baseline {va['baseline']}): "
              f"ALS β={ap.get('beta')}±{ap.get('se')}  ΔR²={va['delta_r2_als']:+} "
              f"(baseline R²={va['cv_r2_baseline']['mean']} → +ALS {va['cv_r2_full']['mean']})")


if __name__ == '__main__':
    main()