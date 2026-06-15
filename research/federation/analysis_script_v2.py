#!/usr/bin/env python3
"""
Aaron Owl — Local Analysis Script v2  (Teacher / Institution)
=============================================================
Run on your own machine. Your grade data NEVER leaves — only standardized,
aggregated effect sizes + sufficient statistics are written out.

Answers three research questions, all on WITHIN-COURSE STANDARDIZED scores so
results pool across courses of different difficulty:

  Q1  Does ALS correlate with the Moed-A outcome?  (cross-sectional, all students)
  Q2  Does ALS correlate with A->B improvement?     (retakers)
  Q3  Does *increasing* activity raise the grade?   (within-person FE, RTM-controlled)

Usage:
    python analysis_script_v2.py \
        --features student_features_<course>_federation.csv \
        --grades   grades_moed_ab.csv \
        --course   "Course Name" \
        --out      results/

Grades CSV schema:  email, moed_a, moed_b
    moed_a / moed_b = numeric per-sitting grade; blank = did not sit that exam.

Output (no individual grades):  <out>/results.json   (the federation contract)
Requires: pandas, numpy, scipy
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

try:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    HAS_SK = True
except ImportError:
    HAS_SK = False

SUPPRESS_K = 3          # suppress any group with fewer than K students
MIN_POS_MODEL = 10      # need >=10 of EACH class before fitting a CV classifier (AUC)
TIER_ORDER = ['Low', 'Medium', 'High']
DEFAULT_PASS = 60


# ── grade cleaning ──────────────────────────────────────────────────────────
def clean_grade(v):
    """Extract leading numeric ('52 נכשל'->52); blank/absent/fail-word->NaN."""
    s = str(v).strip()
    if s in ('', 'nan', 'NaN', 'None', '-'):
        return np.nan
    m = pd.Series([s]).str.extract(r'^\s*(\d+(?:\.\d+)?)')[0].iloc[0]
    return float(m) if pd.notna(m) else np.nan


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
    drop = {'moed_a', 'moed_b', 'moed_a_z', 'moed_b_z', 'high', 'course_id'}
    return [c for c in df.columns
            if not c.startswith('postA_') and not c.endswith(('_z', '_pct'))
            and c not in drop and pd.api.types.is_numeric_dtype(df[c]) and df[c].std() > 0]


def classify(df_pop, y, feat_cols):
    """Binary-risk block: base rate, ALS log-odds (High vs Low), per-feature corr, CV-AUC.
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
    return out


def predictive_block(df, feat_cols):
    """Data-driven model for moed_a_z + ALS audit: does a free model beat ALS-only?
    Returns CV R² (full vs ALS-only), the gap, RF importances, Ridge std-coefs."""
    pop = df.dropna(subset=['moed_a_z'])
    n = len(pop)
    out = {'n': int(n)}
    if not HAS_SK or n < 30:
        out['suppressed'] = True
        return out
    out['suppressed'] = False
    y = pop['moed_a_z'].values
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


