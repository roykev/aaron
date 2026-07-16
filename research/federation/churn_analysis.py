#!/usr/bin/env python3
"""
Aaron Owl — Churn / Early-warning analysis  (R3, grade-FREE)
============================================================
Runs on Aaron Owl's side from events alone — NO teacher, NO grades. Predicts which
ENGAGED students drop off before the exam, using only EARLY-window activity, so it can
fire mid-semester as a live early-warning signal and pool across courses like the rest.

Churn label (among students active in the EARLY window):
    churned = ZERO activity in the LATE window before moed_a_date.

Windows are COURSE-LENGTH-RELATIVE (a fixed 4w/3w split breaks on short courses):
    early = first EARLY_FRAC of the pre-exam span ; late = last LATE_FRAC.
    Floored at MIN_*_DAYS so very short courses still get a usable split.

Usage:
    python churn_analysis.py --course psy --out <dir>
    (reads config.yaml: weekly events + moed_a_date, same as pipeline.py)
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.event_loader import EventLoader
from modules.identity_resolver import IdentityResolver
from pipeline import load_config

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    HAS_SK = True
except ImportError:
    HAS_SK = False

EARLY_FRAC = 1 / 3      # early window = min(EARLY_WEEKS_CAP, this fraction of span)
LATE_FRAC = 1 / 4
EARLY_WEEKS_CAP = 4
LATE_WEEKS_CAP = 3
MIN_SPAN_WEEKS = 8      # churn N/A below this — cram-style courses have no early window
MIN_ELIGIBLE = 20       # too few engaged starters → rate only, no model
SUPPRESS_K = 3


def early_features(ev):
    """Per-student features from the early window only."""
    g = ev.groupby('email')
    f = pd.DataFrame({
        'early_events': g.size(),
        'early_active_events': g['is_active_event'].sum(),
        'early_active_days': g['datetime'].apply(lambda s: s.dt.date.nunique()),
        'early_unique_lectures': g['lecture'].nunique(),
        'early_active_weeks': g['week'].nunique(),
    })
    return f.fillna(0)


def analyze(config, course_key):
    cc = config['courses'][course_key]
    cid = cc['course_id']
    moed_a = pd.Timestamp(cc['moed_a_date'])
    ev = EventLoader(config).load(cid)
    ev = IdentityResolver(config).resolve(ev)
    ev = ev.dropna(subset=['email'])
    ev['email'] = ev['email'].str.lower().str.strip()

    course_start = ev['datetime'].min().normalize()
    span_days = (moed_a - course_start).days
    base = {'course': cc['name'], 'course_id': hashlib.sha256(cc['name'].encode()).hexdigest()[:12]}

    # Applicability gate: cram-style / short courses have no meaningful early→late split.
    if span_days < MIN_SPAN_WEEKS * 7:
        return {**base, 'applicable': False, 'span_days': int(span_days),
                'reason': f'pre-exam span {span_days}d < {MIN_SPAN_WEEKS}w — '
                          'engagement too compressed for an early/late churn split'}

    # Windows: capped at a few weeks, but never more than a fraction of the span.
    early_end = course_start + pd.Timedelta(days=min(EARLY_WEEKS_CAP * 7, span_days * EARLY_FRAC))
    late_start = moed_a - pd.Timedelta(days=min(LATE_WEEKS_CAP * 7, span_days * LATE_FRAC))

    early = ev[ev['datetime'] < early_end]
    late = ev[(ev['datetime'] >= late_start) & (ev['datetime'] < moed_a)]

    eligible = set(early[early['is_active_event']]['email'].unique())   # engaged starters
    active_late = set(late['email'].unique())
    feats = early_features(early[early['email'].isin(eligible)])
    feats['churned'] = [0 if e in active_late else 1 for e in feats.index]

    n = len(feats); n_churn = int(feats['churned'].sum())
    rate = n_churn / n if n else 0.0
    res = {**base, 'applicable': True,
           'window': {'span_days': int(span_days),
                      'early_end': str(early_end.date()), 'late_start': str(late_start.date()),
                      'course_start': str(course_start.date()), 'moed_a': str(moed_a.date())},
           'n_eligible': n, 'n_churned': n_churn, 'churn_rate': round(rate, 4)}

    Xcols = [c for c in feats.columns if c != 'churned']
    # per-feature point-biserial corr with churn — poolable. Needs variance in BOTH.
    eff = {}
    if 0 < n_churn < n:
        for c in Xcols:
            x = feats[c].astype(float)
            if x.std(ddof=0) > 0:
                eff[c] = round(float(np.corrcoef(x, feats['churned'])[0, 1]), 4)
    res['feature_churn_corr'] = dict(sorted(eff.items(), key=lambda kv: -abs(kv[1])))

    # multivariate model AUC (cross-validated) if enough of each class + enough starters
    res['model_auc'] = None
    if HAS_SK and n >= MIN_ELIGIBLE and n_churn >= SUPPRESS_K and (n - n_churn) >= SUPPRESS_K:
        X, y = feats[Xcols].values, feats['churned'].values
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        try:
            auc = cross_val_score(model, X, y, cv=min(5, n_churn), scoring='roc_auc')
            res['model_auc'] = {'mean': round(float(auc.mean()), 4),
                                'se': round(float(auc.std() / np.sqrt(len(auc))), 4), 'n': n}
            model.fit(X, y)
            coef = model.named_steps['logisticregression'].coef_[0]
            res['logodds_per_sd'] = {c: round(float(v), 4)
                                     for c, v in sorted(zip(Xcols, coef), key=lambda kv: -abs(kv[1]))}
        except Exception as e:
            res['model_auc'] = {'error': str(e)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', required=True)
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    config = load_config(a.config)
    res = analyze(config, a.course)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'churn_results.json').write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding='utf-8')
    if not res.get('applicable', True):
        print(f"[{res['course']}] churn N/A — {res['reason']}")
    else:
        w = res['window']
        print(f"[{res['course']}] churn {res['n_churned']}/{res['n_eligible']} = {res['churn_rate']*100:.1f}%"
              f"  (span {w['span_days']}d: early≤{w['early_end']}, late≥{w['late_start']})")
        print(f"  early-feature → churn corr: {res['feature_churn_corr']}")
        print(f"  model AUC: {res['model_auc']}")
    print(f"  wrote {out/'churn_results.json'}")


if __name__ == '__main__':
    main()