# ── the three questions ─────────────────────────────────────────────────────
def analyze(features_path, grades_path, course_name, pass_mark=DEFAULT_PASS):
    F = pd.read_csv(features_path)
    F['email'] = F['email'].str.lower().str.strip()
    G = pd.read_csv(grades_path)
    G.columns = [c.strip().lower() for c in G.columns]
    for c in ('moed_a', 'moed_b'):
        if c not in G.columns:
            G[c] = np.nan
        G[c] = G[c].map(clean_grade)
    G['email'] = G['email'].str.lower().str.strip()
    roster = set(G['email'])
    df = F.merge(G[['email', 'moed_a', 'moed_b']], on='email', how='left')
    df['in_roster'] = df['email'].isin(roster)

    # within-course standardization against the Moed-A distribution
    A = df['moed_a'].dropna()
    mu, sd = float(A.mean()), float(A.std(ddof=1))
    high_cut = float(A.quantile(2 / 3))                    # relative 'high' = top tertile
    df['moed_a_z'] = (df['moed_a'] - mu) / sd
    df['moed_b_z'] = (df['moed_b'] - mu) / sd
    df['high'] = (df['moed_a'] >= high_cut).astype('Int64')

    res = {'course': course_name,
           'course_id': hashlib.sha256(course_name.encode()).hexdigest()[:12],
           'n_features': int(len(F)),
           'standardization': {'moed_a_mean': round(mu, 2), 'moed_a_sd': round(sd, 2),
                               'high_cut': round(high_cut, 2), 'suppress_k': SUPPRESS_K}}

    # ---- Q1: ALS -> Moed-A outcome (all students with moed_a) -----------------
    A1 = df.dropna(subset=['moed_a'])
    hi = A1[A1['active_learning_level'] == 'High']
    lo = A1[A1['active_learning_level'] == 'Low']
    res['Q1'] = {
        'n': int(len(A1)),
        'tiers_score_z': tier_suff_stats(A1, 'moed_a_z'),
        'r_ALS_score': pearson(A1['active_learning_score'], A1['moed_a_z']),
        'd_high_low_score': cohens_d(hi['moed_a_z'], lo['moed_a_z']),
        'logOR_high_score': (log_or(int(hi['high'].sum()), len(hi),
                                    int(lo['high'].sum()), len(lo))
                             if len(hi) >= SUPPRESS_K and len(lo) >= SUPPRESS_K else None),
    }

    # ---- Q2: ALS tier -> A->B improvement (paired retakers) -------------------
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

    # ---- Q3: within-person dRate -> dGrade, controlling moed_a_z --------------
    res['Q3'] = {'n': int(len(B)), 'beta_dRate': None}
    if len(B) >= SUPPRESS_K + 2 and 'postA_total_active_events' in B.columns:
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

    # ---- Risk family (early-warning classification) --------------------------
    feat_cols = risk_features(df)
    sat_A = df.dropna(subset=['moed_a'])                       # R1 population: sat Moed A
    in_roster = df[df['in_roster']]                            # R2 population: enrolled
    res['risk'] = {
        'pass_mark': pass_mark,
        # R1 Fail-A: among those who sat A, did they fail (< pass_mark)?
        'R1_fail_a': classify(sat_A, (sat_A['moed_a'] < pass_mark), feat_cols),
        # R2 No-show-A: among the enrolled roster, were they absent from A?
        'R2_no_show_a': classify(in_roster, in_roster['moed_a'].isna(), feat_cols),
    }
    res['risk']['R2_no_show_a']['coverage_note'] = \
        'platform-users only; never-engaged enrollees have no features'

    # ---- Predictive block: data-driven model + ALS audit ---------------------
    res['predictive'] = predictive_block(df, feat_cols)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--features', required=True)
    ap.add_argument('--grades', required=True)
    ap.add_argument('--course', required=True)
    ap.add_argument('--pass-mark', type=float, default=DEFAULT_PASS)
    ap.add_argument('--out', default='results/')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = analyze(a.features, a.grades, a.course, pass_mark=a.pass_mark)
    (out / 'results.json').write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"[{res['course']}] wrote {out/'results.json'}")
    print(f"  Q1 n={res['Q1']['n']}  r(ALS,score)={res['Q1']['r_ALS_score']}")
    print(f"  Q2 retakers={res['Q2']['n_retakers']} (B-only={res['Q2']['n_b_only']})")
    r1, r2 = res['risk']['R1_fail_a'], res['risk']['R2_no_show_a']
    print(f"  R1 fail-A: {r1['n_pos']}/{r1['n']} fails"
          + (f", AUC={r1.get('auc')}" if not r1.get('suppressed') else " (suppressed)"))
    print(f"  R2 no-show-A: {r2['n_pos']}/{r2['n']}"
          + (" (suppressed)" if r2.get('suppressed') else f", AUC={r2.get('auc')}"))
    pb = res['predictive']
    if not pb.get('suppressed'):
        print(f"  Predictive: full R²={pb['cv_r2_full']['mean']} vs ALS-only "
              f"R²={pb['cv_r2_als_only']['mean']}  (Δ={pb['delta_r2_full_minus_als']:+}) "
              f"| top RF: {list(pb['rf_importance'])[:4]}")


if __name__ == '__main__':
    main()